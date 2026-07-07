"""
HFS+ 卷头解析器

提供读取和解析 HFS+ 卷头的功能。
"""

import os
from typing import BinaryIO, Optional, Union

from .constants import (
    VOLUME_HEADER_OFFSET,
    VOLUME_HEADER_SIZE,
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
)
from .structures import HFSPlusVolumeHeader


class HFSPlusVolumeHeaderReader:
    """
    HFS+ 卷头读取器
    
    用于从文件或设备读取 HFS+ 卷头。
    
    Usage:
        reader = HFSPlusVolumeHeaderReader("/path/to/disk.img")
        header = reader.read_header()
        print(header)
    """
    
    def __init__(self, source: Union[str, BinaryIO]):
        """
        初始化卷头读取器
        
        Args:
            source: 文件路径或已打开的文件对象
        """
        self._source = source
        self._file: Optional[BinaryIO] = None
        self._header: Optional[HFSPlusVolumeHeader] = None
        
        # 如果是字符串，打开文件
        if isinstance(source, str):
            self._file = open(source, 'rb')
            self._should_close = True
        else:
            self._file = source
            self._should_close = False
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    def close(self):
        """关闭文件"""
        if self._file and self._should_close:
            self._file.close()
            self._file = None
    
    def read_header(self) -> HFSPlusVolumeHeader:
        """
        读取 HFS+ 卷头
        
        Returns:
            HFSPlusVolumeHeader 对象
        
        Raises:
            ValueError: 如果签名无效
            IOError: 如果读取失败
        """
        # 定位到卷头位置
        self._file.seek(VOLUME_HEADER_OFFSET)
        
        # 读取卷头数据
        data = self._file.read(VOLUME_HEADER_SIZE)
        if len(data) < VOLUME_HEADER_SIZE:
            raise IOError(f"无法读取完整的卷头: 期望 {VOLUME_HEADER_SIZE} 字节, 实际 {len(data)} 字节")
        
        # 解析卷头
        header = HFSPlusVolumeHeader.from_bytes(data)
        
        # 验证签名
        if not header.is_valid:
            raise ValueError(f"无效的 HFS+ 签名: 0x{header.signature:04X}")
        
        self._header = header
        return header
    
    def get_header(self) -> Optional[HFSPlusVolumeHeader]:
        """
        获取已读取的卷头
        
        Returns:
            HFSPlusVolumeHeader 对象，如果尚未读取则返回 None
        """
        return self._header
    
    def is_hfs_plus(self) -> bool:
        """
        检查是否为 HFS+ 卷
        
        Returns:
            如果是 HFS+ 卷则返回 True
        """
        if self._header is None:
            self.read_header()
        return self._header.is_hfs_plus
    
    def is_hfsx(self) -> bool:
        """
        检查是否为 HFSX 卷
        
        Returns:
            如果是 HFSX 卷则返回 True
        """
        if self._header is None:
            self.read_header()
        return self._header.is_hfsx
    
    def validate(self) -> bool:
        """
        验证卷头有效性
        
        Returns:
            如果卷头有效则返回 True
        """
        try:
            if self._header is None:
                self.read_header()
            return self._header.is_valid
        except (ValueError, IOError):
            return False


def read_volume_header(source: Union[str, BinaryIO]) -> HFSPlusVolumeHeader:
    """
    读取 HFS+ 卷头的便捷函数
    
    Args:
        source: 文件路径或已打开的文件对象
        
    Returns:
        HFSPlusVolumeHeader 对象
        
    Raises:
        ValueError: 如果签名无效
        IOError: 如果读取失败
    """
    with HFSPlusVolumeHeaderReader(source) as reader:
        return reader.read_header()


def is_hfs_plus_volume(source: Union[str, BinaryIO]) -> bool:
    """
    检查是否为 HFS+ 卷的便捷函数
    
    Args:
        source: 文件路径或已打开的文件对象
        
    Returns:
        如果是 HFS+ 卷则返回 True
    """
    try:
        with HFSPlusVolumeHeaderReader(source) as reader:
            return reader.is_hfs_plus()
    except (ValueError, IOError):
        return False


def get_volume_info(source: Union[str, BinaryIO]) -> dict:
    """
    获取卷信息的便捷函数
    
    Args:
        source: 文件路径或已打开的文件对象
        
    Returns:
        包含卷信息的字典
    """
    with HFSPlusVolumeHeaderReader(source) as reader:
        header = reader.read_header()
        
        return {
            'signature': header.signature,
            'signature_string': 'HFS+' if header.is_hfs_plus else 'HFSX',
            'version': header.version,
            'attributes': header.attributes,
            'is_journaled': header.is_journaled,
            'is_locked': header.is_locked,
            'is_cleanly_unmounted': header.is_cleanly_unmounted,
            'last_mounted_version': header.last_mounted_version,
            'create_date': header.create_datetime.isoformat() if header.create_datetime else None,
            'modify_date': header.modify_datetime.isoformat() if header.modify_datetime else None,
            'backup_date': header.backup_datetime.isoformat() if header.backup_datetime else None,
            'checked_date': header.checked_datetime.isoformat() if header.checked_datetime else None,
            'file_count': header.file_count,
            'folder_count': header.folder_count,
            'block_size': header.block_size,
            'total_blocks': header.total_blocks,
            'free_blocks': header.free_blocks,
            'volume_size': header.volume_size,
            'free_space': header.free_space,
            'used_space': header.used_space,
            'next_catalog_id': header.next_catalog_id,
            'write_count': header.write_count,
        }