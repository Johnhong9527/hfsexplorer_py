"""
HFS+ 卷头解析器和卷读取器

提供读取和解析 HFS+ 卷头的功能，以及完整的卷读取接口。
"""

import struct
import os
from typing import BinaryIO, Optional, Union, List, Dict, Any

from .constants import (
    VOLUME_HEADER_OFFSET,
    VOLUME_HEADER_SIZE,
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
)
from .structures import HFSPlusVolumeHeader
from .btree import (
    CatalogBTree, ExtentsBTree, HFSPlusFileReader,
    HFSPlusCatalogKey, HFSPlusCatalogFolder, HFSPlusCatalogFile,
    CatalogRecordType, ForkType,
)


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


# =============================================================================
# HFS+ 卷读取器
# =============================================================================

class HFSPlusVolume:
    """
    HFS+ 卷读取器
    
    提供统一的接口来读取 HFS+ 卷的内容。
    整合了卷头、Catalog B-tree、Extents B-tree 和文件读取器。
    
    Usage:
        with HFSPlusVolume("/path/to/disk.img") as vol:
            # 获取卷信息
            info = vol.get_info()
            
            # 列出根目录
            contents = vol.list_folder(2)  # 2 = root CNID
            
            # 读取文件
            data = vol.read_file(file_id)
    """
    
    def __init__(self, source: Union[str, BinaryIO], volume_offset: int = 0):
        """
        初始化 HFS+ 卷读取器
        
        Args:
            source: 文件路径或已打开的文件对象
            volume_offset: 卷在文件中的偏移量（用于分区支持）
        """
        self._source = source
        self._volume_offset = volume_offset
        self._file: Optional[BinaryIO] = None
        self._should_close = False
        self._header: Optional[HFSPlusVolumeHeader] = None
        self._catalog: Optional[CatalogBTree] = None
        self._extents: Optional[ExtentsBTree] = None
        self._file_reader: Optional[HFSPlusFileReader] = None
        
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
    
    @property
    def header(self) -> HFSPlusVolumeHeader:
        """获取卷头"""
        if self._header is None:
            self._read_header()
        return self._header
    
    @property
    def catalog(self) -> CatalogBTree:
        """获取 Catalog B-tree"""
        if self._catalog is None:
            self._init_btrees()
        return self._catalog
    
    @property
    def extents(self) -> ExtentsBTree:
        """获取 Extents B-tree"""
        if self._extents is None:
            self._init_btrees()
        return self._extents
    
    def _read_header(self):
        """读取卷头"""
        self._file.seek(self._volume_offset + VOLUME_HEADER_OFFSET)
        data = self._file.read(VOLUME_HEADER_SIZE)
        
        if len(data) < VOLUME_HEADER_SIZE:
            raise IOError(f"无法读取完整的卷头")
        
        self._header = HFSPlusVolumeHeader.from_bytes(data)
        
        if not self._header.is_valid:
            raise ValueError(f"无效的 HFS+ 签名: 0x{self._header.signature:04X}")
    
    def _init_btrees(self):
        """初始化 B-tree 读取器"""
        h = self.header
        
        # Catalog B-tree
        # catalog_file 是 ForkData，其 extents 描述了 B-tree 的位置
        catalog_extents = h.catalog_file.extents
        if catalog_extents and catalog_extents[0].block_count > 0:
            catalog_start = self._volume_offset + catalog_extents[0].start_block * h.block_size
            # CatalogBTree 会从 B-tree 头记录读取 node_size
            self._catalog = CatalogBTree(
                self._file,
                start_offset=catalog_start,
                node_size=4096  # 默认值，会被 B-tree 头记录覆盖
            )
        else:
            raise IOError("Catalog B-tree 位置无效")
        
        # Extents B-tree
        extents_extents = h.extents_file.extents
        if extents_extents and extents_extents[0].block_count > 0:
            extents_start = self._volume_offset + extents_extents[0].start_block * h.block_size
            # ExtentsBTree 会从 B-tree 头记录读取 node_size
            self._extents = ExtentsBTree(
                self._file,
                start_offset=extents_start,
                node_size=4096  # 默认值，会被 B-tree 头记录覆盖
            )
        else:
            # Extents B-tree 可能为空（小卷没有 overflow extents）
            self._extents = ExtentsBTree(
                self._file,
                start_offset=0,
                node_size=4096
            )
        
        # 文件读取器
        self._file_reader = HFSPlusFileReader(
            self._file,
            self._catalog,
            self._extents,
            block_size=h.block_size
        )
    
    def get_info(self) -> Dict[str, Any]:
        """获取卷信息"""
        h = self.header
        return {
            'signature': 'HFS+' if h.is_hfs_plus else 'HFSX',
            'version': h.version,
            'block_size': h.block_size,
            'total_blocks': h.total_blocks,
            'free_blocks': h.free_blocks,
            'volume_size': h.volume_size,
            'file_count': h.file_count,
            'folder_count': h.folder_count,
            'is_journaled': h.is_journaled,
        }
    
    def list_folder(self, parent_id: int = 2) -> List[Dict[str, Any]]:
        """
        列出文件夹内容
        
        Args:
            parent_id: 父文件夹 CNID (默认 2 = 根目录)
        
        Returns:
            文件夹内容列表
        """
        return self.catalog.list_folder_contents(parent_id)
    
    def read_file(self, file_id: int) -> bytes:
        """
        读取文件数据
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            文件数据
        """
        if self._file_reader is None:
            self._init_btrees()
        return self._file_reader.read_data_fork(file_id)
    
    def get_file_info(self, file_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            文件信息字典，如果未找到则返回 None
        """
        for node in self.catalog.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                key = HFSPlusCatalogKey.from_bytes(data)
                record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                
                if record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                    if file.file_id == file_id:
                        return {
                            'id': file.file_id,
                            'name': key.node_name,
                            'size': file.get_data_fork_size(),
                            'create_date': file.create_date,
                            'mod_date': file.content_mod_date,
                            'owner_id': file.get_owner_id(),
                            'group_id': file.get_group_id(),
                            'mode': file.get_file_mode(),
                        }
                elif record_type == CatalogRecordType.FOLDER:
                    folder = HFSPlusCatalogFolder.from_bytes(data, key.occupied_size)
                    if folder.folder_id == file_id:
                        return {
                            'id': folder.folder_id,
                            'name': key.node_name,
                            'create_date': folder.create_date,
                            'mod_date': folder.content_mod_date,
                            'owner_id': folder.get_owner_id(),
                            'group_id': folder.get_group_id(),
                            'mode': folder.get_file_mode(),
                        }
        
        return None


def open_volume(source: Union[str, BinaryIO], 
                volume_offset: int = 0) -> HFSPlusVolume:
    """
    打开 HFS+ 卷的便捷函数
    
    Args:
        source: 文件路径或已打开的文件对象
        volume_offset: 卷在文件中的偏移量
    
    Returns:
        HFSPlusVolume 对象
    """
    return HFSPlusVolume(source, volume_offset)