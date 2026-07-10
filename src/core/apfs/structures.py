"""
APFS 数据结构定义

基于 Apple File System Reference 和 apfs-fuse 项目
"""

import struct
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import IntEnum

# ============================================================
# 魔数和常量
# ============================================================

# APFS 容器魔数 "NXSB"
NX_MAGIC = b'NXSB'

# APFS 卷魔数 "APSB"
APFS_MAGIC = b'APSB'

# APFS 类型掩码和移位
APFS_TYPE_MASK = 0x0000FFFF
APFS_TYPE_SHIFT = 0

# 对象类型
class ObjType(IntEnum):
    """APFS 对象类型"""
    NX_SUPERBLOCK = 0x0001
    B_TREE = 0x0002
    B_TREE_NODE = 0x0003
    SPACEMAN_FREE_QUEUE = 0x0004
    EXTENT_LIST_TREE = 0x0005
    OMAP = 0x0006
    CHECKPOINT_MAP = 0x0007
    FS = 0x0008  # 卷超级块
    FUSION_MIDDLE_TREE = 0x0009
    NX_REAPER = 0x000A
    NX_TEST = 0x000B
    NX_MINI_2ND = 0x000C
    GBITMAP = 0x000D
    GBITMAP_TREE = 0x000E
    GBITMAP_BLOCK = 0x000F
    ER_STATE = 0x0010
    GBITMAP_EXTENT = 0x0011
    OMAP_SNAPSHOT = 0x0012
    EFI_JUMPSTART = 0x0013
    FUSION_ITERN = 0x0014
    ENCRYPTION_STATE = 0x0015
    SD_DATA = 0x0016
    
    # 卷对象类型
    INVALID = 0
    TEST = 1
    CONTAINER = 2
    VOLUME = 3
    SNAPSHOT = 4

# 对象标志
class ObjFlags(IntEnum):
    """APFS 对象标志"""
    VIRTUAL = 0x0000
    EPHEMERAL = 0x8000
    PHYSICAL = 0x4000
    NOHEADER = 0x2000
    ENCRYPTED = 0x1000
    NONPERSISTENT = 0x0800

# B-tree 节点标志
class BTNodeFlags(IntEnum):
    """B-tree 节点标志"""
    NODE_FIXED_KV_SIZE = 0x0001  # 固定键值大小
    NODE_CHECK_KOFF_INVAL_ORDER = 0x0002  # 检查键偏移无效顺序
    NODE_HASHED = 0x0004  # 哈希节点
    NODE_NOHEADER = 0x0008  # 无头节点
    NODE_LEAF = 0x0001  # 叶节点（与 FIXED_KV_SIZE 共用）
    NODE_INDEX = 0x0002  # 索引节点

# ============================================================
# 数据结构
# ============================================================

@dataclass
class APFSHeader:
    """APFS 对象头"""
    checksum: int  # uint64 - 校验和
    oid: int  # uint64 - 对象 ID
    xid: int  # uint64 - 事务 ID
    type: int  # uint32 - 对象类型
    subtype: int  # uint32 - 子类型
    
    STRUCT_FORMAT = '<QQQII'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'APFSHeader':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)
    
    def to_bytes(self) -> bytes:
        return struct.pack(self.STRUCT_FORMAT, 
                          self.checksum, self.oid, self.xid, 
                          self.type, self.subtype)


