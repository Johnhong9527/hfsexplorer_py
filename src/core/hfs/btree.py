"""
HFS+ B-tree 模块

实现 B-tree 节点描述符、头记录和遍历算法。
"""

import struct
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Callable, BinaryIO

from .constants import (
    BTreeNodeKind,
    BTREE_NODE_DESCRIPTOR_SIZE,
    BTREE_HEADER_RECORD_SIZE,
)


# =============================================================================
# 节点描述符 (14 bytes)
# =============================================================================

@dataclass
class BTNodeDescriptor:
    """
    B-tree 节点描述符
    
    位于每个节点的开头，14 字节。
    
    Attributes:
        fLink: 前向链接（下一个同类型节点的节点号，0 表示最后一个）
        bLink: 后向链接（上一个同类型节点的节点号，0 表示第一个）
        kind: 节点类型（-1=叶, 0=索引, 1=头, 2=位图）
        height: 子树高度（叶=1, 索引=子高度+1, 头/位图=0）
        numRecords: 此节点中的记录数
        reserved: 保留字段
    """
    fLink: int       # UInt32 - 前向链接
    bLink: int       # UInt32 - 后向链接
    kind: int        # Int8 - 节点类型
    height: int      # UInt8 - 子树高度
    numRecords: int  # UInt16 - 记录数
    reserved: int    # UInt16 - 保留
    
    @property
    def node_type(self) -> BTreeNodeKind:
        """获取节点类型枚举"""
        if self.kind == -1 or self.kind == 0xFF:
            return BTreeNodeKind.LEAF
        elif self.kind == 0:
            return BTreeNodeKind.INDEX
        elif self.kind == 1:
            return BTreeNodeKind.HEADER
        elif self.kind == 2:
            return BTreeNodeKind.MAP
        else:
            raise ValueError(f"未知节点类型: {self.kind}")
    
    @property
    def is_leaf(self) -> bool:
        """是否为叶节点"""
        return self.node_type == BTreeNodeKind.LEAF
    
    @property
    def is_index(self) -> bool:
        """是否为索引节点"""
        return self.node_type == BTreeNodeKind.INDEX
    
    @property
    def is_header(self) -> bool:
        """是否为头节点"""
        return self.node_type == BTreeNodeKind.HEADER
    
    @property
    def is_map(self) -> bool:
        """是否为位图节点"""
        return self.node_type == BTreeNodeKind.MAP
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        return struct.pack(
            '>II Bb HH',
            self.fLink,
            self.bLink,
            self.kind & 0xFF,  # 转换为无符号字节
            self.height,
            self.numRecords,
            self.reserved
        )
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTNodeDescriptor':
        """从字节序列解析"""
        if len(data) < offset + BTREE_NODE_DESCRIPTOR_SIZE:
            raise ValueError(f"数据不足: 需要 {BTREE_NODE_DESCRIPTOR_SIZE} 字节")
        
        fLink, bLink, kind_raw, height, numRecords, reserved = struct.unpack_from(
            '>II Bb HH', data, offset
        )
        
        # 将无符号字节转换为有符号
        kind = kind_raw if kind_raw < 128 else kind_raw - 256
        
        return cls(
            fLink=fLink,
            bLink=bLink,
            kind=kind,
            height=height,
            numRecords=numRecords,
            reserved=reserved
        )
    
    def __str__(self) -> str:
        return (f"BTNodeDescriptor(type={self.node_type.name}, "
                f"height={self.height}, records={self.numRecords}, "
                f"fLink={self.fLink}, bLink={self.bLink})")


# =============================================================================
# 头记录 (106 bytes)
# =============================================================================

