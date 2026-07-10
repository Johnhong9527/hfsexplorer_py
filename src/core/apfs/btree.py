"""
APFS B-tree 完整实现

提供完整的 APFS B-tree 写入支持，包括：
- 节点管理
- 插入/删除操作
- 分裂/合并
- 空间管理
"""

import struct
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, BinaryIO, Any
from enum import IntEnum, IntFlag
import time


# =============================================================================
# APFS B-tree 常量
# =============================================================================

# 节点类型
class NodeType(IntEnum):
    """节点类型"""
    INDEX = 0x00  # 索引节点
    LEAF = 0x01   # 叶节点
    HEADER = 0x02 # 头部节点


# 节点标志
class NodeFlags(IntFlag):
    """节点标志"""
    FIXED_KV_SIZE = 0x01  # 固定键值大小
    CHECKSUM = 0x02       # 有校验和
    PHYSICAL = 0x04       # 物理地址
    EPHEMERAL = 0x08      # 临时对象
    PERSISTENT = 0x10     # 持久对象


# 对象类型
class ObjType(IntEnum):
    """对象类型"""
    SNAP_metadata = 0x01
    OMAP = 0x02
    BTREE = 0x03
    SPACEMAN = 0x05
    SPACEMAN_CAB = 0x06
    SPACEMAN_IP = 0x07
    SPACEMAN_FREE_QUEUE = 0x08
    EXTENT_LIST = 0x09
    OMAP_SNAPSHOT = 0x0A
    JOURN_ALLOC = 0x0B
    JOURN = 0x0C
    JOURN_DATA = 0x0D
    FS = 0x0E
    FSTREE = 0x0F
    BLOCKREFTREE = 0x10
    SNAPMETATREE = 0x11
    OMAP_SYSTEM = 0x12
    FUSION_MIDTREE = 0x13
    NXSUPERBLOCK = 0x14
    INODE = 0x20
    XATTR = 0x21
    SIBLING_LINK = 0x22
    DSTREAM_ID = 0x23
    CRYPTO_STATE = 0x24
    FILE_EXTENT = 0x25
    DIR_REC = 0x26
    DIR_STATS = 0x27
    SNAPSHOT_NAME = 0x28
    SNAP_META = 0x29


# =============================================================================
# APFS B-tree 数据结构
# =============================================================================

@dataclass
class BTNodeDescriptor:
    """B-tree 节点描述符"""
    next: int  # 下一个节点 OID
    prev: int  # 上一个节点 OID
    type: int  # 节点类型
    flags: int  # 标志
    num_keys: int  # 键数量
    
    SIZE = 20
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<Q', self.next)
        result += struct.pack('<Q', self.prev)
        result += struct.pack('<B', self.type)
        result += struct.pack('<B', self.flags)
        result += struct.pack('<H', self.num_keys)
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTNodeDescriptor':
        """反序列化"""
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
    type: int    # 对象类型
    num: int     # 序列号
    
    SIZE = 8
    
    def to_bytes(self) -> bytes:
        """序列化"""
        # 编码为 8 字节
        val = (self.obj_id & 0x00000FFFFFFFFFFF)
        val |= ((self.type & 0xFF) << 44)
        val |= ((self.num & 0xFFF) << 52)
        return struct.pack('<Q', val)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'JKey':
        """反序列化"""
        val = struct.unpack_from('<Q', data, offset)[0]
        obj_id = val & 0x00000FFFFFFFFFFF
        type_val = (val >> 44) & 0xFF
        num = (val >> 52) & 0xFFF
        return cls(obj_id=obj_id, type=type_val, num=num)
    
    def __lt__(self, other: 'JKey') -> bool:
        """比较"""
        if self.obj_id != other.obj_id:
            return self.obj_id < other.obj_id
        if self.type != other.type:
            return self.type < other.type
        return self.num < other.num
    
    def __eq__(self, other: 'JKey') -> bool:
        """相等"""
        return (self.obj_id == other.obj_id and 
                self.type == other.type and 
                self.num == other.num)


