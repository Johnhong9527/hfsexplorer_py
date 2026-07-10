"""
HFS Classic 文件系统支持

HFS (Hierarchical File System) 是 Apple 在 1985 年推出的文件系统。
它是 HFS+ 的前身，现在已经被 HFS+ 取代。

HFS Classic 结构：
- 卷头 (512 字节，在第 2 扇区)
- B-tree (Catalog, Extents Overflow)
- 分配位图
- 数据区域
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta


class HFSError(Exception):
    """HFS 相关错误"""
    pass


# HFS 签名
HFS_SIGNATURE = 0x4244  # 'BD'

# HFS 日期偏移 (1904-01-01 到 1970-01-01)
HFS_EPOCH_OFFSET = 2082844800


@dataclass
class HFSVolumeHeader:
    """
    HFS 卷头
    
    位于第 2 扇区（偏移 1024 字节）。
    
    Attributes:
        signature: 签名 (0x4244)
        create_date: 创建日期
        modify_date: 修改日期
        backup_date: 备份日期
        file_count: 文件数量
        folder_count: 文件夹数量
        block_size: 块大小（字节）
        total_blocks: 总块数
        free_blocks: 空闲块数
        next_allocation: 下一个分配块
        catalog_clump_size: Catalog Clump 大小
        extents_clump_size: Extents Clump 大小
        next_catalog_id: 下一个 Catalog ID
        write_count: 写入计数
        bitmap_start: 位图起始块
        catalog_start: Catalog 起始块
        extents_start: Extents 起始块
    """
    signature: int
    create_date: int
    modify_date: int
    backup_date: int
    file_count: int
    folder_count: int
    block_size: int
    total_blocks: int
    free_blocks: int
    next_allocation: int
    catalog_clump_size: int
    extents_clump_size: int
    next_catalog_id: int
    write_count: int
    bitmap_start: int
    catalog_start: int
    extents_start: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSVolumeHeader':
        """从字节序列解析"""
        if len(data) < offset + 512:
            raise HFSError("数据太短")
        
        signature = struct.unpack_from('>H', data, offset)[0]
        if signature != HFS_SIGNATURE:
            raise HFSError(f"无效的签名: 0x{signature:04X}")
        
        # 解析卷头
        create_date = struct.unpack_from('>I', data, offset + 4)[0]
        modify_date = struct.unpack_from('>I', data, offset + 8)[0]
        backup_date = struct.unpack_from('>I', data, offset + 12)[0]
        
        file_count = struct.unpack_from('>H', data, offset + 22)[0]
        folder_count = struct.unpack_from('>H', data, offset + 24)[0]
        
        block_size = struct.unpack_from('>I', data, offset + 28)[0]
        total_blocks = struct.unpack_from('>I', data, offset + 32)[0]
        
        free_blocks = struct.unpack_from('>I', data, offset + 36)[0]
        next_allocation = struct.unpack_from('>I', data, offset + 40)[0]
        
        catalog_clump_size = struct.unpack_from('>I', data, offset + 44)[0]
        extents_clump_size = struct.unpack_from('>I', data, offset + 48)[0]
        
        next_catalog_id = struct.unpack_from('>I', data, offset + 56)[0]
        write_count = struct.unpack_from('>I', data, offset + 60)[0]
        
        bitmap_start = struct.unpack_from('>H', data, offset + 64)[0]
        catalog_start = struct.unpack_from('>H', data, offset + 66)[0]
        extents_start = struct.unpack_from('>H', data, offset + 68)[0]
        
        return cls(
            signature=signature,
            create_date=create_date,
            modify_date=modify_date,
            backup_date=backup_date,
            file_count=file_count,
            folder_count=folder_count,
            block_size=block_size,
            total_blocks=total_blocks,
            free_blocks=free_blocks,
            next_allocation=next_allocation,
            catalog_clump_size=catalog_clump_size,
            extents_clump_size=extents_clump_size,
            next_catalog_id=next_catalog_id,
            write_count=write_count,
            bitmap_start=bitmap_start,
            catalog_start=catalog_start,
            extents_start=extents_start
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == HFS_SIGNATURE
    
    @property
    def volume_size(self) -> int:
        """卷大小（字节）"""
        return self.block_size * self.total_blocks
    
    @property
    def free_space(self) -> int:
        """空闲空间（字节）"""
        return self.block_size * self.free_blocks
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"HFS Volume Header:\n"
            f"  Signature: 0x{self.signature:04X}\n"
            f"  Block Size: {self.block_size:,}\n"
            f"  Total Blocks: {self.total_blocks:,}\n"
            f"  Free Blocks: {self.free_blocks:,}\n"
            f"  Volume Size: {self.volume_size:,} bytes\n"
            f"  File Count: {self.file_count:,}\n"
            f"  Folder Count: {self.folder_count:,}"
        )


def parse_hfs_header(stream, offset: int = 1024) -> HFSVolumeHeader:
    """
    解析 HFS 卷头
    
    Args:
        stream: 二进制流
        offset: 偏移量
    
    Returns:
        HFSVolumeHeader 对象
    """
    stream.seek(offset)
    data = stream.read(512)
    
    return HFSVolumeHeader.from_bytes(data)


def is_hfs_volume(stream, offset: int = 1024) -> bool:
    """
    检查是否是 HFS 卷
    
    Args:
        stream: 二进制流
        offset: 偏移量
    
    Returns:
        是否是 HFS 卷
    """
    try:
        stream.seek(offset)
        signature = struct.unpack('>H', stream.read(2))[0]
        return signature == HFS_SIGNATURE
    except:
        return False