@dataclass
class BTHeaderRec:
    """
    B-tree 头记录
    
    位于头节点（节点 0）中，106 字节。
    
    Attributes:
        treeDepth: 树的当前深度
        rootNode: 根节点的节点号
        leafRecords: 叶记录总数
        firstLeafNode: 第一个叶节点的节点号
        lastLeafNode: 最后一个叶节点的节点号
        nodeSize: 每个节点的大小（字节）
        maxKeyLength: 最大键长度
        totalNodes: 树中的节点总数
        freeNodes: 空闲节点数
        reserved1: 保留字段
        clumpSize: Clump 大小
        btreeType: B-tree 类型
        keyCompareType: 键比较类型
        attributes: 属性标志
    """
    treeDepth: int        # UInt16 - 树深度
    rootNode: int         # UInt32 - 根节点号
    leafRecords: int      # UInt32 - 叶记录数
    firstLeafNode: int    # UInt32 - 第一个叶节点
    lastLeafNode: int     # UInt32 - 最后一个叶节点
    nodeSize: int         # UInt16 - 节点大小
    maxKeyLength: int     # UInt16 - 最大键长度
    totalNodes: int       # UInt32 - 总节点数
    freeNodes: int        # UInt32 - 空闲节点数
    reserved1: int        # UInt16 - 保留
    clumpSize: int        # UInt32 - Clump 大小
    btreeType: int        # UInt8 - B-tree 类型
    keyCompareType: int   # UInt8 - 键比较类型
    attributes: int       # UInt32 - 属性标志
    
    @property
    def is_bad_close(self) -> bool:
        """B-tree 是否未正确关闭"""
        return bool(self.attributes & (1 << 0))
    
    @property
    def big_keys(self) -> bool:
        """是否使用大键（键长度 > 255 字节）"""
        return bool(self.attributes & (1 << 1))
    
    @property
    def variable_index_keys(self) -> bool:
        """是否使用变长索引键"""
        return bool(self.attributes & (1 << 2))
    
    @property
    def is_case_sensitive(self) -> bool:
        """是否区分大小写"""
        return self.keyCompareType == 0xBC  # kHFSBinaryCompare
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        # 打包主要字段
        result = struct.pack(
            '>H IIII HH II H I BB I',
            self.treeDepth,
            self.rootNode,
            self.leafRecords,
            self.firstLeafNode,
            self.lastLeafNode,
            self.nodeSize,
            self.maxKeyLength,
            self.totalNodes,
            self.freeNodes,
            self.reserved1,
            self.clumpSize,
            self.btreeType,
            self.keyCompareType,
            self.attributes
        )
        
        # 添加保留字段 (16 x UInt32 = 64 bytes)
        result += b'\x00' * 64
        
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTHeaderRec':
        """从字节序列解析"""
        if len(data) < offset + BTREE_HEADER_RECORD_SIZE:
            raise ValueError(f"数据不足: 需要 {BTREE_HEADER_RECORD_SIZE} 字节")
        
        (
            treeDepth,
            rootNode,
            leafRecords,
            firstLeafNode,
            lastLeafNode,
            nodeSize,
            maxKeyLength,
            totalNodes,
            freeNodes,
            reserved1,
            clumpSize,
            btreeType,
            keyCompareType,
            attributes
        ) = struct.unpack_from('>H IIII HH II H I BB I', data, offset)
        
        return cls(
            treeDepth=treeDepth,
            rootNode=rootNode,
            leafRecords=leafRecords,
            firstLeafNode=firstLeafNode,
            lastLeafNode=lastLeafNode,
            nodeSize=nodeSize,
            maxKeyLength=maxKeyLength,
            totalNodes=totalNodes,
            freeNodes=freeNodes,
            reserved1=reserved1,
            clumpSize=clumpSize,
            btreeType=btreeType,
            keyCompareType=keyCompareType,
            attributes=attributes
        )
    
    def __str__(self) -> str:
        return (f"BTHeaderRec(depth={self.treeDepth}, root={self.rootNode}, "
                f"leaves={self.leafRecords}, nodeSize={self.nodeSize}, "
                f"totalNodes={self.totalNodes}, freeNodes={self.freeNodes})")