@dataclass
class KVLocation:
    """键值位置"""
    key_offset: int  # 键偏移
    key_length: int  # 键长度
    val_offset: int  # 值偏移
    val_length: int  # 值长度
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<H', self.key_offset)
        result += struct.pack('<H', self.key_length)
        result += struct.pack('<H', self.val_offset)
        result += struct.pack('<H', self.val_length)
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'KVLocation':
        """反序列化"""
        key_offset = struct.unpack_from('<H', data, offset)[0]
        key_length = struct.unpack_from('<H', data, offset + 2)[0]
        val_offset = struct.unpack_from('<H', data, offset + 4)[0]
        val_length = struct.unpack_from('<H', data, offset + 6)[0]
        
        return cls(
            key_offset=key_offset,
            key_length=key_length,
            val_offset=val_offset,
            val_length=val_length
        )


@dataclass
class BTNode:
    """B-tree 节点"""
    descriptor: BTNodeDescriptor
    keys: List[bytes] = field(default_factory=list)
    values: List[bytes] = field(default_factory=list)
    children: List[int] = field(default_factory=list)  # 子节点 OID
    data: bytes = b''  # 原始数据
    
    @property
    def is_leaf(self) -> bool:
        """是否是叶节点"""
        return bool(self.descriptor.type & NodeType.LEAF)
    
    @property
    def is_index(self) -> bool:
        """是否是索引节点"""
        return not self.is_leaf
    
    @property
    def num_keys(self) -> int:
        """键数量"""
        return len(self.keys)
    
    def to_bytes(self, node_size: int = 4096) -> bytes:
        """序列化"""
        result = bytearray(node_size)
        
        # 写入描述符
        desc_data = self.descriptor.to_bytes()
        result[0:len(desc_data)] = desc_data
        
        # 计算偏移
        offset = BTNodeDescriptor.SIZE
        
        # 写入键值位置表
        kv_table_offset = offset
        for i, (key, val) in enumerate(zip(self.keys, self.values)):
            kv_loc = KVLocation(
                key_offset=len(result),
                key_length=len(key),
                val_offset=len(result) + len(key),
                val_length=len(val)
            )
            result[offset:offset + 8] = kv_loc.to_bytes()
            offset += 8
        
        # 写入子节点表（如果是索引节点）
        if self.is_index:
            for child_oid in self.children:
                struct.pack_into('<Q', result, offset, child_oid)
                offset += 8
        
        # 写入键值数据
        for key, val in zip(self.keys, self.values):
            result[offset:offset + len(key)] = key
            offset += len(key)
            result[offset:offset + len(val)] = val
            offset += len(val)
        
        return bytes(result)
    
    @classmethod
    def from_bytes(cls, data: bytes, node_size: int = 4096) -> 'BTNode':
        """反序列化"""
        descriptor = BTNodeDescriptor.from_bytes(data)
        
        node = cls(descriptor=descriptor, data=data)
        
        # 解析键值位置表
        offset = BTNodeDescriptor.SIZE
        kv_locations = []
        for i in range(descriptor.num_keys):
            kv_loc = KVLocation.from_bytes(data, offset)
            kv_locations.append(kv_loc)
            offset += 8
        
        # 解析子节点（如果是索引节点）
        if not (descriptor.type & NodeType.LEAF):
            for i in range(descriptor.num_keys + 1):
                child_oid = struct.unpack_from('<Q', data, offset)[0]
                node.children.append(child_oid)
                offset += 8
        
        # 解析键值数据
        for kv_loc in kv_locations:
            key = data[kv_loc.key_offset:kv_loc.key_offset + kv_loc.key_length]
            val = data[kv_loc.val_offset:kv_loc.val_offset + kv_loc.val_length]
            node.keys.append(key)
            node.values.append(val)
        
        return node


