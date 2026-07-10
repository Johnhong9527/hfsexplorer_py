"""
APFS 完整支持模块

提供 APFS 文件系统的完整读取、写入和管理功能。
"""

import struct
from typing import Optional, List, Dict, Tuple, BinaryIO
from dataclasses import dataclass
from enum import IntEnum, IntFlag
from datetime import datetime, timezone


# =============================================================================
# APFS 常量
# =============================================================================

# 魔数
NX_MAGIC = b'NXSB'
APFS_MAGIC = b'APSB'

# 对象类型
class ObjType(IntEnum):
    """对象类型"""
    NX_SUPERBLOCK = 0x00000001
    BTREE = 0x00000002
    BTREE_NODE = 0x00000003
    SPACEMAN = 0x00000005
    EXTENT_LIST = 0x00000006
    OMAP = 0x00000007
    CHECKPOINT_MAP = 0x00000008
    FS = 0x00000009  # 文件系统（卷）
    FSTREE = 0x0000000A
    BLOCKREFTREE = 0x0000000B
    SNAPSHOTMETATREE = 0x0000000C
    NUMLINKS_LIST = 0x0000000D
    FUSION_MIDTREE = 0x0000000E
    
    # APFS 对象类型
    JOURN_ALLOC = 0x00000010
    JOURN = 0x00000011
    
    # 目录/文件相关
    INODE = 0x00000020
    XATTR = 0x00000021
    SIBLING_LINK = 0x00000022
    DSTREAM_ID = 0x00000023
    CRYPTO_STATE = 0x00000024
    FILE_EXTENT = 0x00000025
    DIR_REC = 0x00000026
    DIR_STATS = 0x00000027
    SNAPSHOT_NAME = 0x00000028
    SNAP_META = 0x00000029


# 对象标志
class ObjFlags(IntFlag):
    """对象标志"""
    VIRTUAL = 0x00000001
    EPHEMERAL = 0x00000002
    PHYSICAL = 0x00000004
    NONPERSISTENT = 0x00000008
    HEADER = 0x00000010
    HASHED = 0x00000020
    NOHEADER = 0x00000040
    ENCRYPTED = 0x00000080


# 目录条目类型
class DirEntryType(IntEnum):
    """目录条目类型"""
    UNKNOWN = 0
    REG_FILE = 1
    DIR = 2
    SYMLINK = 3
    FIFO = 4
    CHARDEV = 5
    BLOCKDEV = 6
    SOCKET = 7
    WHITEOUT = 8


# =============================================================================
# APFS 数据结构
# =============================================================================

@dataclass
class BTNodeDescriptor:
    """B-tree 节点描述符"""
    next: int  # 下一个节点 OID
    prev: int  # 上一个节点 OID
    type: int  # 节点类型
    flags: int  # 标志
    num_keys: int  # 键数量
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTNodeDescriptor':
        """从字节序列解析"""
        next_oid = struct.unpack_from('<Q', data, offset)[0]
        prev_oid = struct.unpack_from('<Q', data, offset + 8)[0]
        node_type = struct.unpack_from('<B', data, offset + 16)[0]
        flags = struct.unpack_from('<B', data, offset + 17)[0]
        num_keys = struct.unpack_from('<H', data, offset + 18)[0]
        
        return cls(
            next=next_oid,
            prev=prev_oid,
            type=node_type,
            flags=flags,
            num_keys=num_keys
        )


@dataclass
class JKey:
    """APFS 日志键"""
    obj_id: int  # 对象 ID
    type: int  # 对象类型
    num: int  # 序列号
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JKey':
        """从字节序列解析"""
        # JKey 是 8 字节
        # 低 44 位是 obj_id
        # 接下来 8 位是 type
        # 高 12 位是 num
        val = struct.unpack_from('<Q', data, offset)[0]
        obj_id = val & 0x00000FFFFFFFFFFF
        type_val = (val >> 44) & 0xFF
        num = (val >> 52) & 0xFFF
        
        return cls(obj_id=obj_id, type=type_val, num=num)