@dataclass
class NXSuperblock:
    """
    容器超级块 (Container Superblock)
    
    位于容器的物理偏移 0 处，包含容器的全局信息
    """
    header: APFSHeader
    magic: bytes  # uint32 - 魔数 "NXSB"
    block_size: int  # uint32 - 块大小（字节）
    block_count: int  # uint64 - 总块数
    features: int  # uint64 - 特性标志
    read_only_features: int  # uint64 - 只读特性
    incompatible_features: int  # uint64 - 不兼容特性
    
    # UUID
    uuid: bytes  # 16 字节
    
    # 下一个交易 ID
    next_xid: int  # uint64
    
    # 下一个对象 ID
    next_oid: int  # uint64
    
    # 空间管理器
    spaceman_oid: int  # uint64 - 空间管理器对象 ID
    
    # 对象映射
    omap_oid: int  # uint64 - 对象映射 B-tree 的根对象 ID
    
    # 重新启动区域
    reaper_oid: int  # uint64
    
    # 测试类型
    test_type: int  # uint32
    
    # 最大卷数
    max_volumes: int  # uint32
    
    # 卷对象 ID 数组（最多 100 个）
    volume_oids: List[int]  # uint64[100]
    
    # 检查点描述符
    nx_desc_count: int  # uint32
    nx_desc_blocks: int  # uint32
    nx_data_count: int  # uint32
    nx_data_blocks: int  # uint32
    
    # 快照
    nx_latest_xid: int  # uint64
    
    STRUCT_FORMAT = '<32sIQQQQ16sQQQQQQ100sIIIQQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'NXSuperblock':
        """从字节数据解析容器超级块"""
        header = APFSHeader.from_bytes(data, offset)
        offset += APFSHeader.STRUCT_SIZE
        
        magic = struct.unpack_from('<I', data, offset)[0]
        magic_bytes = struct.pack('<I', magic)
        offset += 4
        
        if magic_bytes != NX_MAGIC:
            raise ValueError(f"无效的容器魔数: {magic_bytes!r} (期望 {NX_MAGIC!r})")
        
        # 手动解析各个字段
        block_size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        block_count = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        features = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        read_only_features = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        incompatible_features = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        uuid = struct.unpack_from('<16s', data, offset)[0]
        offset += 16
        next_xid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        next_oid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        spaceman_oid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        omap_oid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        reaper_oid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        test_type = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        max_volumes = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # 解析卷 OID 数组
        volume_oids_data = data[offset:offset + 100 * 8]
        volume_oids = list(struct.unpack_from(f'<{100}Q', volume_oids_data, 0))
        offset += 100 * 8
        
        nx_desc_count = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        nx_desc_blocks = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        nx_data_count = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        nx_data_blocks = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        nx_latest_xid = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        return cls(
            header=header,
            magic=magic_bytes,
            block_size=block_size,
            block_count=block_count,
            features=features,
            read_only_features=read_only_features,
            incompatible_features=incompatible_features,
            uuid=uuid,
            next_xid=next_xid,
            next_oid=next_oid,
            spaceman_oid=spaceman_oid,
            omap_oid=omap_oid,
            reaper_oid=reaper_oid,
            test_type=test_type,
            max_volumes=max_volumes,
            volume_oids=volume_oids,
            nx_desc_count=nx_desc_count,
            nx_desc_blocks=nx_desc_blocks,
            nx_data_count=nx_data_count,
            nx_data_blocks=nx_data_blocks,
            nx_latest_xid=nx_latest_xid,
        )