# =============================================================================
# 节点偏移表解析
# =============================================================================

@dataclass
class BTreeNode:
    """
    B-tree 节点
    
    包含节点描述符和记录偏移表。
    
    Attributes:
        descriptor: 节点描述符
        node_size: 节点大小
        offsets: 记录偏移表（包含 numRecords + 1 个条目）
        raw_data: 原始节点数据
    """
    descriptor: BTNodeDescriptor
    node_size: int
    offsets: List[int]
    raw_data: bytes
    
    @property
    def num_records(self) -> int:
        """记录数"""
        return self.descriptor.numRecords
    
    def get_record_offset(self, index: int) -> int:
        """获取记录的偏移量"""
        if index < 0 or index >= self.num_records:
            raise IndexError(f"记录索引超出范围: {index}")
        return self.offsets[index]
    
    def get_record_length(self, index: int) -> int:
        """获取记录的长度"""
        if index < 0 or index >= self.num_records:
            raise IndexError(f"记录索引超出范围: {index}")
        return self.offsets[index + 1] - self.offsets[index]
    
    def get_record_data(self, index: int) -> bytes:
        """获取记录的数据"""
        offset = self.get_record_offset(index)
        length = self.get_record_length(index)
        return self.raw_data[offset:offset + length]
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTreeNode':
        """从字节序列解析"""
        if len(data) < offset + BTREE_NODE_DESCRIPTOR_SIZE:
            raise ValueError(f"数据不足: 需要至少 {BTREE_NODE_DESCRIPTOR_SIZE} 字节")
        
        # 解析节点描述符
        descriptor = BTNodeDescriptor.from_bytes(data, offset)
        node_size = len(data) - offset
        
        # 解析偏移表（从节点末尾反向读取）
        num_records = descriptor.numRecords
        offsets = []
        
        # 偏移表存储在节点末尾，反向排列
        # 有 numRecords + 1 个条目（最后一个指向空闲空间）
        for i in range(num_records + 1):
            off = struct.unpack_from(
                '>H', data, offset + node_size - ((i + 1) * 2)
            )[0]
            offsets.append(off)
        
        # 反转，使索引 0 = 第一个记录的偏移
        offsets.reverse()
        
        return cls(
            descriptor=descriptor,
            node_size=node_size,
            offsets=offsets,
            raw_data=data[offset:offset + node_size]
        )
    
    def __str__(self) -> str:
        return (f"BTreeNode({self.descriptor}, "
                f"offsets={self.offsets[:min(5, len(self.offsets))]}...)")


# =============================================================================
# 索引记录和叶记录
# =============================================================================

@dataclass
class BTIndexRecord:
    """
    B-tree 索引记录
    
    包含键和子节点指针。
    
    Attributes:
        key_data: 原始键数据
        child_node: 子节点号
        offset: 记录在节点中的偏移量
        length: 记录总长度
    """
    key_data: bytes
    child_node: int
    offset: int
    length: int


@dataclass
class BTLeafRecord:
    """
    B-tree 叶记录
    
    包含键和记录数据。
    
    Attributes:
        key_data: 原始键数据
        record_data: 记录数据（不包括键）
        offset: 记录在节点中的偏移量
        length: 记录总长度
    """
    key_data: bytes
    record_data: bytes
    offset: int
    length: int


# =============================================================================
# B-tree 文件遍历
# =============================================================================