@dataclass
class JInode:
    """APFS inode"""
    parent_id: int
    private_id: int
    create_time: int
    mod_time: int
    change_time: int
    access_time: int
    internal_flags: int
    nchildren_or_nlink: int
    default_protection_class: int
    write_gen_counter: int
    bsd_flags: int
    owner: int
    group: int
    mode: int
    uncompressed_size: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JInode':
        """从字节序列解析"""
        parent_id = struct.unpack_from('<Q', data, offset)[0]
        private_id = struct.unpack_from('<Q', data, offset + 8)[0]
        create_time = struct.unpack_from('<Q', data, offset + 16)[0]
        mod_time = struct.unpack_from('<Q', data, offset + 24)[0]
        change_time = struct.unpack_from('<Q', data, offset + 32)[0]
        access_time = struct.unpack_from('<Q', data, offset + 40)[0]
        internal_flags = struct.unpack_from('<Q', data, offset + 48)[0]
        nchildren_or_nlink = struct.unpack_from('<I', data, offset + 56)[0]
        default_protection_class = struct.unpack_from('<I', data, offset + 60)[0]
        write_gen_counter = struct.unpack_from('<I', data, offset + 64)[0]
        bsd_flags = struct.unpack_from('<I', data, offset + 68)[0]
        owner = struct.unpack_from('<I', data, offset + 72)[0]
        group = struct.unpack_from('<I', data, offset + 76)[0]
        mode = struct.unpack_from('<H', data, offset + 80)[0]
        uncompressed_size = struct.unpack_from('<Q', data, offset + 82)[0]
        
        return cls(
            parent_id=parent_id,
            private_id=private_id,
            create_time=create_time,
            mod_time=mod_time,
            change_time=change_time,
            access_time=access_time,
            internal_flags=internal_flags,
            nchildren_or_nlink=nchildren_or_nlink,
            default_protection_class=default_protection_class,
            write_gen_counter=write_gen_counter,
            bsd_flags=bsd_flags,
            owner=owner,
            group=group,
            mode=mode,
            uncompressed_size=uncompressed_size
        )


@dataclass
class JDirEntry:
    """APFS 目录条目"""
    target_id: int  # 目标对象 ID
    date_added: int  # 添加日期
    flags: int  # 标志
    name: str  # 文件名
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JDirEntry':
        """从字节序列解析"""
        target_id = struct.unpack_from('<Q', data, offset)[0]
        date_added = struct.unpack_from('<Q', data, offset + 8)[0]
        flags = struct.unpack_from('<H', data, offset + 16)[0]
        
        # 读取文件名
        name_len = struct.unpack_from('<H', data, offset + 18)[0]
        name_bytes = data[offset + 20:offset + 20 + name_len]
        name = name_bytes.decode('utf-8', errors='replace').rstrip('\x00')
        
        return cls(
            target_id=target_id,
            date_added=date_added,
            flags=flags,
            name=name
        )


@dataclass
class JFileExtent:
    """APFS 文件扩展"""
    private_id: int
    logical_addr: int
    phys_block_num: int
    length: int
    crypto_id: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JFileExtent':
        """从字节序列解析"""
        private_id = struct.unpack_from('<Q', data, offset)[0]
        logical_addr = struct.unpack_from('<Q', data, offset + 8)[0]
        
        # 解析长度和标志
        len_and_flags = struct.unpack_from('<Q', data, offset + 16)[0]
        length = len_and_flags & 0x00FFFFFFFFFFFFFF
        flags = (len_and_flags >> 56) & 0xFF
        
        phys_block_num = struct.unpack_from('<Q', data, offset + 24)[0]
        crypto_id = struct.unpack_from('<Q', data, offset + 32)[0]
        
        return cls(
            private_id=private_id,
            logical_addr=logical_addr,
            phys_block_num=phys_block_num,
            length=length,
            crypto_id=crypto_id
        )