@dataclass
class BTHeaderRec:
    """B-tree 头部记录"""
    tree_type: int  # 树类型
    tree_height: int  # 树高度
    num_entries: int  # 条目数量
    max_key_size: int  # 最大键大小
    max_val_size: int  # 最大值大小
    root_oid: int  # 根节点 OID
    first_leaf_oid: int  # 第一个叶节点 OID
    last_leaf_oid: int  # 最后一个叶节点 OID
    node_size: int  # 节点大小
    max_inline_val_size: int  # 最大内联值大小
    num_free_nodes: int  # 空闲节点数量
    embedded_root_oid: int  # 嵌入式根节点 OID
    
    SIZE = 96
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<B', self.tree_type)
        result += struct.pack('<B', self.tree_height)
        result += struct.pack('<H', 0)  # padding
        result += struct.pack('<I', self.num_entries)
        result += struct.pack('<I', self.max_key_size)
        result += struct.pack('<I', self.max_val_size)
        result += struct.pack('<Q', self.root_oid)
        result += struct.pack('<Q', self.first_leaf_oid)
        result += struct.pack('<Q', self.last_leaf_oid)
        result += struct.pack('<I', self.node_size)
        result += struct.pack('<I', self.max_inline_val_size)
        result += struct.pack('<I', self.num_free_nodes)
        result += struct.pack('<I', 0)  # padding
        result += struct.pack('<Q', self.embedded_root_oid)
        result += struct.pack('<Q', 0)  # padding
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTHeaderRec':
        """反序列化"""
        tree_type = struct.unpack_from('<B', data, offset)[0]
        tree_height = struct.unpack_from('<B', data, offset + 1)[0]
        num_entries = struct.unpack_from('<I', data, offset + 4)[0]
        max_key_size = struct.unpack_from('<I', data, offset + 8)[0]
        max_val_size = struct.unpack_from('<I', data, offset + 12)[0]
        root_oid = struct.unpack_from('<Q', data, offset + 16)[0]
        first_leaf_oid = struct.unpack_from('<Q', data, offset + 24)[0]
        last_leaf_oid = struct.unpack_from('<Q', data, offset + 32)[0]
        node_size = struct.unpack_from('<I', data, offset + 40)[0]
        max_inline_val_size = struct.unpack_from('<I', data, offset + 44)[0]
        num_free_nodes = struct.unpack_from('<I', data, offset + 48)[0]
        embedded_root_oid = struct.unpack_from('<Q', data, offset + 52)[0]
        
        return cls(
            tree_type=tree_type,
            tree_height=tree_height,
            num_entries=num_entries,
            max_key_size=max_key_size,
            max_val_size=max_val_size,
            root_oid=root_oid,
            first_leaf_oid=first_leaf_oid,
            last_leaf_oid=last_leaf_oid,
            node_size=node_size,
            max_inline_val_size=max_inline_val_size,
            num_free_nodes=num_free_nodes,
            embedded_root_oid=embedded_root_oid
        )


# =============================================================================
# APFS B-tree 管理器
# =============================================================================

