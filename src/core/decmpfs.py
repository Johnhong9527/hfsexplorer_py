"""
DecmpFS (Decompress File System) 支持

DecmpFS 是 Apple 用于文件压缩的技术。
它允许文件系统透明地压缩和解压缩文件。

压缩类型：
- ZLIB (0x80000003)
- LZVN (0x80000004)
- LZFSE (0x80000005)
"""

import struct
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import IntEnum
import zlib


class DecmpfsError(Exception):
    """Decmpfs 相关错误"""
    pass


class DecmpfsCompressionType(IntEnum):
    """Decmpfs 压缩类型"""
    UNCOMPRESSED = 0x00000000      # 未压缩
    ZLIB = 0x80000003              # zlib 压缩
    LZVN = 0x80000004              # LZVN 压缩
    LZFSE = 0x80000005             # LZFSE 压缩
    INLINE = 0x80000006            # 内联数据


# Decmpfs 魔数
DECMPFS_MAGIC = b'cmpf'

# Decmpfs 头部大小
DECMPFS_HEADER_SIZE = 16


@dataclass
class DecmpfsHeader:
    """
    Decmpfs 头部
    
    Attributes:
        magic: 魔数 'cmpf'
        compression_type: 压缩类型
        uncompressed_size: 未压缩大小
        compressed_size: 压缩大小（不含头部）
    """
    magic: bytes
    compression_type: int
    uncompressed_size: int
    compressed_size: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DecmpfsHeader':
        """从字节序列解析"""
        if len(data) < DECMPFS_HEADER_SIZE:
            raise DecmpfsError("头部数据太短")
        
        magic = data[0:4]
        if magic != DECMPFS_MAGIC:
            raise DecmpfsError(f"无效的魔数: {magic}")
        
        compression_type = struct.unpack_from('>I', data, 4)[0]
        uncompressed_size = struct.unpack_from('>I', data, 8)[0]
        compressed_size = struct.unpack_from('>I', data, 12)[0]
        
        return cls(
            magic=magic,
            compression_type=compression_type,
            uncompressed_size=uncompressed_size,
            compressed_size=compressed_size
        )
    
    @property
    def is_compressed(self) -> bool:
        """是否压缩"""
        return self.compression_type != DecmpfsCompressionType.UNCOMPRESSED
    
    @property
    def is_inline(self) -> bool:
        """是否是内联数据"""
        return self.compression_type == DecmpfsCompressionType.INLINE


def decompress_decmpfs(data: bytes) -> Tuple[bytes, int]:
    """
    解压 Decmpfs 数据
    
    Args:
        data: 包含 Decmpfs 头部的数据
    
    Returns:
        (解压后的数据, 消耗的字节数)
    """
    if len(data) < DECMPFS_HEADER_SIZE:
        raise DecmpfsError("数据太短")
    
    header = DecmpfsHeader.from_bytes(data)
    
    if not header.is_compressed:
        # 未压缩数据
        return data[DECMPFS_HEADER_SIZE:], DECMPFS_HEADER_SIZE
    
    if header.is_inline:
        # 内联数据
        return data[DECMPFS_HEADER_SIZE:DECMPFS_HEADER_SIZE + header.uncompressed_size], DECMPFS_HEADER_SIZE + header.uncompressed_size
    
    # 压缩数据
    compressed_data = data[DECMPFS_HEADER_SIZE:DECMPFS_HEADER_SIZE + header.compressed_size]
    
    if header.compression_type == DecmpfsCompressionType.ZLIB:
        # zlib 解压
        try:
            decompressed = zlib.decompress(compressed_data)
        except zlib.error as e:
            raise DecmpfsError(f"zlib 解压失败: {e}")
    elif header.compression_type == DecmpfsCompressionType.LZVN:
        # LZVN 解压（需要实现）
        raise DecmpfsError("LZVN 解压暂不支持")
    elif header.compression_type == DecmpfsCompressionType.LZFSE:
        # LZFSE 解压（需要实现）
        raise DecmpfsError("LZFSE 解压暂不支持")
    else:
        raise DecmpfsError(f"未知的压缩类型: 0x{header.compression_type:08X}")
    
    return decompressed, DECMPFS_HEADER_SIZE + header.compressed_size


def is_decmpfs_file(data: bytes) -> bool:
    """
    检查是否是 Decmpfs 文件
    
    Args:
        data: 文件数据
    
    Returns:
        是否是 Decmpfs 文件
    """
    if len(data) < 4:
        return False
    
    return data[0:4] == DECMPFS_MAGIC


def get_decmpfs_info(data: bytes) -> dict:
    """
    获取 Decmpfs 信息
    
    Args:
        data: 文件数据
    
    Returns:
        信息字典
    """
    if not is_decmpfs_file(data):
        return {}
    
    header = DecmpfsHeader.from_bytes(data)
    
    compression_names = {
        DecmpfsCompressionType.UNCOMPRESSED: "未压缩",
        DecmpfsCompressionType.ZLIB: "ZLIB",
        DecmpfsCompressionType.LZVN: "LZVN",
        DecmpfsCompressionType.LZFSE: "LZFSE",
        DecmpfsCompressionType.INLINE: "内联",
    }
    
    return {
        'compression_type': compression_names.get(header.compression_type, f"未知 (0x{header.compression_type:08X})"),
        'uncompressed_size': header.uncompressed_size,
        'compressed_size': header.compressed_size,
        'is_compressed': header.is_compressed,
    }