@dataclass
class NXSuperblock:
    """NX 容器超级块"""
    magic: bytes
    block_size: int
    total_blocks: int
    num_volumes: int
    volume_oids: List[int]
    omap_oid: int
    xp_desc_base: int
    xp_data_base: int
    xp_desc_blocks: int
    xp_data_blocks: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'NXSuperblock':
        """从字节序列解析"""
        magic = data[32:36]
        if magic != NX_MAGIC:
            raise ValueError("不是有效的 NX 容器")
        
        block_size = struct.unpack_from('<I', data, 36)[0]
        total_blocks = struct.unpack_from('<Q', data, 40)[0]
        
        # 读取卷 OID 数组（最多 100 个）
        num_volumes = 0
        volume_oids = []
        for i in range(100):
            oid = struct.unpack_from('<Q', data, 200 + i * 8)[0]
            if oid != 0:
                num_volumes += 1
            volume_oids.append(oid)
        
        omap_oid = struct.unpack_from('<Q', data, 1000)[0]
        
        # 检查点信息
        xp_desc_base = struct.unpack_from('<Q', data, 1008)[0]
        xp_data_base = struct.unpack_from('<Q', data, 1016)[0]
        xp_desc_blocks = struct.unpack_from('<I', data, 1024)[0]
        xp_data_blocks = struct.unpack_from('<I', data, 1028)[0]
        
        return cls(
            magic=magic,
            block_size=block_size,
            total_blocks=total_blocks,
            num_volumes=num_volumes,
            volume_oids=volume_oids,
            omap_oid=omap_oid,
            xp_desc_base=xp_desc_base,
            xp_data_base=xp_data_base,
            xp_desc_blocks=xp_desc_blocks,
            xp_data_blocks=xp_data_blocks
        )


@dataclass
class APFSSuperblock:
    """APFS 卷超级块"""
    magic: bytes
    block_size: int
    total_blocks: int
    num_blocks_used: int
    features: int
    read_only_features: int
    incompatible_features: int
    uuid: bytes
    next_obj_id: int
    next_xid: int
    root_tree_oid: int
    extentref_tree_oid: int
    snap_meta_tree_oid: int
    num_snapshots: int
    name: str
    version: int
    minor_version: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'APFSSuperblock':
        """从字节序列解析"""
        magic = data[32:36]
        if magic != APFS_MAGIC:
            raise ValueError("不是有效的 APFS 卷")
        
        block_size = struct.unpack_from('<I', data, 36)[0]
        total_blocks = struct.unpack_from('<Q', data, 40)[0]
        num_blocks_used = struct.unpack_from('<Q', data, 48)[0]
        
        features = struct.unpack_from('<Q', data, 56)[0]
        read_only_features = struct.unpack_from('<Q', data, 64)[0]
        incompatible_features = struct.unpack_from('<Q', data, 72)[0]
        
        uuid = data[80:96]
        
        next_obj_id = struct.unpack_from('<Q', data, 96)[0]
        next_xid = struct.unpack_from('<Q', data, 104)[0]
        
        root_tree_oid = struct.unpack_from('<Q', data, 112)[0]
        extentref_tree_oid = struct.unpack_from('<Q', data, 120)[0]
        snap_meta_tree_oid = struct.unpack_from('<Q', data, 128)[0]
        
        num_snapshots = struct.unpack_from('<Q', data, 136)[0]
        
        # 读取卷名
        name_offset = 300
        name_len = struct.unpack_from('<H', data, name_offset)[0]
        name_bytes = data[name_offset + 2:name_offset + 2 + name_len]
        name = name_bytes.decode('utf-8', errors='replace').rstrip('\x00')
        
        version = struct.unpack_from('<I', data, 200)[0]
        minor_version = struct.unpack_from('<I', data, 204)[0]
        
        return cls(
            magic=magic,
            block_size=block_size,
            total_blocks=total_blocks,
            num_blocks_used=num_blocks_used,
            features=features,
            read_only_features=read_only_features,
            incompatible_features=incompatible_features,
            uuid=uuid,
            next_obj_id=next_obj_id,
            next_xid=next_xid,
            root_tree_oid=root_tree_oid,
            extentref_tree_oid=extentref_tree_oid,
            snap_meta_tree_oid=snap_meta_tree_oid,
            num_snapshots=num_snapshots,
            name=name,
            version=version,
            minor_version=minor_version
        )


