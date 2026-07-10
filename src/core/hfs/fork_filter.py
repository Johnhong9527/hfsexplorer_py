"""
HFS+ Fork Filter

将文件的 data fork 和 resource fork 抽象为可 seek 的流。
参考 Java 版本的 ForkFilter 实现。

Usage:
    fork_filter = ForkFilter(
        fork_type=ForkType.DATA,
        cnid=file_id,
        fork_data=file_record.data_fork,
        extents_overflow=extents_btree,
        source_stream=volume_stream,
        allocation_block_size=4096,
        allocation_block_start=0
    )
    
    # 读取数据
    data = fork_filter.read(1024)
    
    # seek 到指定位置
    fork_filter.seek(100)
"""

import struct
from enum import IntEnum
from typing import List, Optional, BinaryIO, Tuple
from dataclasses import dataclass, field


class ForkType(IntEnum):
    """Fork 类型"""
    DATA = 0x00      # 数据分支
    RESOURCE = 0xFF  # 资源分支


@dataclass
class ExtentDescriptor:
    """
    Extent 描述符
    
    描述文件的一个连续区域。
    """
    start_block: int  # UInt32 - 起始分配块号
    block_count: int  # UInt32 - 分配块数量
    
    @property
    def is_empty(self) -> bool:
        """是否为空 extent"""
        return self.block_count == 0
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ExtentDescriptor':
        """从字节序列解析"""
        start_block, block_count = struct.unpack_from('>II', data, offset)
        return cls(start_block=start_block, block_count=block_count)