@dataclass
class APFSSuperblock:
    """
    卷超级块 (Volume Superblock)
    
    包含卷的元数据信息
    """
    header: APFSHeader
    magic: bytes  # uint32 - 魔数 "APSB"
    fs_index: int  # uint32 - 卷索引
    features: int  # uint64 - 特性标志
    read_only_features: int  # uint64 - 只读特性
    incompatible_features: int  # uint64 - 不兼容特性
    
    # UUID
    uuid: bytes  # 16 字节
    
    # 时间戳
    timestamp: int  # int64 - 最后修改时间（纳秒）
    
    # 版本
    version: int  # uint32 - APFS 版本
    minor_version: int  # uint32 - 次版本
    
    # 对象映射
    omap_oid: int  # uint64 - 对象映射 B-tree 的根对象 ID
    
    # 根目录
    root_tree_oid: int  # uint64 - 根目录 B-tree 的根对象 ID
    
    # 扩展属性
    extentref_tree_oid: int  # uint64 - 扩展引用树的根对象 ID
    snap_meta_tree_oid: int  # uint64 - 快照元数据树的根对象 ID
    
    # 下一个对象 ID
    next_obj_id: int  # uint64
    
    # 下一个交易 ID
    next_xid: int  # uint64
    
    # 快照数量
    num_snapshots: int  # uint32
    
    # 总文件数
    total_blocks_used: int  # uint64
    
    # 块大小
    block_size: int  # uint32
    
    # 卷名
    name: str  # UTF-8 字符串
    
    STRUCT_FORMAT = '<32sIQQQ16sQIIQQQQQQIQI256s'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'APFSSuperblock':
        """从字节数据解析卷超级块"""
        header = APFSHeader.from_bytes(data, offset)
        offset += APFSHeader.STRUCT_SIZE
        
        magic = struct.unpack_from('<I', data, offset)[0]
        magic_bytes = struct.pack('<I', magic)
        offset += 4
        
        if magic_bytes != APFS_MAGIC:
            raise ValueError(f"无效的卷魔数: {magic_bytes!r} (期望 {APFS_MAGIC!r})")
        
        fields = struct.unpack_from(
            '<IQQQ16sQIIQQQQQQIQI256s',
            data, offset
        )
        
        # 解析卷名（去除 null 终止符）
        name_bytes = fields[17]
        name = name_bytes.decode('utf-8', errors='replace').rstrip('\x00')
        
        return cls(
            header=header,
            magic=magic_bytes,
            fs_index=fields[0],
            features=fields[1],
            read_only_features=fields[2],
            incompatible_features=fields[3],
            uuid=fields[4],
            timestamp=fields[5],
            version=fields[6],
            minor_version=fields[7],
            omap_oid=fields[8],
            root_tree_oid=fields[9],
            extentref_tree_oid=fields[10],
            snap_meta_tree_oid=fields[11],
            next_obj_id=fields[12],
            next_xid=fields[13],
            num_snapshots=fields[14],
            total_blocks_used=fields[15],
            block_size=fields[16],
            name=name,
        )


@dataclass
class BTNodeDescriptor:
    """
    B-tree 节点描述符
    
    描述 B-tree 节点的类型和状态
    """
    type: int  # uint16 - 节点类型
    flags: int  # uint16 - 节点标志
    left_sibling: int  # uint64 - 左兄弟节点 ID
    right_sibling: int  # uint64 - 右兄弟节点 ID
    
    STRUCT_FORMAT = '<HHQQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTNodeDescriptor':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class BTInfo:
    """
    B-tree 信息
    
    包含 B-tree 的配置信息
    """
    flags: int  # uint32 - 标志
    node_size: int  # uint32 - 节点大小（字节）
    key_size: int  # uint32 - 键大小（0 表示变长）
    val_size: int  # uint32 - 值大小（0 表示变长）
    
    STRUCT_FORMAT = '<IIII'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTInfo':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class JKey:
    """
    APFS 日志键
    
    用于标识文件系统对象
    """
    obj_id: int  # uint64 - 对象 ID
    type: int  # uint16 - 对象类型
    
    STRUCT_FORMAT = '<QH'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JKey':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


# 目录条目类型
class DirEntryType(IntEnum):
    """目录条目类型"""
    UNKNOWN = 0
    FIFO = 1  # FIFO
    CHAR = 2  # 字符设备
    DIR = 4  # 目录
    BLOCK = 6  # 块设备
    REG = 8  # 普通文件
    LINK = 10  # 符号链接
    SOCKET = 12  # 套接字
    WHITEOUT = 14  # 白色输出