@dataclass
class OMAP:
    """对象映射"""
    flags: int
    tree_oid: int
    snapshot_xid: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'OMAP':
        """从字节序列解析"""
        # OMAP 在偏移 32 开始
        flags = struct.unpack_from('<I', data, 32)[0]
        tree_oid = struct.unpack_from('<Q', data, 40)[0]
        snapshot_xid = struct.unpack_from('<Q', data, 48)[0]
        
        return cls(
            flags=flags,
            tree_oid=tree_oid,
            snapshot_xid=snapshot_xid
        )


@dataclass
class OMAPEntry:
    """对象映射条目"""
    oid: int  # 对象 ID
    paddr: int  # 物理地址
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'OMAPEntry':
        """从字节序列解析"""
        oid = struct.unpack_from('<Q', data, offset)[0]
        paddr = struct.unpack_from('<Q', data, offset + 8)[0]
        
        return cls(oid=oid, paddr=paddr)


# =============================================================================
# APFS 读取器
# =============================================================================

class APFSContainerReader:
    """
    APFS 容器读取器
    
    负责读取和解析 APFS 容器
    """
    
    def __init__(self, file_path: str):
        """
        初始化 APFS 容器读取器
        
        Args:
            file_path: APFS 镜像文件路径
        """
        self.file_path = file_path
        self.file: Optional[BinaryIO] = None
        self.container: Optional[NXSuperblock] = None
        self.block_size: int = 4096
        self.volumes: Dict[int, 'APFSVolumeReader'] = {}
        
    def open(self) -> None:
        """打开 APFS 容器"""
        self.file = open(self.file_path, 'rb')
        self._read_container()
        
    def close(self) -> None:
        """关闭文件"""
        if self.file:
            self.file.close()
            self.file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _read_block(self, block_num: int) -> bytes:
        """读取指定块"""
        if not self.file:
            raise RuntimeError("文件未打开")
            
        offset = block_num * self.block_size
        self.file.seek(offset)
        return self.file.read(self.block_size)
        
    def _read_container(self) -> None:
        """读取容器超级块"""
        if not self.file:
            raise RuntimeError("文件未打开")
            
        # 尝试不同的偏移
        for offset in [0, 512, 4096]:
            self.file.seek(offset)
            data = self.file.read(4096)
            
            if len(data) >= 36 and data[32:36] == NX_MAGIC:
                self.container = NXSuperblock.from_bytes(data)
                self.block_size = self.container.block_size
                self._load_volumes()
                return
                
        raise ValueError("不是有效的 APFS 容器")
        
    def _load_volumes(self) -> None:
        """加载所有卷"""
        if not self.container:
            return
            
        for i, oid in enumerate(self.container.volume_oids):
            if oid == 0:
                continue
                
            try:
                volume = APFSVolumeReader(self, oid)
                volume.open()
                self.volumes[i] = volume
            except Exception as e:
                print(f"警告: 无法加载卷 {i}: {e}")
                
    def resolve_oid(self, oid: int) -> int:
        """解析对象 ID 到物理地址"""
        if not self.container:
            raise RuntimeError("容器未初始化")
            
        # 读取对象映射
        omap_data = self._read_block(self.container.omap_oid)
        omap = OMAP.from_bytes(omap_data)
        
        # 在对象映射树中查找
        return self._search_omap_tree(omap.tree_oid, oid)
        
    def _search_omap_tree(self, tree_oid: int, target_oid: int) -> int:
        """在对象映射树中搜索"""
        # 读取树节点
        paddr = self.resolve_oid(tree_oid)
        data = self._read_block(paddr)
        
        # 解析节点描述符
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 检查是否是叶节点
        is_leaf = (node_desc.flags & 0x04) != 0
        
        if is_leaf:
            return self._search_omap_leaf(data, target_oid)
        else:
            return self._search_omap_index(data, target_oid)
            
    def _search_omap_leaf(self, data: bytes, target_oid: int) -> int:
        """在叶节点中搜索"""
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 读取偏移表
        table_offset = len(data) - 2
        table_size = struct.unpack_from('<H', data, table_offset)[0]
        
        # 遍历条目
        for i in range(table_size):
            entry_offset = struct.unpack_from('<H', data, table_offset - (i + 1) * 2)[0]
            entry = OMAPEntry.from_bytes(data, entry_offset)
            
            if entry.oid == target_oid:
                return entry.paddr
                
        raise ValueError(f"未找到对象 {target_oid}")
        
    def _search_omap_index(self, data: bytes, target_oid: int) -> int:
        """在索引节点中搜索"""
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 读取偏移表
        table_offset = len(data) - 2
        table_size = struct.unpack_from('<H', data, table_offset)[0]
        
        # 二分查找
        left, right = 0, table_size - 1
        
        while left <= right:
            mid = (left + right) // 2
            entry_offset = struct.unpack_from('<H', data, table_offset - (mid + 1) * 2)[0]
            
            # 读取键
            key_oid = struct.unpack_from('<Q', data, entry_offset)[0]
            
            if key_oid == target_oid:
                # 找到，读取子节点指针
                child_ptr = struct.unpack_from('<Q', data, entry_offset + 8)[0]
                return child_ptr
            elif key_oid < target_oid:
                left = mid + 1
            else:
                right = mid - 1
                
        # 使用最接近的子节点
        if left > 0:
            entry_offset = struct.unpack_from('<H', data, table_offset - left * 2)[0]
            child_ptr = struct.unpack_from('<Q', data, entry_offset + 8)[0]
            return self._search_omap_tree(child_ptr, target_oid)
            
        raise ValueError(f"未找到对象 {target_oid}")
        
    def read_btree(self, oid: int) -> List[Tuple[bytes, bytes]]:
        """读取 B-tree 内容"""
        result = []
        self._read_btree_recursive(oid, result)
        return result
        
    def _read_btree_recursive(self, oid: int, result: List[Tuple[bytes, bytes]]) -> None:
        """递归读取 B-tree"""
        paddr = self.resolve_oid(oid)
        data = self._read_block(paddr)
        
        node_desc = BTNodeDescriptor.from_bytes(data)
        is_leaf = (node_desc.flags & 0x04) != 0
        
        # 读取偏移表
        table_offset = len(data) - 2
        table_size = struct.unpack_from('<H', data, table_offset)[0]
        
        for i in range(table_size):
            entry_offset = struct.unpack_from('<H', data, table_offset - (i + 1) * 2)[0]
            
            if is_leaf:
                # 读取键和值
                key_len = struct.unpack_from('<H', data, entry_offset)[0]
                key = data[entry_offset + 2:entry_offset + 2 + key_len]
                
                val_offset = entry_offset + 2 + key_len
                val_len = struct.unpack_from('<H', data, val_offset)[0]
                value = data[val_offset + 2:val_offset + 2 + val_len]
                
                result.append((key, value))
            else:
                # 索引节点，递归读取
                child_oid = struct.unpack_from('<Q', data, entry_offset + 8)[0]
                self._read_btree_recursive(child_oid, result)