class ForkFilter:
    """
    Fork 过滤器
    
    将文件的 data fork 或 resource fork 抽象为可 seek 的流。
    自动处理 extents 和 overflow extents。
    
    主要特点：
    1. 支持延迟加载 overflow extents（当需要时才查询）
    2. 缓存已知的 extents
    3. 支持 seek 和 read 操作，自动处理跨 extent 的读取
    
    Usage:
        fork_filter = ForkFilter(
            fork_type=ForkType.DATA,
            cnid=file_id,
            fork_length=1024,
            basic_extents=[ExtentDescriptor(100, 10)],
            extents_overflow=extents_btree,
            source_stream=volume_stream,
            fs_offset=0,
            allocation_block_size=4096,
            first_block_byte_offset=0
        )
        
        # 读取全部数据
        data = fork_filter.read()
        
        # seek 到指定位置
        fork_filter.seek(100)
        data = fork_filter.read(50)
    """
    
    def __init__(self, 
                 fork_type: ForkType,
                 cnid: int,
                 fork_length: int,
                 basic_extents: List[ExtentDescriptor],
                 extents_overflow=None,
                 source_stream: BinaryIO = None,
                 fs_offset: int = 0,
                 allocation_block_size: int = 4096,
                 first_block_byte_offset: int = 0):
        """
        初始化 Fork 过滤器
        
        Args:
            fork_type: Fork 类型（DATA 或 RESOURCE）
            cnid: 文件的 Catalog Node ID
            fork_length: Fork 的逻辑长度（字节）
            basic_extents: 基本 extents（来自 catalog 记录）
            extents_overflow: ExtentsOverflowFile（用于查找 overflow extents）
            source_stream: 底层二进制流
            fs_offset: 文件系统在流中的偏移量
            allocation_block_size: 分配块大小
            first_block_byte_offset: 第一个分配块的字节偏移量
        """
        self._fork_type = fork_type
        self._cnid = cnid
        self._fork_length = fork_length
        self._extents: List[ExtentDescriptor] = list(basic_extents)
        self._extents_overflow = extents_overflow
        self._source_stream = source_stream
        self._fs_offset = fs_offset
        self._allocation_block_size = allocation_block_size
        self._first_block_byte_offset = first_block_byte_offset
        
        # 当前逻辑位置
        self._logical_position = 0
        
        # 上次读取的位置（用于优化 seek）
        self._last_logical_pos = -1
        self._last_physical_pos = 0
        
        # 是否所有 extents 都已映射
        self._all_extents_mapped = False
        
        # 计算每个 extent 的起始逻辑块号
        self._extent_start_blocks: List[int] = []
        cur_block = 0
        for ext in self._extents:
            self._extent_start_blocks.append(cur_block)
            cur_block += ext.block_count
    
    @classmethod
    def from_fork_data(cls, fork_type: ForkType, cnid: int,
                       fork_data_bytes: bytes,
                       extents_overflow=None,
                       source_stream: BinaryIO = None,
                       fs_offset: int = 0,
                       allocation_block_size: int = 4096,
                       first_block_byte_offset: int = 0) -> 'ForkFilter':
        """
        从 HFSPlusForkData 字节数据创建 ForkFilter
        
        Args:
            fork_type: Fork 类型
            cnid: 文件 CNID
            fork_data_bytes: HFSPlusForkData 的字节数据（80 字节）
            extents_overflow: ExtentsOverflowFile
            source_stream: 底层流
            fs_offset: 文件系统偏移
            allocation_block_size: 分配块大小
            first_block_byte_offset: 第一个块的字节偏移
        
        Returns:
            ForkFilter 实例
        """
        # 解析 HFSPlusForkData
        # logicalSize(8) + clumpSize(4) + totalBlocks(4) + extents(64)
        fork_length = struct.unpack_from('>Q', fork_data_bytes, 0)[0]
        total_blocks = struct.unpack_from('>I', fork_data_bytes, 12)[0]
        
        # 解析 8 个 extent 描述符
        basic_extents = []
        for i in range(8):
            start_block, block_count = struct.unpack_from('>II', fork_data_bytes, 16 + i * 8)
            if block_count > 0:
                basic_extents.append(ExtentDescriptor(start_block, block_count))
        
        return cls(
            fork_type=fork_type,
            cnid=cnid,
            fork_length=fork_length,
            basic_extents=basic_extents,
            extents_overflow=extents_overflow,
            source_stream=source_stream,
            fs_offset=fs_offset,
            allocation_block_size=allocation_block_size,
            first_block_byte_offset=first_block_byte_offset
        )
    
    @property
    def length(self) -> int:
        """获取 fork 的逻辑长度"""
        return self._fork_length
    
    @property
    def position(self) -> int:
        """获取当前逻辑位置"""
        return self._logical_position
    
    def seek(self, position: int):
        """
        移动到指定位置
        
        Args:
            position: 目标位置（字节偏移）
        """
        if position < 0:
            raise ValueError(f"位置不能为负数: {position}")
        if position > self._fork_length:
            raise ValueError(f"位置超出文件长度: {position} > {self._fork_length}")
        self._logical_position = position
    
    def tell(self) -> int:
        """获取当前位置"""
        return self._logical_position
    
    def read(self, size: int = -1) -> bytes:
        """
        读取数据
        
        Args:
            size: 要读取的字节数，-1 表示读取到末尾
        
        Returns:
            读取的数据
        """
        if self._source_stream is None:
            raise RuntimeError("未设置底层流")
        
        if self._logical_position >= self._fork_length:
            return b''  # EOF
        
        # 计算要读取的字节数
        if size < 0:
            bytes_to_read = self._fork_length - self._logical_position
        else:
            bytes_to_read = min(size, self._fork_length - self._logical_position)
        
        if bytes_to_read <= 0:
            return b''
        
        # 读取数据
        result = bytearray()
        bytes_remaining = bytes_to_read
        
        while bytes_remaining > 0:
            # 找到当前逻辑位置对应的 extent
            extent_index, extent_offset = self._find_extent_for_position(self._logical_position)
            
            if extent_index >= len(self._extents):
                break  # 没有更多 extent
            
            extent = self._extents[extent_index]
            
            # 计算在当前 extent 中可以读取的字节数
            extent_remaining = (extent.block_count * self._allocation_block_size) - extent_offset
            bytes_to_read_from_extent = min(bytes_remaining, extent_remaining)
            
            # 计算物理位置
            physical_offset = (self._fs_offset + 
                             self._first_block_byte_offset +
                             extent.start_block * self._allocation_block_size +
                             extent_offset)
            
            # seek 到物理位置
            if self._logical_position != self._last_logical_pos:
                self._source_stream.seek(physical_offset)
            elif self._source_stream.tell() != self._last_physical_pos:
                self._source_stream.seek(physical_offset)
            
            # 读取数据
            chunk = self._source_stream.read(bytes_to_read_from_extent)
            if not chunk:
                break
            
            result.extend(chunk)
            self._logical_position += len(chunk)
            bytes_remaining -= len(chunk)
            
            # 更新位置跟踪
            self._last_logical_pos = self._logical_position
            self._last_physical_pos = self._source_stream.tell()
        
        return bytes(result)
    
    def read_byte(self) -> int:
        """读取单个字节"""
        data = self.read(1)
        if data:
            return data[0]
        return -1
    
    def read_at(self, position: int, size: int) -> bytes:
        """
        在指定位置读取数据（不改变当前位置）
        
        Args:
            position: 起始位置
            size: 要读取的字节数
        
        Returns:
            读取的数据
        """
        old_pos = self._logical_position
        self.seek(position)
        data = self.read(size)
        self.seek(old_pos)
        return data
    
    def _find_extent_for_position(self, position: int) -> Tuple[int, int]:
        """
        查找指定逻辑位置对应的 extent
        
        Args:
            position: 逻辑位置（字节偏移）
        
        Returns:
            (extent_index, offset_in_extent)
        """
        bytes_remaining = position
        
        for i, extent in enumerate(self._extents):
            extent_size = extent.block_count * self._allocation_block_size
            
            if bytes_remaining < extent_size:
                return i, bytes_remaining
            
            bytes_remaining -= extent_size
        
        # 需要查找 overflow extents
        if not self._all_extents_mapped and self._extents_overflow is not None:
            self._load_overflow_extents()
            # 递归调用
            return self._find_extent_for_position(position)
        
        # 超出范围
        return len(self._extents), 0
    
    def _load_overflow_extents(self):
        """加载 overflow extents"""
        if self._all_extents_mapped or self._extents_overflow is None:
            return
        
        # 计算最后一个已知 extent 的结束块号
        last_start_block = 0
        for ext in self._extents:
            last_start_block = ext.start_block + ext.block_count
        
        # 从 ExtentsOverflowFile 查找 overflow extents
        try:
            overflow_extents = self._extents_overflow.get_extents_for_fork(
                self._cnid, self._fork_type
            )
            
            if overflow_extents:
                for ext in overflow_extents:
                    if ext.block_count == 0:
                        self._all_extents_mapped = True
                        break
                    self._extents.append(ext)
                    self._extent_start_blocks.append(last_start_block)
                    last_start_block += ext.block_count
            else:
                self._all_extents_mapped = True
        except Exception:
            # 如果查找失败，标记为所有 extents 已映射
            self._all_extents_mapped = True
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pass  # 不关闭底层流
    
    def __repr__(self) -> str:
        return (f"ForkFilter(cnid={self._cnid}, "
                f"type={'DATA' if self._fork_type == ForkType.DATA else 'RESOURCE'}, "
                f"length={self._fork_length}, "
                f"extents={len(self._extents)})")