class BTreeFile:
    """
    HFS+ B-tree 文件读取器
    
    实现从根到叶的遍历算法。
    
    Usage:
        btree = BTreeFile(stream, node_size=4096)
        header = btree.header
        records = btree.get_all_leaf_records()
    """
    
    def __init__(self, stream: BinaryIO, start_offset: int = 0,
                 node_size: int = 4096, parse_key_fn: Optional[Callable] = None):
        """
        初始化 B-tree 文件读取器
        
        Args:
            stream: 可 seek 的二进制流
            start_offset: B-tree 数据在流中的起始偏移量
            node_size: 节点大小（字节），默认 4096
            parse_key_fn: 可选的键解析函数
        """
        self.stream = stream
        self.start_offset = start_offset
        self._node_size = node_size
        self.parse_key_fn = parse_key_fn
        self._header: Optional[BTHeaderRec] = None
    
    @property
    def header(self) -> BTHeaderRec:
        """读取并缓存 B-tree 头记录"""
        if self._header is None:
            node = self._read_node(0)  # 节点 0 总是头节点
            if not node.descriptor.is_header:
                raise ValueError("节点 0 不是头节点!")
            
            # 头记录在节点的偏移 14 处（紧跟节点描述符）
            self._header = BTHeaderRec.from_bytes(node.raw_data, BTREE_NODE_DESCRIPTOR_SIZE)
            self._node_size = self._header.nodeSize
        
        return self._header
    
    @property
    def node_size(self) -> int:
        """获取节点大小"""
        return self._node_size
    
    def _read_node(self, node_number: int) -> BTreeNode:
        """读取并解析单个节点"""
        byte_offset = self.start_offset + node_number * self.node_size
        self.stream.seek(byte_offset)
        data = self.stream.read(self.node_size)
        
        if len(data) < self.node_size:
            raise IOError(f"读取不足: 期望 {self.node_size}, 实际 {len(data)}")
        
        return BTreeNode.from_bytes(data)
    
    def get_node(self, node_number: int) -> BTreeNode:
        """获取指定节点"""
        return self._read_node(node_number)
    
    def get_root_node(self) -> Optional[BTreeNode]:
        """获取根节点"""
        root_number = self.header.rootNode
        if root_number == 0:
            return None  # 空树
        return self._read_node(root_number)
    
    def list_leaf_nodes(self) -> List[BTreeNode]:
        """遍历所有叶节点（通过前向链接）"""
        h = self.header
        if h.firstLeafNode == 0:
            return []
        
        nodes = []
        node_number = h.firstLeafNode
        
        while node_number != 0:
            node = self._read_node(node_number)
            nodes.append(node)
            node_number = node.descriptor.fLink
        
        return nodes
    
    def get_all_leaf_records(self) -> List[BTLeafRecord]:
        """获取所有叶记录"""
        records = []
        
        for node in self.list_leaf_nodes():
            for i in range(node.num_records):
                offset = node.get_record_offset(i)
                length = node.get_record_length(i)
                data = node.get_record_data(i)
                
                # 假设键长度为 2 字节（UInt16 keyLength）
                key_length = struct.unpack_from('>H', data, 0)[0]
                key_data = data[:2 + key_length]
                record_data = data[2 + key_length:]
                
                records.append(BTLeafRecord(
                    key_data=key_data,
                    record_data=record_data,
                    offset=offset,
                    length=length
                ))
        
        return records
    
    def find_record(self, search_key_data: bytes) -> Optional[BTLeafRecord]:
        """
        查找匹配的叶记录
        
        从根到叶的 O(log n) 遍历。
        
        Args:
            search_key_data: 搜索键的原始数据
        
        Returns:
            匹配的叶记录，如果未找到则返回 None
        """
        h = self.header
        root_number = h.rootNode
        
        if root_number == 0:
            return None
        
        # 读取根节点
        current_node = self._read_node(root_number)
        
        # 通过索引节点下降
        while current_node.descriptor.is_index:
            matching_record = self._find_le_key(current_node, search_key_data)
            
            if matching_record is None:
                return None  # 键不在树中
            
            # 跟随子节点指针
            current_node = self._read_node(matching_record.child_node)
        
        # 到达叶节点 - 查找精确匹配
        if current_node.descriptor.is_leaf:
            for i in range(current_node.num_records):
                data = current_node.get_record_data(i)
                key_length = struct.unpack_from('>H', data, 0)[0]
                key_data = data[:2 + key_length]
                
                if key_data == search_key_data:
                    record_data = data[2 + key_length:]
                    return BTLeafRecord(
                        key_data=key_data,
                        record_data=record_data,
                        offset=current_node.get_record_offset(i),
                        length=current_node.get_record_length(i)
                    )
        
        return None
    
    def _find_le_key(self, node: BTreeNode, search_key_data: bytes) -> Optional[BTIndexRecord]:
        """
        查找最大键 <= search_key 的索引记录
        
        Args:
            node: 索引节点
            search_key_data: 搜索键数据
        
        Returns:
            匹配的索引记录
        """
        best = None
        
        for i in range(node.num_records):
            data = node.get_record_data(i)
            offset = node.get_record_offset(i)
            length = node.get_record_length(i)
            
            # 解析键长度
            key_length = struct.unpack_from('>H', data, 0)[0]
            key_data = data[:2 + key_length]
            
            # 子节点号在键之后
            child_node = struct.unpack_from('>I', data, 2 + key_length)[0]
            
            record = BTIndexRecord(
                key_data=key_data,
                child_node=child_node,
                offset=offset,
                length=length
            )
            
            # 如果键 <= 搜索键
            if key_data <= search_key_data:
                if best is None or key_data > best.key_data:
                    best = record
        
        return best


