"""
HFS+ 文件系统常量定义

定义 HFS+ 文件系统中使用的常量、签名和属性标志。
"""

from enum import IntEnum, IntFlag
from typing import Dict

# =============================================================================
# 签名常量
# =============================================================================

# HFS+ 签名 (0x482B = "H+")
SIGNATURE_HFS_PLUS: int = 0x482B

# HFSX 签名 (0x4858 = "HX")
SIGNATURE_HFSX: int = 0x4858

# =============================================================================
# 日期相关常量
# =============================================================================

# HFS 纪元偏移 (1904-01-01 到 1970-01-01 的秒数)
HFS_EPOCH_OFFSET: int = 2082844800

# =============================================================================
# 块大小相关常量
# =============================================================================

# 默认块大小
DEFAULT_BLOCK_SIZE: int = 4096

# 最小块大小
MIN_BLOCK_SIZE: int = 512

# 最大块大小
MAX_BLOCK_SIZE: int = 65536

# =============================================================================
# Catalog Node ID 保留值
# =============================================================================

class CatalogNodeID(IntEnum):
    """Catalog Node ID 保留值"""
    ROOT_PARENT = 1
    ROOT_FOLDER = 2
    EXTENTS_FILE = 3
    CATALOG_FILE = 4
    BAD_BLOCK_FILE = 5
    ALLOCATION_FILE = 6
    STARTUP_FILE = 7
    ATTRIBUTES_FILE = 8
    REPAIR_CATALOG_FILE = 14
    BOGUS_EXTENT_FILE = 15
    FIRST_USER = 16

# =============================================================================
# 卷属性标志
# =============================================================================

class VolumeAttributes(IntFlag):
    """卷属性标志位"""
    HARDWARE_LOCK = 1 << 7        # bit 7: 卷被硬件锁定
    VOLUME_UNMOUNTED = 1 << 8     # bit 8: 卷已干净卸载
    SPARED_BLOCKS = 1 << 9        # bit 9: 卷有备用块
    NO_CACHE_REQUIRED = 1 << 10   # bit 10: 不需要缓存
    BOOT_INCONSISTENT = 1 << 11   # bit 11: 启动卷不一致
    CATALOG_IDS_REUSED = 1 << 12  # bit 12: Catalog Node ID 已重用
    VOLUME_JOURNALED = 1 << 13    # bit 13: 卷已启用日志
    SOFTWARE_LOCK = 1 << 15       # bit 15: 卷被软件锁定

# =============================================================================
# 卷头偏移量
# =============================================================================

class VolumeHeaderOffset(IntEnum):
    """卷头字段偏移量"""
    SIGNATURE = 0                # 2 bytes, uint16
    VERSION = 2                  # 2 bytes, uint16
    ATTRIBUTES = 4               # 4 bytes, uint32
    LAST_MOUNTED_VERSION = 8     # 4 bytes, uint32 (ASCII)
    JOURNAL_INFO_BLOCK = 12      # 4 bytes, uint32
    CREATE_DATE = 16             # 4 bytes, uint32 (本地时间)
    MODIFY_DATE = 20             # 4 bytes, uint32 (本地时间)
    BACKUP_DATE = 24             # 4 bytes, uint32 (本地时间)
    CHECKED_DATE = 28            # 4 bytes, uint32 (本地时间)
    FILE_COUNT = 32              # 4 bytes, uint32
    FOLDER_COUNT = 36            # 4 bytes, uint32
    BLOCK_SIZE = 40              # 4 bytes, uint32
    TOTAL_BLOCKS = 44            # 4 bytes, uint32
    FREE_BLOCKS = 48             # 4 bytes, uint32
    NEXT_ALLOCATION = 52         # 4 bytes, uint32
    RSRC_CLUMP_SIZE = 56         # 4 bytes, uint32
    DATA_CLUMP_SIZE = 60         # 4 bytes, uint32
    NEXT_CATALOG_ID = 64         # 4 bytes, uint32
    WRITE_COUNT = 68             # 4 bytes, uint32
    ENCODINGS_BITMAP = 72        # 8 bytes, uint64
    FINDER_INFO = 80             # 32 bytes, HFSVolumeFinderInfo
    ALLOCATION_FILE = 112        # 80 bytes, HFSPlusForkData
    EXTENTS_FILE = 192           # 80 bytes, HFSPlusForkData
    CATALOG_FILE = 272           # 80 bytes, HFSPlusForkData
    ATTRIBUTES_FILE = 352        # 80 bytes, HFSPlusForkData
    STARTUP_FILE = 432           # 80 bytes, HFSPlusForkData

