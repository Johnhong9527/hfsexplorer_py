"""
APFS 空间管理模块

提供完整的空间管理功能，包括：
- 位图管理
- 块分配/释放
- 空间统计
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, BinaryIO
from enum import IntEnum


# =============================================================================
# 空间管理常量
# =============================================================================

# 块状态
class BlockState(IntEnum):
    """块状态"""
    FREE = 0      # 空闲
    ALLOCATED = 1 # 已分配
    RESERVED = 2  # 已保留


# =============================================================================
# 空间管理数据结构
# =============================================================================

@dataclass
class SpaceManagerHeader:
    """空间管理器头部"""
    block_size: int  # 块大小
    total_blocks: int  # 总块数
    free_blocks: int  # 空闲块数
    bitmap_blocks: int  # 位图块数
    first_bitmap_block: int  # 第一个位图块
    
    SIZE = 32
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<I', self.block_size)
        result += struct.pack('<Q', self.total_blocks)
        result += struct.pack('<Q', self.free_blocks)
        result += struct.pack('<I', self.bitmap_blocks)
        result += struct.pack('<Q', self.first_bitmap_block)
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'SpaceManagerHeader':
        """反序列化"""
        block_size = struct.unpack_from('<I', data, offset)[0]
        total_blocks = struct.unpack_from('<Q', data, offset + 4)[0]
        free_blocks = struct.unpack_from('<Q', data, offset + 12)[0]
        bitmap_blocks = struct.unpack_from('<I', data, offset + 20)[0]
        first_bitmap_block = struct.unpack_from('<Q', data, offset + 24)[0]
        
        return cls(
            block_size=block_size,
            total_blocks=total_blocks,
            free_blocks=free_blocks,
            bitmap_blocks=bitmap_blocks,
            first_bitmap_block=first_bitmap_block
        )


@dataclass
class BitmapBlock:
    """位图块"""
    block_num: int  # 块号
    data: bytearray  # 位图数据
    
    def is_allocated(self, block_offset: int) -> bool:
        """
        检查块是否已分配
        
        Args:
            block_offset: 块偏移
            
        Returns:
            是否已分配
        """
        byte_index = block_offset // 8
        bit_index = block_offset % 8
        
        if byte_index >= len(self.data):
            return False
            
        return bool(self.data[byte_index] & (1 << bit_index))
        
    def allocate(self, block_offset: int) -> None:
        """
        分配块
        
        Args:
            block_offset: 块偏移
        """
        byte_index = block_offset // 8
        bit_index = block_offset % 8
        
        if byte_index < len(self.data):
            self.data[byte_index] |= (1 << bit_index)
            
    def free(self, block_offset: int) -> None:
        """
        释放块
        
        Args:
            block_offset: 块偏移
        """
        byte_index = block_offset // 8
        bit_index = block_offset % 8
        
        if byte_index < len(self.data):
            self.data[byte_index] &= ~(1 << bit_index)
            
    def find_free_blocks(self, count: int, start: int = 0) -> List[int]:
        """
        查找空闲块
        
        Args:
            count: 需要的块数
            start: 起始偏移
            
        Returns:
            空闲块偏移列表
        """
        free_blocks = []
        for offset in range(start, len(self.data) * 8):
            if not self.is_allocated(offset):
                free_blocks.append(offset)
                if len(free_blocks) >= count:
                    break
        return free_blocks


# =============================================================================
# 空间管理器
# =============================================================================

class SpaceManager:
    """
    空间管理器
    
    负责管理块的分配和释放。
    """
    
    def __init__(self, file_path: str, block_size: int = 4096):
        """
        初始化空间管理器
        
        Args:
            file_path: 文件路径
            block_size: 块大小
        """
        self.file_path = file_path
        self.block_size = block_size
        self._file: Optional[BinaryIO] = None
        self._header: Optional[SpaceManagerHeader] = None
        self._bitmaps: Dict[int, BitmapBlock] = {}
        self._first_data_block = 0
        
    def open(self) -> None:
        """打开文件"""
        self._file = open(self.file_path, 'r+b')
        
    def close(self) -> None:
        """关闭文件"""
        if self._file:
            self._file.close()
            self._file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def initialize(self, total_blocks: int) -> None:
        """
        初始化空间管理器
        
        Args:
            total_blocks: 总块数
        """
        # 计算需要的位图块数
        # 每个位图块可以管理 block_size * 8 个块
        blocks_per_bitmap = self.block_size * 8
        bitmap_blocks = (total_blocks + blocks_per_bitmap - 1) // blocks_per_bitmap
        
        # 创建头部
        self._header = SpaceManagerHeader(
            block_size=self.block_size,
            total_blocks=total_blocks,
            free_blocks=total_blocks,
            bitmap_blocks=bitmap_blocks,
            first_bitmap_block=1  # 从块 1 开始
        )
        
        # 创建位图块
        for i in range(bitmap_blocks):
            bitmap = BitmapBlock(
                block_num=1 + i,
                data=bytearray(self.block_size)
            )
            self._bitmaps[i] = bitmap
            
        # 保留前几个块（头部、位图等）
        self._first_data_block = 1 + bitmap_blocks
        for i in range(self._first_data_block):
            self._mark_allocated(i)
            
    def _read_bitmap(self, bitmap_index: int) -> BitmapBlock:
        """
        读取位图块
        
        Args:
            bitmap_index: 位图索引
            
        Returns:
            位图块
        """
        if bitmap_index in self._bitmaps:
            return self._bitmaps[bitmap_index]
            
        if not self._file or not self._header:
            raise RuntimeError("空间管理器未初始化")
            
        # 从文件读取
        block_num = self._header.first_bitmap_block + bitmap_index
        offset = block_num * self.block_size
        
        self._file.seek(offset)
        data = self._file.read(self.block_size)
        
        bitmap = BitmapBlock(
            block_num=block_num,
            data=bytearray(data)
        )
        self._bitmaps[bitmap_index] = bitmap
        
        return bitmap
        
    def _write_bitmap(self, bitmap_index: int) -> None:
        """
        写入位图块
        
        Args:
            bitmap_index: 位图索引
        """
        if bitmap_index not in self._bitmaps:
            return
            
        if not self._file or not self._header:
            return
            
        bitmap = self._bitmaps[bitmap_index]
        offset = bitmap.block_num * self.block_size
        
        self._file.seek(offset)
        self._file.write(bitmap.data)
        
    def _get_bitmap_index(self, block_num: int) -> Tuple[int, int]:
        """
        获取位图索引和块偏移
        
        Args:
            block_num: 块号
            
        Returns:
            (位图索引, 块偏移)
        """
        blocks_per_bitmap = self.block_size * 8
        bitmap_index = block_num // blocks_per_bitmap
        block_offset = block_num % blocks_per_bitmap
        return bitmap_index, block_offset
        
    def _mark_allocated(self, block_num: int) -> None:
        """
        标记块为已分配
        
        Args:
            block_num: 块号
        """
        bitmap_index, block_offset = self._get_bitmap_index(block_num)
        bitmap = self._read_bitmap(bitmap_index)
        bitmap.allocate(block_offset)
        
    def _mark_free(self, block_num: int) -> None:
        """
        标记块为空闲
        
        Args:
            block_num: 块号
        """
        bitmap_index, block_offset = self._get_bitmap_index(block_num)
        bitmap = self._read_bitmap(bitmap_index)
        bitmap.free(block_offset)
        
    def allocate_block(self) -> Optional[int]:
        """
        分配一个块
        
        Returns:
            块号，如果没有空闲块返回 None
        """
        if not self._header:
            raise RuntimeError("空间管理器未初始化")
            
        if self._header.free_blocks == 0:
            return None
            
        # 搜索空闲块
        for bitmap_index in range(self._header.bitmap_blocks):
            bitmap = self._read_bitmap(bitmap_index)
            
            # 计算起始偏移
            blocks_per_bitmap = self.block_size * 8
            start_offset = 0
            if bitmap_index == 0:
                start_offset = self._first_data_block
                
            # 查找空闲块
            free_blocks = bitmap.find_free_blocks(1, start_offset)
            
            if free_blocks:
                block_offset = free_blocks[0]
                block_num = bitmap_index * blocks_per_bitmap + block_offset
                
                # 标记为已分配
                bitmap.allocate(block_offset)
                self._write_bitmap(bitmap_index)
                
                # 更新头部
                self._header.free_blocks -= 1
                
                return block_num
                
        return None
        
    def allocate_blocks(self, count: int) -> List[int]:
        """
        分配多个块
        
        Args:
            count: 需要的块数
            
        Returns:
            块号列表
        """
        if not self._header:
            raise RuntimeError("空间管理器未初始化")
            
        if self._header.free_blocks < count:
            return []
            
        allocated = []
        
        for _ in range(count):
            block_num = self.allocate_block()
            if block_num is None:
                # 回滚
                for block in allocated:
                    self.free_block(block)
                return []
            allocated.append(block_num)
            
        return allocated
        
    def free_block(self, block_num: int) -> bool:
        """
        释放块
        
        Args:
            block_num: 块号
            
        Returns:
            是否成功
        """
        if not self._header:
            raise RuntimeError("空间管理器未初始化")
            
        if block_num >= self._header.total_blocks:
            return False
            
        # 标记为空闲
        self._mark_free(block_num)
        
        # 更新头部
        self._header.free_blocks += 1
        
        return True
        
    def free_blocks(self, block_nums: List[int]) -> int:
        """
        释放多个块
        
        Args:
            block_nums: 块号列表
            
        Returns:
            成功释放的块数
        """
        count = 0
        for block_num in block_nums:
            if self.free_block(block_num):
                count += 1
        return count
        
    def is_allocated(self, block_num: int) -> bool:
        """
        检查块是否已分配
        
        Args:
            block_num: 块号
            
        Returns:
            是否已分配
        """
        if not self._header:
            return False
            
        if block_num >= self._header.total_blocks:
            return False
            
        bitmap_index, block_offset = self._get_bitmap_index(block_num)
        bitmap = self._read_bitmap(bitmap_index)
        
        return bitmap.is_allocated(block_offset)
        
    def get_free_blocks(self) -> int:
        """
        获取空闲块数
        
        Returns:
            空闲块数
        """
        if not self._header:
            return 0
        return self._header.free_blocks
        
    def get_total_blocks(self) -> int:
        """
        获取总块数
        
        Returns:
            总块数
        """
        if not self._header:
            return 0
        return self._header.total_blocks
        
    def flush(self) -> None:
        """刷新到文件"""
        if not self._file:
            return
            
        # 写入头部
        if self._header:
            header_data = self._header.to_bytes()
            self._file.seek(0)
            self._file.write(header_data)
            
        # 写入所有位图块
        for bitmap_index in self._bitmaps:
            self._write_bitmap(bitmap_index)
            
        self._file.flush()
        
    def get_info(self) -> Dict[str, int]:
        """
        获取信息
        
        Returns:
            信息字典
        """
        if not self._header:
            return {}
            
        return {
            'block_size': self._header.block_size,
            'total_blocks': self._header.total_blocks,
            'free_blocks': self._header.free_blocks,
            'allocated_blocks': self._header.total_blocks - self._header.free_blocks,
            'bitmap_blocks': self._header.bitmap_blocks,
        }


# =============================================================================
# 便捷函数
# =============================================================================

def create_space_manager(file_path: str, total_blocks: int,
                         block_size: int = 4096) -> SpaceManager:
    """
    创建空间管理器
    
    Args:
        file_path: 文件路径
        total_blocks: 总块数
        block_size: 块大小
        
    Returns:
        空间管理器
    """
    manager = SpaceManager(file_path, block_size)
    manager.open()
    manager.initialize(total_blocks)
    return manager


def open_space_manager(file_path: str, block_size: int = 4096) -> SpaceManager:
    """
    打开空间管理器
    
    Args:
        file_path: 文件路径
        block_size: 块大小
        
    Returns:
        空间管理器
    """
    manager = SpaceManager(file_path, block_size)
    manager.open()
    return manager