# =============================================================================
# Catalog B-tree
# =============================================================================

@dataclass
class HFSPlusCatalogKey:
    """
    HFS+ Catalog 键
    
    变长结构，最大 518 字节。
    
    Attributes:
        key_length: 键长度（4 + nodeName 字节长度）
        parent_id: 父文件夹 CNID
        node_name: 节点名称（UTF-16BE）
    """
    key_length: int
    parent_id: int
    node_name: str
    
    @property
    def occupied_size(self) -> int:
        """占用的字节数"""
        return 2 + self.key_length  # 2 字节 keyLength + 数据
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusCatalogKey':
        """从字节序列解析"""
        key_length = struct.unpack_from('>H', data, offset)[0]
        parent_id = struct.unpack_from('>I', data, offset + 2)[0]
        
        # 计算名称字节长度
        name_byte_len = key_length - 4
        if name_byte_len < 0:
            name_byte_len = 0
        
        # 解析 UTF-16BE 名称
        raw_name = data[offset + 6:offset + 6 + name_byte_len]
        node_name = raw_name.decode('utf-16-be') if name_byte_len > 0 else ""
        
        return cls(
            key_length=key_length,
            parent_id=parent_id,
            node_name=node_name
        )
    
    def __str__(self) -> str:
        return f"CatalogKey(parent={self.parent_id}, name='{self.node_name}')"


@dataclass
class HFSPlusCatalogFolder:
    """
    HFS+ Catalog 文件夹记录
    
    88 字节。
    
    Attributes:
        record_type: 记录类型 (0x0001)
        flags: 标志
        valence: 子项计数
        folder_id: 文件夹 CNID
        create_date: 创建日期
        content_mod_date: 内容修改日期
        attribute_mod_date: 属性修改日期
        access_date: 访问日期
        backup_date: 备份日期
        owner_id: 所有者 ID
        group_id: 组 ID
        admin_flags: 管理员标志
        owner_flags: 所有者标志
        file_mode: 文件模式
    """
    record_type: int
    flags: int
    valence: int
    folder_id: int
    create_date: int
    content_mod_date: int
    attribute_mod_date: int
    access_date: int
    backup_date: int
    owner_id: int
    group_id: int
    admin_flags: int
    owner_flags: int
    file_mode: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusCatalogFolder':
        """从字节序列解析"""
        (
            record_type,
            flags,
            valence,
            folder_id,
            create_date,
            content_mod_date,
            attribute_mod_date,
            access_date,
            backup_date,
            owner_id,
            group_id,
            admin_flags,
            owner_flags,
            file_mode
        ) = struct.unpack_from('>HHI I IIII IIII BBH', data, offset)
        
        return cls(
            record_type=record_type,
            flags=flags,
            valence=valence,
            folder_id=folder_id,
            create_date=create_date,
            content_mod_date=content_mod_date,
            attribute_mod_date=attribute_mod_date,
            access_date=access_date,
            backup_date=backup_date,
            owner_id=owner_id,
            group_id=group_id,
            admin_flags=admin_flags,
            owner_flags=owner_flags,
            file_mode=file_mode
        )


