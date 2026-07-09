"""
DMG/UDIF 镜像支持

支持读取 Apple Disk Image (.dmg) 格式。
主要支持 UDIF (Universal Disk Image Format) 格式。

DMG 文件结构：
1. 数据块（文件开头）
2. Trailer（文件末尾，包含 koly 块）
3. koly 块指向 plist
4. plist 包含块映射表 (blkx)

参考：
- https://opensource.apple.com/source/hfs/hfs-366.1.1/tools/udif.h
- https://newosxbook.com/files/DMG.pdf
"""

import struct
import plistlib
from dataclasses import dataclass, field
from typing import List, Optional, BinaryIO, Dict, Any
from enum import IntEnum


class DMGError(Exception):
    """DMG 相关错误"""
    pass


# =============================================================================
# DMG 常量
# =============================================================================

# koly 块签名
KOLY_SIGNATURE = b'koly'

# koly 块大小
KOLY_SIZE = 512

# 块类型
class DMGBlockType(IntEnum):
    """DMG 块类型"""
    ZERO = 0x00000000        # 零填充
    RAW = 0x00000001         # 原始数据
    IGNORE = 0x00000002      # 忽略
    ADC_COMPRESSED = 0x80000004  # ADC 压缩
    ZLIB_COMPRESSED = 0x80000005  # zlib 压缩
    BZIP2_COMPRESSED = 0x80000006  # bzip2 压缩
    LZFSE_COMPRESSED = 0x80000007  # LZFSE 压缩
    COMMENT = 0x7FFFFFFE     # 注释
    TERMINATOR = 0xFFFFFFFF  # 终止符


# =============================================================================
# koly 块结构
# =============================================================================