@dataclass
class JInode:
    """
    APFS Inode 结构
    
    包含文件/目录的基本信息
    """
    parent_id: int  # uint64 - 父目录 ID
    private_id: int  # uint64 - 私有 ID
    create_time: int  # uint64 - 创建时间（纳秒）
    mod_time: int  # uint64 - 修改时间（纳秒）
    change_time: int  # uint64 - 状态改变时间
    access_time: int  # uint64 - 访问时间
    internal_flags: int  # uint64 - 内部标志
    nchildren: int  # int32 - 子项数量（仅目录）
    nlink: int  # int32 - 硬链接数
    
    # 所有者信息
    uid: int  # uint32 - 用户 ID
    gid: int  # uint32 - 组 ID
    mode: int  # uint16 - 文件模式
    
    # 标志
    pad1: int  # uint16
    pad2: int  # uint32
    
    # 扩展字段
    bsd_flags: int  # uint32 - BSD 标志
    rdev: int  # uint32 - 设备号
    
    # 数据大小
    nsec: int  # uint64 - 纳秒级时间戳
    
    STRUCT_FORMAT = '<QQQQQQQiiIIIHHIIQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JInode':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class JDirEntry:
    """
    APFS 目录条目
    
    包含文件名和 inode 信息
    """
    target_id: int  # uint64 - 目标 inode ID
    date_added: int  # uint64 - 添加日期
    flags: int  # uint16 - 标志
    name: str  # 文件名
    
    STRUCT_FORMAT = '<QQH'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0, name_offset: int = 0) -> 'JDirEntry':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        
        # 读取文件名（变长）
        name_bytes = data[name_offset:]
        null_pos = name_bytes.find(b'\x00')
        if null_pos >= 0:
            name_bytes = name_bytes[:null_pos]
        
        name = name_bytes.decode('utf-8', errors='replace')
        
        return cls(
            target_id=fields[0],
            date_added=fields[1],
            flags=fields[2],
            name=name,
        )


@dataclass
class JFileExtent:
    """
    APFS 文件扩展
    
    描述文件数据的物理位置
    """
    len_and_flags: int  # uint64 - 长度和标志
    phys_block_num: int  # uint64 - 物理块号
    crypto_id: int  # uint64 - 加密 ID
    
    STRUCT_FORMAT = '<QQQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JFileExtent':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)
    
    @property
    def length(self) -> int:
        """获取长度（字节）"""
        return self.len_and_flags & 0x00FFFFFFFFFFFFFF
    
    @property
    def flags(self) -> int:
        """获取标志"""
        return (self.len_and_flags >> 56) & 0xFF


@dataclass
class OMAP:
    """
    对象映射 (Object Map)
    
    将虚拟对象 ID 映射到物理块号
    """
    flags: int  # uint32 - 标志
    snap_count: int  # uint32 - 快照数量
    tree_type: int  # uint32 - 树类型
    tree_oid: int  # uint64 - 树对象 ID
    latest_snap_xid: int  # uint64 - 最新快照 XID
    
    STRUCT_FORMAT = '<IIIIQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'OMAP':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class OMAPEntry:
    """
    对象映射条目
    
    将虚拟对象 ID 映射到物理块号
    """
    oid: int  # uint64 - 对象 ID
    xid: int  # uint64 - 事务 ID
    paddr: int  # uint64 - 物理地址（块号）
    
    STRUCT_FORMAT = '<QQQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'OMAPEntry':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class SpacemanDevice:
    """
    空间管理器设备信息
    """
    block_size: int  # uint32 - 块大小
    blocks_per_chunk: int  # uint32 - 每个 chunk 的块数
    chunks_per_cib: int  # uint32 - 每个 CIB 的 chunk 数
    cibs_per_cab: int  # uint32 - 每个 CAB 的 CIB 数
    
    STRUCT_FORMAT = '<IIII'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'SpacemanDevice':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)


@dataclass
class SpacemanFreeQueue:
    """
    空间管理器空闲队列
    """
    count: int  # uint64 - 条目数量
    tree_oid: int  # uint64 - 树对象 ID
    oldest_xid: int  # uint64 - 最旧的事务 ID
    newest_xid: int  # uint64 - 最新的事务 ID
    
    STRUCT_FORMAT = '<QQQQ'
    STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'SpacemanFreeQueue':
        fields = struct.unpack_from(cls.STRUCT_FORMAT, data, offset)
        return cls(*fields)