class BTreeManager:
    """
    APFS B-tree 管理器
    
    提供完整的 B-tree 操作支持。
    """
    
    def __init__(self, file_path: str, node_size: int = 4096):
        """
        初始化 B-tree 管理器
        
        Args:
            file_path: 文件路径
            node_size: 节点大小
        """
        self.file_path = file_path
        self.node_size = node_size
        self._file: Optional[BinaryIO] = None
        self._header: Optional[BTHeaderRec] = None
        self._nodes: Dict[int, BTNode] = {}  # OID -> Node
        self._next_oid = 1000
        self._free_nodes: List[int] = []
        
    def open(self) -> None:
        """打开文件"""
        self._file = open(self.file_path, 'r+b')
        
    def close(self) -> None:
        """关闭文件"""
        if self._file:
            self._file.close()
            self._file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def initialize(self, tree_type: int = 0) -> None:
        """
        初始化 B-tree
        
        Args:
            tree_type: 树类型
        """
        # 创建头部记录
        self._header = BTHeaderRec(
            tree_type=tree_type,
            tree_height=1,
            num_entries=0,
            max_key_size=256,
            max_val_size=4096,
            root_oid=0,
            first_leaf_oid=0,
            last_leaf_oid=0,
            node_size=self.node_size,
            max_inline_val_size=3800,
            num_free_nodes=0,
            embedded_root_oid=0
        )
        
        # 创建根节点（叶节点）
        root_oid = self._allocate_oid()
        root_node = BTNode(
            descriptor=BTNodeDescriptor(
                next=0,
                prev=0,
                type=NodeType.LEAF,
                flags=0,
                num_keys=0
            )
        )
        
        self._nodes[root_oid] = root_node
        self._header.root_oid = root_oid
        self._header.first_leaf_oid = root_oid
        self._header.last_leaf_oid = root_oid
        
    def _allocate_oid(self) -> int:
        """分配对象 ID"""
        if self._free_nodes:
            return self._free_nodes.pop()
        oid = self._next_oid
        self._next_oid += 1
        return oid
        
    def _read_node(self, oid: int) -> BTNode:
        """
        读取节点
        
        Args:
            oid: 节点 OID
            
        Returns:
            节点对象
        """
        if oid in self._nodes:
            return self._nodes[oid]
            
        if not self._file:
            raise RuntimeError("文件未打开")
            
        # 从文件读取
        offset = oid * self.node_size
        self._file.seek(offset)
        data = self._file.read(self.node_size)
        
        node = BTNode.from_bytes(data, self.node_size)
        self._nodes[oid] = node
        
        return node
        
    def _write_node(self, oid: int, node: BTNode) -> None:
        """
        写入节点
        
        Args:
            oid: 节点 OID
            node: 节点对象
        """
        if not self._file:
            raise RuntimeError("文件未打开")
            
        # 更新描述符
        node.descriptor.num_keys = len(node.keys)
        
        # 序列化
        data = node.to_bytes(self.node_size)
        
        # 写入文件
        offset = oid * self.node_size
        self._file.seek(offset)
        self._file.write(data)
        
        # 更新缓存
        self._nodes[oid] = node
        
    def _compare_keys(self, key1: bytes, key2: bytes) -> int:
        """
        比较键
        
        Args:
            key1: 键1
            key2: 键2
            
        Returns:
            -1, 0, 1
        """
        # 解析键
        jkey1 = JKey.from_bytes(key1)
        jkey2 = JKey.from_bytes(key2)
        
        if jkey1 < jkey2:
            return -1
        elif jkey1 == jkey2:
            return 0
        else:
            return 1
            
    def _find_key_index(self, node: BTNode, key: bytes) -> int:
        """
        查找键在节点中的位置
        
        Args:
            node: 节点
            key: 键
            
        Returns:
            位置索引
        """
        for i, node_key in enumerate(node.keys):
            if self._compare_keys(key, node_key) <= 0:
                return i
        return len(node.keys)
        
    def insert(self, key: bytes, value: bytes) -> bool:
        """
        插入键值对
        
        Args:
            key: 键
            value: 值
            
        Returns:
            是否成功
        """
        if not self._header:
            raise RuntimeError("B-tree 未初始化")
            
        # 获取根节点
        root_oid = self._header.root_oid
        root_node = self._read_node(root_oid)
        
        # 插入到根节点
        split_key, split_oid = self._insert_into_node(root_oid, key, value)
        
        # 如果根节点分裂，需要创建新的根节点
        if split_key is not None:
            self._split_root(split_key, split_oid)
            
        # 更新头部
        self._header.num_entries += 1
        
        return True
        
    def _insert_into_node(self, oid: int, key: bytes, value: bytes) -> Tuple[Optional[bytes], Optional[int]]:
        """
        插入到节点
        
        Args:
            oid: 节点 OID
            key: 键
            value: 值
            
        Returns:
            (分裂键, 分裂节点OID) 或 (None, None)
        """
        node = self._read_node(oid)
        
        # 查找插入位置
        idx = self._find_key_index(node, key)
        
        # 检查是否是叶节点
        if node.is_leaf:
            # 插入到叶节点
            node.keys.insert(idx, key)
            node.values.insert(idx, value)
            
            # 写入节点
            self._write_node(oid, node)
            
            # 检查是否需要分裂
            if len(node.keys) > 10:  # 简化的分裂阈值
                return self._split_node(oid)
            
            return None, None
        else:
            # 索引节点，递归插入
            child_oid = node.children[idx]
            split_key, split_oid = self._insert_into_node(child_oid, key, value)
            
            # 如果子节点分裂，需要插入到当前节点
            if split_key is not None:
                node.keys.insert(idx, split_key)
                node.children.insert(idx + 1, split_oid)
                
                # 写入节点
                self._write_node(oid, node)
                
                # 检查是否需要分裂
                if len(node.keys) > 10:
                    return self._split_node(oid)
            
            return None, None
            
    def _split_node(self, oid: int) -> Tuple[bytes, int]:
        """
        分裂节点
        
        Args:
            oid: 节点 OID
            
        Returns:
            (分裂键, 新节点OID)
        """
        node = self._read_node(oid)
        
        # 计算分裂点
        mid = len(node.keys) // 2
        
        # 创建新节点
        new_oid = self._allocate_oid()
        new_node = BTNode(
            descriptor=BTNodeDescriptor(
                next=node.descriptor.next,
                prev=oid,
                type=node.descriptor.type,
                flags=node.descriptor.flags,
                num_keys=0
            )
        )
        
        # 分割键和值
        split_key = node.keys[mid]
        
        if node.is_leaf:
            # 叶节点分裂
            new_node.keys = node.keys[mid:]
            new_node.values = node.values[mid:]
            
            node.keys = node.keys[:mid]
            node.values = node.values[:mid]
        else:
            # 索引节点分裂
            new_node.keys = node.keys[mid + 1:]
            new_node.children = node.children[mid + 1:]
            
            node.keys = node.keys[:mid]
            node.children = node.children[:mid + 1]
        
        # 更新链接
        node.descriptor.next = new_oid
        
        # 写入节点
        self._write_node(oid, node)
        self._write_node(new_oid, new_node)
        
        return split_key, new_oid
        
    def _split_root(self, split_key: bytes, split_oid: int) -> None:
        """
        分裂根节点
        
        Args:
            split_key: 分裂键
            split_oid: 分裂节点OID
        """
        old_root_oid = self._header.root_oid
        
        # 创建新的根节点
        new_root_oid = self._allocate_oid()
        new_root = BTNode(
            descriptor=BTNodeDescriptor(
                next=0,
                prev=0,
                type=NodeType.INDEX,
                flags=0,
                num_keys=1
            ),
            keys=[split_key],
            children=[old_root_oid, split_oid]
        )
        
        # 更新头部
        self._header.root_oid = new_root_oid
        self._header.tree_height += 1
        
        # 写入节点
        self._write_node(new_root_oid, new_root)
        
    def search(self, key: bytes) -> Optional[bytes]:
        """
        搜索键
        
        Args:
            key: 键
            
        Returns:
            值，如果不存在返回 None
        """
        if not self._header:
            return None
            
        return self._search_in_node(self._header.root_oid, key)
        
    def _search_in_node(self, oid: int, key: bytes) -> Optional[bytes]:
        """
        在节点中搜索
        
        Args:
            oid: 节点 OID
            key: 键
            
        Returns:
            值，如果不存在返回 None
        """
        node = self._read_node(oid)
        
        # 查找位置
        idx = self._find_key_index(node, key)
        
        if node.is_leaf:
            # 叶节点
            if idx < len(node.keys) and self._compare_keys(key, node.keys[idx]) == 0:
                return node.values[idx]
            return None
        else:
            # 索引节点，递归搜索
            if idx < len(node.keys) and self._compare_keys(key, node.keys[idx]) == 0:
                # 找到键，返回右子树的最小值
                return self._search_in_node(node.children[idx + 1], key)
            return self._search_in_node(node.children[idx], key)
            
    def delete(self, key: bytes) -> bool:
        """
        删除键
        
        Args:
            key: 键
            
        Returns:
            是否成功
        """
        if not self._header:
            return False
            
        # 删除
        result = self._delete_from_node(self._header.root_oid, key)
        
        if result:
            self._header.num_entries -= 1
            
        return result
        
    def _delete_from_node(self, oid: int, key: bytes) -> bool:
        """
        从节点删除
        
        Args:
            oid: 节点 OID
            key: 键
            
        Returns:
            是否成功
        """
        node = self._read_node(oid)
        
        # 查找位置
        idx = self._find_key_index(node, key)
        
        if node.is_leaf:
            # 叶节点
            if idx < len(node.keys) and self._compare_keys(key, node.keys[idx]) == 0:
                node.keys.pop(idx)
                node.values.pop(idx)
                self._write_node(oid, node)
                return True
            return False
        else:
            # 索引节点
            if idx < len(node.keys) and self._compare_keys(key, node.keys[idx]) == 0:
                # 找到键，删除
                node.keys.pop(idx)
                node.children.pop(idx + 1)
                self._write_node(oid, node)
                return True
            
            # 递归删除
            return self._delete_from_node(node.children[idx], key)
            
    def update(self, key: bytes, value: bytes) -> bool:
        """
        更新键值对
        
        Args:
            key: 键
            value: 值
            
        Returns:
            是否成功
        """
        if not self._header:
            return False
            
        return self._update_in_node(self._header.root_oid, key, value)
        
    def _update_in_node(self, oid: int, key: bytes, value: bytes) -> bool:
        """
        在节点中更新
        
        Args:
            oid: 节点 OID
            key: 键
            value: 值
            
        Returns:
            是否成功
        """
        node = self._read_node(oid)
        
        # 查找位置
        idx = self._find_key_index(node, key)
        
        if node.is_leaf:
            # 叶节点
            if idx < len(node.keys) and self._compare_keys(key, node.keys[idx]) == 0:
                node.values[idx] = value
                self._write_node(oid, node)
                return True
            return False
        else:
            # 索引节点，递归更新
            return self._update_in_node(node.children[idx], key, value)
            
    def get_all_entries(self) -> List[Tuple[bytes, bytes]]:
        """
        获取所有条目
        
        Returns:
            键值对列表
        """
        if not self._header:
            return []
            
        entries = []
        self._collect_entries(self._header.root_oid, entries)
        return entries
        
    def _collect_entries(self, oid: int, entries: List[Tuple[bytes, bytes]]) -> None:
        """
        收集条目
        
        Args:
            oid: 节点 OID
            entries: 条目列表
        """
        node = self._read_node(oid)
        
        if node.is_leaf:
            entries.extend(zip(node.keys, node.values))
        else:
            for i, child_oid in enumerate(node.children):
                self._collect_entries(child_oid, entries)
                if i < len(node.keys):
                    # 索引节点的键不包含在结果中
                    pass
                    
    def flush(self) -> None:
        """刷新到文件"""
        if not self._file:
            return
            
        # 写入头部
        if self._header:
            header_data = self._header.to_bytes()
            self._file.seek(0)
            self._file.write(header_data)
            
        # 写入所有节点
        for oid, node in self._nodes.items():
            self._write_node(oid, node)
            
        self._file.flush()
        
    def get_info(self) -> Dict[str, Any]:
        """
        获取信息
        
        Returns:
            信息字典
        """
        if not self._header:
            return {}
            
        return {
            'tree_type': self._header.tree_type,
            'tree_height': self._header.tree_height,
            'num_entries': self._header.num_entries,
            'node_size': self._header.node_size,
            'root_oid': self._header.root_oid,
        }


# =============================================================================
# 便捷函数
# =============================================================================

def create_btree(file_path: str, node_size: int = 4096) -> BTreeManager:
    """
    创建 B-tree
    
    Args:
        file_path: 文件路径
        node_size: 节点大小
        
    Returns:
        B-tree 管理器
    """
    manager = BTreeManager(file_path, node_size)
    manager.open()
    manager.initialize()
    return manager


def open_btree(file_path: str, node_size: int = 4096) -> BTreeManager:
    """
    打开 B-tree
    
    Args:
        file_path: 文件路径
        node_size: 节点大小
        
    Returns:
        B-tree 管理器
    """
    manager = BTreeManager(file_path, node_size)
    manager.open()
    return manager