@dataclass
class HFSPlusCatalogFile:
    """
    HFS+ Catalog 文件记录
    
    248 字节。
    
    Attributes:
        record_type: 记录类型 (0x0002)
        flags: 标志
        file_id: 文件 CNID
        create_date: 创建日期
        content_mod_date: 内容修改日期
        attribute_mod_date: 属性修改日期
        access_date: 访问日期
        backup_date: 备份日期
        owner_id: 所有者 ID
        group_id: 组 ID
        admin_flags: 管理员标志
        owner_flags: 所有者标志
        file_mode: 文件模式
        data_fork_size: 数据分支逻辑大小
        data_fork_blocks: 数据分支总块数
    """
    record_type: int
    flags: int
    file_id: int
    create_date: int
    content_mod_date: int
    attribute_mod_date: int
    access_date: int
    backup_date: int
    owner_id: int
    group_id: int
    admin_flags: int
    owner_flags: int
    file_mode: int
    data_fork_size: int
    data_fork_blocks: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusCatalogFile':
        """从字节序列解析"""
        (
            record_type,
            flags,
            file_id,
            create_date,
            content_mod_date,
            attribute_mod_date,
            access_date,
            backup_date,
            owner_id,
            group_id,
            admin_flags,
            owner_flags,
            file_mode
        ) = struct.unpack_from('>HHI IIII IIII BBH', data, offset)
        
        # 数据分支在偏移 88 处
        data_fork_size = struct.unpack_from('>Q', data, offset + 88)[0]
        data_fork_blocks = struct.unpack_from('>I', data, offset + 96)[0]
        
        return cls(
            record_type=record_type,
            flags=flags,
            file_id=file_id,
            create_date=create_date,
            content_mod_date=content_mod_date,
            attribute_mod_date=attribute_mod_date,
            access_date=access_date,
            backup_date=backup_date,
            owner_id=owner_id,
            group_id=group_id,
            admin_flags=admin_flags,
            owner_flags=owner_flags,
            file_mode=file_mode,
            data_fork_size=data_fork_size,
            data_fork_blocks=data_fork_blocks
        )


# =============================================================================
# Catalog 记录类型常量
# =============================================================================

class CatalogRecordType(IntEnum):
    """Catalog 记录类型"""
    FOLDER = 0x0001        # 文件夹记录
    FILE = 0x0002          # 文件记录
    FOLDER_THREAD = 0x0003 # 文件夹线程记录
    FILE_THREAD = 0x0004   # 文件线程记录


# =============================================================================
# Extents Overflow
# =============================================================================

class ForkType(IntEnum):
    """Fork 类型"""
    DATA = 0x00      # 数据分支
    RESOURCE = 0xFF  # 资源分支