@dataclass
class KolyBlock:
    """
    koly 块 (UDIF Trailer)
    
    位于 DMG 文件末尾，512 字节。
    
    Attributes:
        signature: 签名 ('koly')
        version: 版本
        header_size: 头部大小
        flags: 标志
        running_data_fork_offset: 运行数据分支偏移
        data_fork_offset: 数据分支偏移
        data_fork_length: 数据分支长度
        rsrc_fork_offset: 资源分支偏移
        rsrc_fork_length: 资源分支长度
        segment_number: 段号
        segment_count: 段数
        segment_id: 段 UUID
        data_checksum_type: 数据校验和类型
        data_checksum_size: 数据校验和大小
        data_checksum: 数据校验和
        xmldata_offset: XML 数据偏移
        xmldata_length: XML 数据长度
        checksum_type: 校验和类型
        checksum_size: 校验和大小
        checksum: 校验和
        plist_length: plist 长度
    """
    signature: bytes
    version: int
    header_size: int
    flags: int
    running_data_fork_offset: int
    data_fork_offset: int
    data_fork_length: int
    rsrc_fork_offset: int
    rsrc_fork_length: int
    segment_number: int
    segment_count: int
    segment_id: bytes
    data_checksum_type: int
    data_checksum_size: int
    data_checksum: bytes
    xmldata_offset: int
    xmldata_length: int
    checksum_type: int
    checksum_size: int
    checksum: bytes
    plist_length: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'KolyBlock':
        """从字节序列解析"""
        if len(data) < KOLY_SIZE:
            raise DMGError(f"koly 块数据不足: 需要 {KOLY_SIZE} 字节")
        
        # 解析固定字段
        signature = data[0:4]
        if signature != KOLY_SIGNATURE:
            raise DMGError(f"无效的 koly 签名: {signature}")
        
        version = struct.unpack_from('>I', data, 4)[0]
        header_size = struct.unpack_from('>I', data, 8)[0]
        flags = struct.unpack_from('>I', data, 12)[0]
        
        running_data_fork_offset = struct.unpack_from('>q', data, 16)[0]
        data_fork_offset = struct.unpack_from('>q', data, 24)[0]
        data_fork_length = struct.unpack_from('>q', data, 32)[0]
        rsrc_fork_offset = struct.unpack_from('>q', data, 40)[0]
        rsrc_fork_length = struct.unpack_from('>q', data, 48)[0]
        
        segment_number = struct.unpack_from('>I', data, 56)[0]
        segment_count = struct.unpack_from('>I', data, 60)[0]
        segment_id = data[64:80]  # 16 bytes UUID
        
        data_checksum_type = struct.unpack_from('>I', data, 80)[0]
        data_checksum_size = struct.unpack_from('>I', data, 84)[0]
        data_checksum = data[88:120]  # 32 bytes
        
        xmldata_offset = struct.unpack_from('>q', data, 120)[0]
        xmldata_length = struct.unpack_from('>q', data, 128)[0]
        
        checksum_type = struct.unpack_from('>I', data, 200)[0]
        checksum_size = struct.unpack_from('>I', data, 204)[0]
        checksum = data[208:240]  # 32 bytes
        
        plist_length = struct.unpack_from('>I', data, 244)[0]
        
        return cls(
            signature=signature,
            version=version,
            header_size=header_size,
            flags=flags,
            running_data_fork_offset=running_data_fork_offset,
            data_fork_offset=data_fork_offset,
            data_fork_length=data_fork_length,
            rsrc_fork_offset=rsrc_fork_offset,
            rsrc_fork_length=rsrc_fork_length,
            segment_number=segment_number,
            segment_count=segment_count,
            segment_id=segment_id,
            data_checksum_type=data_checksum_type,
            data_checksum_size=data_checksum_size,
            data_checksum=data_checksum,
            xmldata_offset=xmldata_offset,
            xmldata_length=xmldata_length,
            checksum_type=checksum_type,
            checksum_size=checksum_size,
            checksum=checksum,
            plist_length=plist_length
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == KOLY_SIGNATURE


# =============================================================================
# 块映射表
# =============================================================================

@dataclass
class DMGBlockEntry:
    """
    DMG 块映射表条目
    
    Attributes:
        entry_type: 块类型
        comment: 注释
        sector_number: 扇区号
        sector_count: 扇区数
        data_offset: 数据偏移
        buffers_needed: 缓冲区需求
        block_descriptor: 块描述符
    """
    entry_type: int
    comment: int
    sector_number: int
    sector_count: int
    data_offset: int
    buffers_needed: int
    block_descriptor: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'DMGBlockEntry':
        """从字节序列解析"""
        entry_type = struct.unpack_from('>I', data, offset)[0]
        comment = struct.unpack_from('>I', data, offset + 4)[0]
        sector_number = struct.unpack_from('>q', data, offset + 8)[0]
        sector_count = struct.unpack_from('>q', data, offset + 16)[0]
        data_offset = struct.unpack_from('>q', data, offset + 24)[0]
        buffers_needed = struct.unpack_from('>I', data, offset + 32)[0]
        block_descriptor = struct.unpack_from('>I', data, offset + 36)[0]
        
        return cls(
            entry_type=entry_type,
            comment=comment,
            sector_number=sector_number,
            sector_count=sector_count,
            data_offset=data_offset,
            buffers_needed=buffers_needed,
            block_descriptor=block_descriptor
        )
    
    @property
    def is_raw(self) -> bool:
        """是否为原始数据块"""
        return self.entry_type == DMGBlockType.RAW
    
    @property
    def is_compressed(self) -> bool:
        """是否为压缩块"""
        return self.entry_type in (
            DMGBlockType.ADC_COMPRESSED,
            DMGBlockType.ZLIB_COMPRESSED,
            DMGBlockType.BZIP2_COMPRESSED,
            DMGBlockType.LZFSE_COMPRESSED
        )
    
    @property
    def is_zero(self) -> bool:
        """是否为零填充块"""
        return self.entry_type == DMGBlockType.ZERO


@dataclass
class DMGBlockMap:
    """
    DMG 块映射表
    
    Attributes:
        signature: 签名
        version: 版本
        sector_number: 扇区号
        sector_count: 扇区数
        data_offset: 数据偏移
        buffers_needed: 缓冲区需求
        block_descriptors_count: 块描述符数量
        block_entries: 块条目列表
    """
    signature: int
    version: int
    sector_number: int
    sector_count: int
    data_offset: int
    buffers_needed: int
    block_descriptors_count: int
    block_entries: List[DMGBlockEntry] = field(default_factory=list)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DMGBlockMap':
        """从字节序列解析"""
        signature = struct.unpack_from('>I', data, 0)[0]
        version = struct.unpack_from('>I', data, 4)[0]
        sector_number = struct.unpack_from('>q', data, 8)[0]
        sector_count = struct.unpack_from('>q', data, 16)[0]
        data_offset = struct.unpack_from('>q', data, 24)[0]
        buffers_needed = struct.unpack_from('>I', data, 32)[0]
        block_descriptors_count = struct.unpack_from('>I', data, 36)[0]
        
        # 解析块条目
        block_entries = []
        offset = 40
        for i in range(block_descriptors_count):
            if offset + 40 > len(data):
                break
            entry = DMGBlockEntry.from_bytes(data, offset)
            block_entries.append(entry)
            offset += 40
        
        return cls(
            signature=signature,
            version=version,
            sector_number=sector_number,
            sector_count=sector_count,
            data_offset=data_offset,
            buffers_needed=buffers_needed,
            block_descriptors_count=block_descriptors_count,
            block_entries=block_entries
        )


# =============================================================================
# DMG 分区
# =============================================================================

@dataclass
class DMGPartition:
    """
    DMG 分区
    
    Attributes:
        name: 分区名称
        block_map: 块映射表
    """
    name: str
    block_map: DMGBlockMap
    
    @property
    def sector_count(self) -> int:
        """扇区数"""
        return self.block_map.sector_count
    
    @property
    def size_bytes(self) -> int:
        """大小（字节）"""
        return self.block_map.sector_count * 512


# =============================================================================
# DMG 镜像读取器
# =============================================================================

class DMGImage:
    """
    DMG 镜像读取器
    
    用于读取 Apple Disk Image (.dmg) 文件。
    
    Usage:
        with DMGImage("/path/to/image.dmg") as dmg:
            # 获取分区列表
            partitions = dmg.partitions
            
            # 读取数据
            data = dmg.read_sectors(0, 100)
    """
    
    def __init__(self, path: str):
        """
        初始化 DMG 镜像读取器
        
        Args:
            path: DMG 文件路径
        """
        self._path = path
        self._file: Optional[BinaryIO] = None
        self._koly: Optional[KolyBlock] = None
        self._partitions: List[DMGPartition] = []
        self._plist_data: Optional[Dict[str, Any]] = None
        
        # 打开文件
        self._file = open(path, 'rb')
        
        # 解析 DMG
        self._parse()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def close(self):
        """关闭文件"""
        if self._file:
            self._file.close()
            self._file = None
    
    def _parse(self):
        """解析 DMG 文件"""
        # 读取 koly 块（文件末尾）
        self._file.seek(-KOLY_SIZE, 2)
        koly_data = self._file.read(KOLY_SIZE)
        self._koly = KolyBlock.from_bytes(koly_data)
        
        if not self._koly.is_valid:
            raise DMGError("无效的 DMG 文件")
        
        # 读取 plist 数据
        if self._koly.xmldata_length > 0:
            self._file.seek(self._koly.xmldata_offset)
            plist_data = self._file.read(self._koly.xmldata_length)
            self._plist_data = plistlib.loads(plist_data)
            
            # 解析分区信息
            self._parse_partitions()
    
    def _parse_partitions(self):
        """解析分区信息"""
        if self._plist_data is None:
            return
        
        # 查找资源分支信息
        resource_fork = self._plist_data.get('resource-fork', {})
        blkx_list = resource_fork.get('blkx', [])
        
        for blkx in blkx_list:
            name = blkx.get('Name', 'Unknown')
            data = blkx.get('Data', b'')
            
            if data:
                block_map = DMGBlockMap.from_bytes(data)
                partition = DMGPartition(name=name, block_map=block_map)
                self._partitions.append(partition)
    
    @property
    def koly(self) -> Optional[KolyBlock]:
        """获取 koly 块"""
        return self._koly
    
    @property
    def partitions(self) -> List[DMGPartition]:
        """获取分区列表"""
        return self._partitions.copy()
    
    @property
    def partition_count(self) -> int:
        """获取分区数量"""
        return len(self._partitions)
    
    @property
    def file_size(self) -> int:
        """获取文件大小"""
        if self._file:
            self._file.seek(0, 2)
            return self._file.tell()
        return 0
    
    def get_partition_by_name(self, name: str) -> Optional[DMGPartition]:
        """根据名称获取分区"""
        for partition in self._partitions:
            if partition.name == name:
                return partition
        return None
    
    def read_partition_data(self, partition: DMGPartition) -> bytes:
        """
        读取分区数据
        
        Args:
            partition: 分区对象
        
        Returns:
            分区数据
        """
        result = bytearray()
        
        for entry in partition.block_map.block_entries:
            if entry.is_raw:
                # 原始数据块
                self._file.seek(entry.data_offset)
                data = self._file.read(entry.sector_count * 512)
                result.extend(data)
            elif entry.is_zero:
                # 零填充块
                result.extend(b'\x00' * (entry.sector_count * 512))
            elif entry.is_compressed:
                # 压缩块 - 需要解压缩
                compressed_data = self._read_compressed_block(entry)
                result.extend(compressed_data)
            else:
                # 未知类型，填充零
                result.extend(b'\x00' * (entry.sector_count * 512))
        
        return bytes(result)
    
    def _read_compressed_block(self, entry: DMGBlockEntry) -> bytes:
        """
        读取压缩块
        
        Args:
            entry: 块条目
        
        Returns:
            解压后的数据
        """
        import zlib
        
        # 读取压缩数据
        self._file.seek(entry.data_offset)
        
        # 压缩块的前 4 字节是未压缩大小
        uncompressed_size_data = self._file.read(4)
        if len(uncompressed_size_data) < 4:
            return b'\x00' * (entry.sector_count * 512)
        
        uncompressed_size = struct.unpack('>I', uncompressed_size_data)[0]
        
        # 读取压缩数据
        compressed_size = entry.sector_count * 512 - 4
        compressed_data = self._file.read(compressed_size)
        
        # 根据压缩类型解压
        if entry.entry_type == DMGBlockType.ZLIB_COMPRESSED:
            try:
                return zlib.decompress(compressed_data)
            except:
                return b'\x00' * uncompressed_size
        else:
            # 其他压缩类型暂不支持
            return b'\x00' * uncompressed_size
    
    def read_sectors(self, start_sector: int, count: int, 
                     partition_index: int = 0) -> bytes:
        """
        读取扇区数据
        
        Args:
            start_sector: 起始扇区
            count: 扇区数
            partition_index: 分区索引
        
        Returns:
            扇区数据
        """
        if partition_index >= len(self._partitions):
            raise DMGError(f"分区索引超出范围: {partition_index}")
        
        partition = self._partitions[partition_index]
        
        # 检查范围
        if start_sector + count > partition.sector_count:
            raise DMGError(f"扇区范围超出分区大小")
        
        result = bytearray()
        current_sector = 0
        
        for entry in partition.block_map.block_entries:
            # 检查是否是我们需要的块
            if entry.sector_number + entry.sector_count <= start_sector:
                current_sector = entry.sector_number + entry.sector_count
                continue
            
            if entry.sector_number >= start_sector + count:
                break
            
            # 计算需要读取的范围
            block_start = max(start_sector, entry.sector_number)
            block_end = min(start_sector + count, 
                          entry.sector_number + entry.sector_count)
            block_count = block_end - block_start
            
            if block_count <= 0:
                continue
            
            # 读取数据
            if entry.is_raw:
                offset = entry.data_offset + (block_start - entry.sector_number) * 512
                self._file.seek(offset)
                data = self._file.read(block_count * 512)
                result.extend(data)
            elif entry.is_zero:
                result.extend(b'\x00' * (block_count * 512))
            else:
                # 压缩块，需要读取整个块
                full_data = self._read_compressed_block(entry)
                offset = (block_start - entry.sector_number) * 512
                result.extend(full_data[offset:offset + block_count * 512])
        
        return bytes(result)
    
    def __str__(self) -> str:
        """字符串表示"""
        lines = [
            f"DMG Image: {self._path}",
            f"  File Size: {self.file_size:,} bytes",
            f"  Partitions: {self.partition_count}",
        ]
        
        for i, partition in enumerate(self._partitions):
            lines.append(f"  Partition {i}: {partition.name}")
            lines.append(f"    Sectors: {partition.sector_count:,}")
            lines.append(f"    Size: {partition.size_bytes:,} bytes")
        
        return "\n".join(lines)


def open_dmg(path: str) -> DMGImage:
    """
    打开 DMG 镜像的便捷函数
    
    Args:
        path: DMG 文件路径
    
    Returns:
        DMGImage 对象
    """
    return DMGImage(path)
