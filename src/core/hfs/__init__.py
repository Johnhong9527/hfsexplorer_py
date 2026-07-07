"""
HFS+ 核心模块

提供 HFS+ 文件系统的解析和访问功能。
"""

from .constants import (
    # 签名常量
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
    
    # 日期常量
    HFS_EPOCH_OFFSET,
    
    # 块大小常量
    DEFAULT_BLOCK_SIZE,
    MIN_BLOCK_SIZE,
    MAX_BLOCK_SIZE,
    
    # Catalog Node ID
    CatalogNodeID,
    
    # 卷属性
    VolumeAttributes,
    
    # 卷头偏移量
    VolumeHeaderOffset,
    VOLUME_HEADER_SIZE,
    VOLUME_HEADER_OFFSET,
    
    # Fork 数据结构
    EXTENT_DESCRIPTOR_SIZE,
    EXTENT_RECORD_COUNT,
    EXTENT_RECORD_SIZE,
    FORK_DATA_SIZE,
    
    # Finder Info
    FINDER_INFO_SIZE,
    
    # B-tree 常量
    BTreeNodeKind,
    BTreeHeaderRecord,
    BTREE_HEADER_RECORD_SIZE,
    BTREE_NODE_DESCRIPTOR_SIZE,
    
    # Catalog 记录类型
    CatalogRecordType,
    
    # Catalog Key 偏移量
    CatalogKeyOffset,
    
    # 文件标志
    FileFlags,
    
    # 辅助函数
    signature_to_string,
    attributes_to_string,
    hfs_date_to_timestamp,
)

from .structures import (
    ExtentDescriptor,
    ForkData,
    FinderInfo,
    HFSPlusVolumeHeader,
)

from .reader import (
    HFSPlusVolumeHeaderReader,
    read_volume_header,
    is_hfs_plus_volume,
    get_volume_info,
)

__all__ = [
    # 常量
    'SIGNATURE_HFS_PLUS',
    'SIGNATURE_HFSX',
    'HFS_EPOCH_OFFSET',
    'DEFAULT_BLOCK_SIZE',
    'MIN_BLOCK_SIZE',
    'MAX_BLOCK_SIZE',
    'CatalogNodeID',
    'VolumeAttributes',
    'VolumeHeaderOffset',
    'VOLUME_HEADER_SIZE',
    'VOLUME_HEADER_OFFSET',
    'EXTENT_DESCRIPTOR_SIZE',
    'EXTENT_RECORD_COUNT',
    'EXTENT_RECORD_SIZE',
    'FORK_DATA_SIZE',
    'FINDER_INFO_SIZE',
    'BTreeNodeKind',
    'BTreeHeaderRecord',
    'BTREE_HEADER_RECORD_SIZE',
    'BTREE_NODE_DESCRIPTOR_SIZE',
    'CatalogRecordType',
    'CatalogKeyOffset',
    'FileFlags',
    
    # 辅助函数
    'signature_to_string',
    'attributes_to_string',
    'hfs_date_to_timestamp',
    
    # 数据结构
    'ExtentDescriptor',
    'ForkData',
    'FinderInfo',
    'HFSPlusVolumeHeader',
    
    # 读取器
    'HFSPlusVolumeHeaderReader',
    'read_volume_header',
    'is_hfs_plus_volume',
    'get_volume_info',
]