@dataclass
class HFSPlusExtentKey:
    """
    HFS+ Extents Overflow 键
    
    12 字节。
    
    Attributes:
        key_length: 键长度（总是 10）
        fork_type: Fork 类型（0=数据, 0xFF=资源）
        pad: 填充字节
        file_id: 文件 CNID
        start_block: 起始分配块号
    """
    key_length: int   # UInt16 - 总是 10
    fork_type: int    # UInt8 - 0=数据, 0xFF=资源
    pad: int          # UInt8 - 填充
    file_id: int      # UInt32 - 文件 CNID
    start_block: int  # UInt32 - 起始分配块
    
    @property
    def occupied_size(self) -> int:
        """占用的字节数"""
        return 2 + self.key_length  # 2 字节 keyLength + 数据
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusExtentKey':
        """从字节序列解析"""
        key_length, fork_type, pad, file_id, start_block = struct.unpack_from(
            '>HBBI I', data, offset
        )
        return cls(
            key_length=key_length,
            fork_type=fork_type,
            pad=pad,
            file_id=file_id,
            start_block=start_block
        )
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, HFSPlusExtentKey):
            return False
        return (self.file_id == other.file_id and
                self.fork_type == other.fork_type and
                self.start_block == other.start_block)
    
    def __lt__(self, other) -> bool:
        if self.file_id != other.file_id:
            return self.file_id < other.file_id
        if self.fork_type != other.fork_type:
            return self.fork_type < other.fork_type
        return self.start_block < other.start_block
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __str__(self) -> str:
        fork_type_str = "DATA" if self.fork_type == ForkType.DATA else "RESOURCE"
        return (f"ExtentKey(file={self.file_id}, fork={fork_type_str}, "
                f"startBlock={self.start_block})")


@dataclass
class HFSPlusExtentDescriptor:
    """
    HFS+ Extent 描述符
    
    8 字节。
    
    Attributes:
        start_block: 起始分配块号
        block_count: 分配块数量
    """
    start_block: int  # UInt32
    block_count: int  # UInt32
    
    @property
    def end_block(self) -> int:
        """结束块号（不包含）"""
        return self.start_block + self.block_count
    
    @property
    def is_empty(self) -> bool:
        """是否为空 extent"""
        return self.block_count == 0
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusExtentDescriptor':
        """从字节序列解析"""
        start_block, block_count = struct.unpack_from('>II', data, offset)
        return cls(start_block=start_block, block_count=block_count)
    
    def __str__(self) -> str:
        return f"Extent(start={self.start_block}, count={self.block_count})"


@dataclass
class HFSPlusExtentRecord:
    """
    HFS+ Extent 记录
    
    包含 8 个 Extent 描述符（64 字节）。
    
    Attributes:
        extents: Extent 描述符列表（最多 8 个）
    """
    extents: List[HFSPlusExtentDescriptor]
    
    @property
    def total_blocks(self) -> int:
        """总分配块数"""
        return sum(ext.block_count for ext in self.extents)
    
    @property
    def is_empty(self) -> bool:
        """是否为空记录"""
        return all(ext.is_empty for ext in self.extents)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusExtentRecord':
        """从字节序列解析"""
        extents = []
        for i in range(8):
            ext = HFSPlusExtentDescriptor.from_bytes(data, offset + i * 8)
            if not ext.is_empty:
                extents.append(ext)
        return cls(extents=extents)
    
    def __str__(self) -> str:
        return f"ExtentRecord({len(self.extents)} extents, {self.total_blocks} blocks)"


# =============================================================================
# Extents B-tree
# =============================================================================

class ExtentsBTree(BTreeFile):
    """
    Extents Overflow B-tree 读取器
    
    继承自 BTreeFile，提供 Extents 特定的解析功能。
    """
    
    def __init__(self, stream: BinaryIO, start_offset: int = 0,
                 node_size: int = 4096):
        super().__init__(stream, start_offset, node_size)
    
    def get_extents(self, file_id: int, fork_type: int,
                    start_block: int) -> List[HFSPlusExtentDescriptor]:
        """
        获取文件的 extent 列表
        
        Args:
            file_id: 文件 CNID
            fork_type: Fork 类型 (0=数据, 0xFF=资源)
            start_block: 起始分配块号
        
        Returns:
            Extent 描述符列表
        """
        extents = []
        
        # 遍历所有叶记录
        for node in self.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusExtentKey.from_bytes(data)
                
                # 检查是否匹配
                if (key.file_id == file_id and
                    key.fork_type == fork_type and
                    key.start_block == start_block):
                    
                    # 解析 extent 记录
                    record = HFSPlusExtentRecord.from_bytes(data, key.occupied_size)
                    extents.extend(record.extents)
                    
                    # 检查是否需要继续查找下一个 extent
                    if len(record.extents) == 8:
                        # 可能有更多 extent，继续查找
                        next_start_block = record.extents[-1].end_block
                        extents.extend(
                            self.get_extents(file_id, fork_type, next_start_block)
                        )
        
        return extents


