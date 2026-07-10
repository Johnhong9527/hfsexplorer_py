"""
稀疏镜像支持

支持 Apple Sparse Image (.sparseimage) 格式。
稀疏镜像是一种动态增长的磁盘镜像格式。
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, BinaryIO
from enum import IntEnum


class SparseImageError(Exception):
    """稀疏镜像相关错误"""
    pass


# 稀疏镜像签名
SPARSE_SIGNATURE = b'sprs'

# 扇区大小
SECTOR_SIZE = 512


class SparseBlockType(IntEnum):
    """稀疏块类型"""
    FREE = 0        # 空闲块
    USED = 1        # 已使用块


@dataclass
class SparseHeader:
    """
    稀疏镜像头部
    
    Attributes:
        signature: 签名
        version: 版本
        num_blocks: 块数量
        block_size: 块大小（字节）
        bitmap_offset: 位图偏移
        data_offset: 数据偏移
    """
    signature: bytes
    version: int
    num_blocks: int
    block_size: int
    bitmap_offset: int
    data_offset: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SparseHeader':
        """从字节序列解析"""
        if len(data) < 56:
            raise SparseImageError("头部数据太短")
        
        signature = data[0:4]
        if signature != SPARSE_SIGNATURE:
            raise SparseImageError(f"无效的签名: {signature}")
        
        version = struct.unpack_from('>I', data, 4)[0]
        num_blocks = struct.unpack_from('>Q', data, 8)[0]
        block_size = struct.unpack_from('>I', data, 16)[0]
        bitmap_offset = struct.unpack_from('>Q', data, 20)[0]
        data_offset = struct.unpack_from('>Q', data, 28)[0]
        
        return cls(
            signature=signature,
            version=version,
            num_blocks=num_blocks,
            block_size=block_size,
            bitmap_offset=bitmap_offset,
            data_offset=data_offset
        )


@dataclass
class SparseImage:
    """
    稀疏镜像
    
    Attributes:
        header: 头部信息
        bitmap: 分配位图
        stream: 文件流
    """
    header: SparseHeader
    bitmap: bytearray
    stream: BinaryIO
    
    @classmethod
    def open(cls, path: str) -> 'SparseImage':
        """
        打开稀疏镜像
        
        Args:
            path: 文件路径
        
        Returns:
            SparseImage 对象
        """
        stream = open(path, 'rb')
        
        try:
            # 读取头部
            header_data = stream.read(56)
            header = SparseHeader.from_bytes(header_data)
            
            # 读取位图
            bitmap_size = (header.num_blocks + 7) // 8
            stream.seek(header.bitmap_offset)
            bitmap = bytearray(stream.read(bitmap_size))
            
            return cls(header=header, bitmap=bitmap, stream=stream)
        except Exception:
            stream.close()
            raise
    
    def close(self):
        """关闭文件"""
        self.stream.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def is_block_allocated(self, block_number: int) -> bool:
        """
        检查块是否已分配
        
        Args:
            block_number: 块号
        
        Returns:
            是否已分配
        """
        byte_index = block_number // 8
        bit_index = block_number % 8
        
        if byte_index >= len(self.bitmap):
            return False
        
        return bool(self.bitmap[byte_index] & (1 << (7 - bit_index)))
    
    def read_block(self, block_number: int) -> bytes:
        """
        读取块数据
        
        Args:
            block_number: 块号
        
        Returns:
            块数据
        """
        if block_number >= self.header.num_blocks:
            raise SparseImageError(f"块号超出范围: {block_number}")
        
        if not self.is_block_allocated(block_number):
            # 空闲块返回全零
            return b'\x00' * self.header.block_size
        
        # 计算块在文件中的偏移
        block_offset = self.header.data_offset + block_number * self.header.block_size
        
        self.stream.seek(block_offset)
        return self.stream.read(self.header.block_size)
    
    def read_sectors(self, start_sector: int, count: int) -> bytes:
        """
        读取扇区数据
        
        Args:
            start_sector: 起始扇区
            count: 扇区数
        
        Returns:
            扇区数据
        """
        sectors_per_block = self.header.block_size // SECTOR_SIZE
        
        result = bytearray()
        
        current_sector = start_sector
        remaining = count
        
        while remaining > 0:
            # 计算当前扇区所在的块
            block_number = current_sector // sectors_per_block
            sector_in_block = current_sector % sectors_per_block
            
            # 读取块
            block_data = self.read_block(block_number)
            
            # 计算要读取的扇区数
            sectors_to_read = min(remaining, sectors_per_block - sector_in_block)
            
            # 提取扇区数据
            start_offset = sector_in_block * SECTOR_SIZE
            end_offset = start_offset + sectors_to_read * SECTOR_SIZE
            result.extend(block_data[start_offset:end_offset])
            
            current_sector += sectors_to_read
            remaining -= sectors_to_read
        
        return bytes(result)
    
    @property
    def total_size(self) -> int:
        """总大小（字节）"""
        return self.header.num_blocks * self.header.block_size
    
    @property
    def allocated_blocks(self) -> int:
        """已分配的块数"""
        count = 0
        for i in range(self.header.num_blocks):
            if self.is_block_allocated(i):
                count += 1
        return count
    
    @property
    def allocated_size(self) -> int:
        """已分配的大小（字节）"""
        return self.allocated_blocks * self.header.block_size


def open_sparse_image(path: str) -> SparseImage:
    """
    打开稀疏镜像的便捷函数
    
    Args:
        path: 文件路径
    
    Returns:
        SparseImage 对象
    """
    return SparseImage.open(path)