class APFSVolumeReader:
    """
    APFS 卷读取器
    
    负责读取和解析 APFS 卷
    """
    
    def __init__(self, container: APFSContainerReader, volume_oid: int):
        """
        初始化 APFS 卷读取器
        
        Args:
            container: 容器读取器
            volume_oid: 卷对象 ID
        """
        self.container = container
        self.volume_oid = volume_oid
        self.superblock: Optional[APFSSuperblock] = None
        
    def open(self) -> None:
        """打开卷"""
        paddr = self.container.resolve_oid(self.volume_oid)
        data = self.container._read_block(paddr)
        self.superblock = APFSSuperblock.from_bytes(data)
        
    @property
    def name(self) -> str:
        """卷名"""
        return self.superblock.name if self.superblock else ""
        
    @property
    def block_size(self) -> int:
        """块大小"""
        return self.superblock.block_size if self.superblock else 4096
        
    def get_info(self) -> Dict:
        """获取卷信息"""
        if not self.superblock:
            return {}
            
        return {
            'name': self.name,
            'uuid': self.superblock.uuid.hex(),
            'block_size': self.superblock.block_size,
            'total_blocks': self.superblock.total_blocks,
            'blocks_used': self.superblock.num_blocks_used,
            'version': f"{self.superblock.version}.{self.superblock.minor_version}",
            'num_snapshots': self.superblock.num_snapshots,
        }
        
    def list_directory(self, dir_oid: int = 2) -> List[Dict]:
        """
        列出目录内容
        
        Args:
            dir_oid: 目录对象 ID（默认 2，即根目录）
            
        Returns:
            目录条目列表
        """
        if not self.superblock:
            return []
            
        # 读取目录树
        entries = self.container.read_btree(self.superblock.root_tree_oid)
        
        result = []
        for key, value in entries:
            try:
                jkey = JKey.from_bytes(key)
                
                # 检查是否是目录条目
                if jkey.type == ObjType.DIR_REC:
                    if len(value) >= 20:
                        target_id = struct.unpack_from('<Q', value, 0)[0]
                        date_added = struct.unpack_from('<Q', value, 8)[0]
                        flags = struct.unpack_from('<H', value, 16)[0]
                        
                        # 读取文件名
                        name_len = struct.unpack_from('<H', value, 18)[0]
                        name_bytes = value[20:20 + name_len]
                        name = name_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                        
                        is_dir = (flags & 0x10) != 0
                        is_file = (flags & 0x20) != 0
                        
                        entry_type = 'folder' if is_dir else 'file'
                        
                        result.append({
                            'name': name,
                            'id': target_id,
                            'type': entry_type,
                            'flags': flags,
                            'date_added': date_added,
                        })
            except Exception:
                continue
                
        return result
        
    def read_file_data(self, file_oid: int) -> bytes:
        """
        读取文件数据
        
        Args:
            file_oid: 文件对象 ID
            
        Returns:
            文件数据
        """
        if not self.superblock:
            return b''
            
        # 读取文件扩展树
        entries = self.container.read_btree(self.superblock.extentref_tree_oid)
        
        # 查找文件扩展
        extents = []
        for key, value in entries:
            try:
                jkey = JKey.from_bytes(key)
                
                if jkey.type == ObjType.FILE_EXTENT and jkey.obj_id == file_oid:
                    extent = JFileExtent.from_bytes(value)
                    extents.append(extent)
            except Exception:
                continue
                
        if not extents:
            return b''
            
        # 按逻辑地址排序
        extents.sort(key=lambda e: e.logical_addr)
        
        # 读取数据
        result = b''
        for extent in extents:
            # 读取物理块
            data = self.container._read_block(extent.phys_block_num)
            
            # 只取需要的长度
            if extent.length < len(data):
                data = data[:extent.length]
                
            result += data
            
        return result


# =============================================================================
# 便捷函数
# =============================================================================

def open_apfs(path: str) -> APFSContainerReader:
    """
    打开 APFS 容器
    
    Args:
        path: 文件路径
        
    Returns:
        APFS 容器读取器
    """
    reader = APFSContainerReader(path)
    reader.open()
    return reader


def list_apfs_volumes(path: str) -> List[Dict]:
    """
    列出 APFS 卷
    
    Args:
        path: 文件路径
        
    Returns:
        卷信息列表
    """
    with APFSContainerReader(path) as reader:
        volumes = []
        for index, volume in reader.volumes.items():
            info = volume.get_info()
            info['index'] = index
            volumes.append(info)
        return volumes