# 卷头总大小
VOLUME_HEADER_SIZE: int = 512

# 卷头偏移量 (从卷开始)
VOLUME_HEADER_OFFSET: int = 1024

# =============================================================================
# Fork 数据结构
# =============================================================================

# Extent 描述符大小
EXTENT_DESCRIPTOR_SIZE: int = 8  # 2 x uint32

# Extent 记录中的描述符数量
EXTENT_RECORD_COUNT: int = 8

# Extent 记录大小
EXTENT_RECORD_SIZE: int = EXTENT_DESCRIPTOR_SIZE * EXTENT_RECORD_COUNT  # 64 bytes

# Fork 数据大小
FORK_DATA_SIZE: int = 80  # 8 + 4 + 4 + 64

# =============================================================================
# Finder Info 结构
# =============================================================================

# Finder Info 大小
FINDER_INFO_SIZE: int = 32

# =============================================================================
# B-tree 相关常量
# =============================================================================

class BTreeNodeKind(IntEnum):
    """B-tree 节点类型"""
    HEADER = 1      # 头节点
    MAP = 2         # 位图节点
    INDEX = 0       # 索引节点
    LEAF = -1       # 叶节点

class BTreeHeaderRecord(IntEnum):
    """B-tree 头记录偏移量"""
    TREE_DEPTH = 0          # 2 bytes
    ROOT_NODE = 2           # 4 bytes
    LEAF_RECORDS = 6        # 4 bytes
    FIRST_LEAF_NODE = 10    # 4 bytes
    LAST_LEAF_NODE = 14     # 4 bytes
    NODE_SIZE = 18          # 2 bytes
    MAX_KEY_LENGTH = 20     # 2 bytes
    TOTAL_NODES = 22        # 4 bytes
    FREE_NODES = 26         # 4 bytes
    CLUMP_SIZE = 30         # 4 bytes
    BTREE_TYPE = 34         # 1 byte
    KEY_COMPARE_TYPE = 35   # 1 byte
    ATTRIBUTES = 36         # 4 bytes

# B-tree 头记录大小
BTREE_HEADER_RECORD_SIZE: int = 106

# B-tree 节点描述符大小
BTREE_NODE_DESCRIPTOR_SIZE: int = 14

# =============================================================================
# Catalog 记录类型
# =============================================================================

class CatalogRecordType(IntEnum):
    """Catalog 记录类型"""
    FOLDER = 0x01           # 文件夹记录
    FILE = 0x02             # 文件记录
    FOLDER_THREAD = 0x03    # 文件夹线程记录
    FILE_THREAD = 0x04      # 文件线程记录

# =============================================================================
# Catalog Key 偏移量
# =============================================================================

class CatalogKeyOffset(IntEnum):
    """Catalog Key 偏移量"""
    KEY_LENGTH = 0      # 2 bytes
    PARENT_ID = 2       # 4 bytes
    NODE_NAME_LENGTH = 6  # 2 bytes
    NODE_NAME = 8       # 变长

# =============================================================================
# 文件标志
# =============================================================================

class FileFlags(IntFlag):
    """文件标志位"""
    LOCKED = 1 << 0        # bit 0: 文件被锁定
    THREAD_EXISTS = 1 << 1 # bit 1: 线程记录存在
    HAS_ATTRIBUTES = 1 << 5  # bit 5: 有扩展属性
    HAS_SECURITY = 1 << 6    # bit 6: 有安全信息
    NAMED_FORKS = 1 << 7     # bit 7: 有命名分支

# =============================================================================
# 辅助函数
# =============================================================================

def signature_to_string(signature: int) -> str:
    """将签名转换为字符串"""
    if signature == SIGNATURE_HFS_PLUS:
        return "HFS+"
    elif signature == SIGNATURE_HFSX:
        return "HFSX"
    else:
        return f"Unknown (0x{signature:04X})"

def attributes_to_string(attributes: int) -> str:
    """将属性标志转换为字符串"""
    flags = []
    for attr in VolumeAttributes:
        if attributes & attr:
            flags.append(attr.name)
    return ", ".join(flags) if flags else "None"

def hfs_date_to_timestamp(hfs_date: int) -> float:
    """将 HFS 日期转换为 Unix 时间戳"""
    if hfs_date == 0:
        return 0.0
    return float(hfs_date) - HFS_EPOCH_OFFSET