# =============================================================================
# Catalog B-tree 读取器
# =============================================================================

class CatalogBTree(BTreeFile):
    """
    Catalog B-tree 读取器
    
    继承自 BTreeFile，提供 Catalog 特定的解析功能。
    """
    
    def __init__(self, stream: BinaryIO, start_offset: int = 0,
                 node_size: int = 4096):
        super().__init__(stream, start_offset, node_size)
    
    def parse_catalog_key(self, data: bytes, offset: int = 0) -> HFSPlusCatalogKey:
        """解析 Catalog 键"""
        return HFSPlusCatalogKey.from_bytes(data, offset)
    
    def list_folder_contents(self, parent_id: int) -> List[dict]:
        """
        列出文件夹内容
        
        Args:
            parent_id: 父文件夹 CNID
        
        Returns:
            包含文件夹内容的字典列表
        """
        results = []
        
        # 遍历所有叶记录
        for node in self.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusCatalogKey.from_bytes(data)
                
                # 检查父 ID 是否匹配
                if key.parent_id != parent_id:
                    continue
                
                # 获取记录类型
                record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                
                if record_type == CatalogRecordType.FOLDER:
                    folder = HFSPlusCatalogFolder.from_bytes(data, key.occupied_size)
                    results.append({
                        'type': 'folder',
                        'name': key.node_name,
                        'id': folder.folder_id,
                        'create_date': folder.create_date,
                        'mod_date': folder.content_mod_date,
                    })
                elif record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                    results.append({
                        'type': 'file',
                        'name': key.node_name,
                        'id': file.file_id,
                        'size': file.data_fork_size,
                        'create_date': file.create_date,
                        'mod_date': file.content_mod_date,
                    })
        
        return results


# =============================================================================
# 文件读取
# =============================================================================

class HFSPlusFileReader:
    """
    HFS+ 文件读取器
    
    用于读取文件的数据分支和资源分支。
    
    Usage:
        reader = HFSPlusFileReader(stream, catalog_btree, extents_btree)
        data = reader.read_data_fork(file_id)
    """
    
    def __init__(self, stream: BinaryIO, 
                 catalog_btree: CatalogBTree,
                 extents_btree: ExtentsBTree,
                 block_size: int = 4096):
        """
        初始化文件读取器
        
        Args:
            stream: 可 seek 的二进制流
            catalog_btree: Catalog B-tree 读取器
            extents_btree: Extents B-tree 读取器
            block_size: 分配块大小
        """
        self.stream = stream
        self.catalog_btree = catalog_btree
        self.extents_btree = extents_btree
        self.block_size = block_size
    
    def read_data_fork(self, file_id: int) -> bytes:
        """
        读取文件的数据分支
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            文件数据
        """
        # 查找文件记录
        file_record = self._find_file_record(file_id)
        if file_record is None:
            raise FileNotFoundError(f"文件未找到: {file_id}")
        
        # 获取内联 extent
        # 注意：这里简化了实现，实际需要从 Catalog 记录中读取 extent
        # 目前只支持读取内联 extent（8 个以内）
        
        # 读取数据
        data = b''
        
        # 遍历所有 extent
        # 注意：这里需要实现完整的 extent 读取逻辑
        # 目前只是一个框架
        
        return data
    
    def _find_file_record(self, file_id: int):
        """查找文件记录"""
        # 遍历所有叶记录
        for node in self.catalog_btree.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusCatalogKey.from_bytes(data)
                
                # 解析记录类型
                record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                
                if record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                    if file.file_id == file_id:
                        return file
        
        return None