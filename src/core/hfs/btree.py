"""
HFS+ B-tree 模块

实现 B-tree 节点描述符、头记录和遍历算法。
"""

import struct
import unicodedata
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Callable, BinaryIO

from .constants import (
    BTreeNodeKind,
    BTREE_NODE_DESCRIPTOR_SIZE,
    BTREE_HEADER_RECORD_SIZE,
)


# =============================================================================
# HFS+ Unicode 比较
# =============================================================================

def _hfs_fold_char(ch: str) -> str:
    """单个字符的 HFS+ 大小写折叠
    
    HFS+ 使用完全分解的 Unicode，大小写不敏感比较。
    简化实现：使用 Unicode casefold + NFD 分解。
    """
    # 分解 + casefold
    folded = unicodedata.normalize('NFD', ch).casefold()
    return folded


def hfs_unicode_compare(str1: str, str2: str) -> int:
    """
    HFS+ Unicode 大小写不敏感比较
    
    按 TN1150 规范：
    - 字符串必须完全分解 (NFD)
    - 大小写不敏感比较
    - 忽略特定 Unicode 格式字符
    
    返回: -1 (str1 < str2), 0 (相等), 1 (str1 > str2)
    """
    # NFD 分解
    s1 = unicodedata.normalize('NFD', str1)
    s2 = unicodedata.normalize('NFD', str2)
    
    # 忽略的字符 (Unicode 格式字符)
    IGNORE_CHARS = frozenset([
        '\u00AD',  # SOFT HYPHEN
        '\u034F',  # COMBINING GRAPHEME JOINER
        '\u1806',  # MONGOLIAN TODO SOFT HYPHEN
        '\u180B',  # MONGOLIAN FREE VARIATION SELECTOR ONE
        '\u180C',  # MONGOLIAN FREE VARIATION SELECTOR TWO
        '\u180D',  # MONGOLIAN FREE VARIATION SELECTOR THREE
        '\u200B',  # ZERO WIDTH SPACE
        '\u200C',  # ZERO WIDTH NON-JOINER
        '\u200D',  # ZERO WIDTH JOINER
        '\u200E',  # LEFT-TO-RIGHT MARK
        '\u200F',  # RIGHT-TO-LEFT MARK
        '\u202A',  # LEFT-TO-RIGHT EMBEDDING
        '\u202B',  # RIGHT-TO-LEFT EMBEDDING
        '\u202C',  # POP DIRECTIONAL FORMATTING
        '\u202D',  # LEFT-TO-RIGHT OVERRIDE
        '\u202E',  # RIGHT-TO-LEFT OVERRIDE
        '\u2060',  # WORD JOINER
        '\u2061',  # FUNCTION APPLICATION
        '\u2062',  # INVISIBLE TIMES
        '\u2063',  # INVISIBLE SEPARATOR
        '\u2064',  # INVISIBLE PLUS
        '\uFEFF',  # ZERO WIDTH NO-BREAK SPACE
    ])
    
    i, j = 0, 0
    len1, len2 = len(s1), len(s2)
    
    while True:
        # 获取 str1 的下一个有效字符
        c1 = '\0'
        while i < len1:
            ch = _hfs_fold_char(s1[i])
            i += 1
            if ch and ch not in IGNORE_CHARS and ch != '\0':
                c1 = ch[0]  # 取第一个字符（casefold 可能产生多字符）
                break
        
        # 获取 str2 的下一个有效字符
        c2 = '\0'
        while j < len2:
            ch = _hfs_fold_char(s2[j])
            j += 1
            if ch and ch not in IGNORE_CHARS and ch != '\0':
                c2 = ch[0]
                break
        
        # 比较
        if c1 != c2:
            if c1 < c2:
                return -1
            else:
                return 1
        
        # 都到达末尾
        if c1 == '\0':
            return 0


def compare_catalog_keys(key1_data: bytes, key2_data: bytes) -> int:
    """
    比较两个 Catalog key 的原始字节数据
    
    比较规则 (TN1150):
    1. 先比较 parentID (UInt32, big-endian)
    2. 再比较 nodeName (HFSUniStr255, case-insensitive)
    
    Args:
        key1_data: 第一个 key 的原始数据 (含 keyLength)
        key2_data: 第二个 key 的原始数据 (含 keyLength)
    
    返回: -1, 0, 1
    """
    # 提取 parentID (offset 2, 4 bytes)
    parent1 = struct.unpack_from('>I', key1_data, 2)[0]
    parent2 = struct.unpack_from('>I', key2_data, 2)[0]
    
    if parent1 < parent2:
        return -1
    if parent1 > parent2:
        return 1
    
    # parentID 相同，比较 nodeName
    # HFSUniStr255: length (2 bytes) + unicode chars
    name1_len = struct.unpack_from('>H', key1_data, 6)[0]
    name2_len = struct.unpack_from('>H', key2_data, 6)[0]
    
    name1 = key1_data[8:8 + name1_len * 2].decode('utf-16-be', errors='replace')
    name2 = key2_data[8:8 + name2_len * 2].decode('utf-16-be', errors='replace')
    
    return hfs_unicode_compare(name1, name2)


def compare_extent_keys(key1_data: bytes, key2_data: bytes) -> int:
    """
    比较两个 Extent key 的原始字节数据
    
    比较规则 (TN1150):
    1. forkType (UInt8)
    2. fileID (UInt32)
    3. startBlock (UInt32)
    """
    # forkType at offset 2
    fork1 = key1_data[2]
    fork2 = key2_data[2]
    if fork1 < fork2:
        return -1
    if fork1 > fork2:
        return 1
    
    # fileID at offset 4
    file1 = struct.unpack_from('>I', key1_data, 4)[0]
    file2 = struct.unpack_from('>I', key2_data, 4)[0]
    if file1 < file2:
        return -1
    if file1 > file2:
        return 1
    
    # startBlock at offset 8
    block1 = struct.unpack_from('>I', key1_data, 8)[0]
    block2 = struct.unpack_from('>I', key2_data, 8)[0]
    if block1 < block2:
        return -1
    if block1 > block2:
        return 1
    
    return 0


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
                 node_size: int = 4096, parse_key_fn: Optional[Callable] = None,
                 compare_fn: Optional[Callable] = None):
        """
        初始化 B-tree 文件读取器
        
        Args:
            stream: 可 seek 的二进制流
            start_offset: B-tree 数据在流中的起始偏移量
            node_size: 节点大小（字节），默认 4096
            parse_key_fn: 可选的键解析函数
            compare_fn: 键比较函数 (key1_data, key2_data) -> int
        """
        self.stream = stream
        self.start_offset = start_offset
        self._node_size = node_size
        self.parse_key_fn = parse_key_fn
        self.compare_fn = compare_fn
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
    
    def _compare_keys(self, key1: bytes, key2: bytes) -> int:
        """比较两个键
        
        使用 compare_fn（如果提供），否则回退到字节比较。
        """
        if self.compare_fn:
            return self.compare_fn(key1, key2)
        # 回退：字节比较
        if key1 < key2:
            return -1
        elif key1 > key2:
            return 1
        return 0
    
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
                
                if self._compare_keys(key_data, search_key_data) == 0:
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
            if self._compare_keys(key_data, search_key_data) <= 0:
                if best is None or self._compare_keys(key_data, best.key_data) > 0:
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
        key_length: 键长度（4 + 2 + nodeName 字节长度）
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
        """从字节序列解析
        
        按 TN1150 规范：
        - keyLength (UInt16): 包含 parentID(4) + HFSUniStr255(2 + 2*numChars)
        - parentID (UInt32): 父文件夹 CNID
        - nodeName (HFSUniStr255): UInt16 length + UInt16[] unicode
        """
        key_length = struct.unpack_from('>H', data, offset)[0]
        parent_id = struct.unpack_from('>I', data, offset + 2)[0]
        
        # HFSUniStr255.length (UInt16) - 字符数量
        name_length = struct.unpack_from('>H', data, offset + 6)[0]
        
        # 计算名称字节长度（每个字符 2 字节）
        name_byte_len = name_length * 2
        
        # 解析 UTF-16BE 名称（从 offset + 8 开始）
        raw_name = data[offset + 8:offset + 8 + name_byte_len]
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
    
    88 字节。按 TN1150 规范。
    
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
        permissions: BSD 权限 (16 字节原始数据)
        userInfo: Finder userInfo (8 字节)
        finderInfo: ExtendedFolderInfo (8 字节)
        text_encoding: 文本编码提示
        reserved: 保留字段
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
    permissions: bytes  # 16 bytes HFSPlusBSDInfo
    userInfo: bytes     # 8 bytes FolderInfo
    finderInfo: bytes   # 8 bytes ExtendedFolderInfo
    text_encoding: int
    reserved: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusCatalogFolder':
        """从字节序列解析
        
        按 TN1150 规范 (88 bytes):
        SInt16 recordType, UInt16 flags, UInt32 valence, UInt32 folderID,
        UInt32 createDate, UInt32 contentModDate, UInt32 attributeModDate,
        UInt32 accessDate, UInt32 backupDate,
        HFSPlusBSDInfo permissions (16 bytes),
        FolderInfo userInfo (8 bytes), ExtendedFolderInfo finderInfo (8 bytes),
        UInt32 textEncoding, UInt32 reserved
        """
        # 前 36 字节: recordType(2) + flags(2) + valence(4) + folderID(4) + 5 dates(20)
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
        ) = struct.unpack_from('>HHI I IIII', data, offset)
        
        # HFSPlusBSDInfo (16 bytes): ownerID(4) + groupID(4) + adminFlags(1) + ownerFlags(1) + fileMode(2) + special(4)
        permissions = bytes(data[offset + 36:offset + 52])
        
        # FolderInfo (8 bytes) + ExtendedFolderInfo (8 bytes)
        userInfo = bytes(data[offset + 52:offset + 60])
        finderInfo = bytes(data[offset + 60:offset + 68])
        
        # textEncoding (4 bytes) + reserved (4 bytes)
        text_encoding, reserved = struct.unpack_from('>II', data, offset + 68)
        
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
            permissions=permissions,
            userInfo=userInfo,
            finderInfo=finderInfo,
            text_encoding=text_encoding,
            reserved=reserved
        )
    
    def get_owner_id(self) -> int:
        """获取所有者 ID"""
        return struct.unpack_from('>I', self.permissions, 0)[0]
    
    def get_group_id(self) -> int:
        """获取组 ID"""
        return struct.unpack_from('>I', self.permissions, 4)[0]
    
    def get_file_mode(self) -> int:
        """获取文件模式"""
        return struct.unpack_from('>H', self.permissions, 10)[0]


@dataclass
class HFSPlusCatalogFile:
    """
    HFS+ Catalog 文件记录
    
    248 字节。按 TN1150 规范。
    
    Attributes:
        record_type: 记录类型 (0x0002)
        flags: 标志
        reserved1: 保留字段
        file_id: 文件 CNID
        create_date: 创建日期
        content_mod_date: 内容修改日期
        attribute_mod_date: 属性修改日期
        access_date: 访问日期
        backup_date: 备份日期
        permissions: BSD 权限 (16 字节原始数据)
        userInfo: Finder userInfo (8 字节)
        finderInfo: ExtendedFileInfo (8 字节)
        text_encoding: 文本编码提示
        reserved2: 保留字段
        data_fork: 数据分支 (HFSPlusForkData, 80 字节)
        resource_fork: 资源分支 (HFSPlusForkData, 80 字节)
    """
    record_type: int
    flags: int
    reserved1: int
    file_id: int
    create_date: int
    content_mod_date: int
    attribute_mod_date: int
    access_date: int
    backup_date: int
    permissions: bytes  # 16 bytes HFSPlusBSDInfo
    userInfo: bytes     # 8 bytes FileInfo
    finderInfo: bytes   # 8 bytes ExtendedFileInfo
    text_encoding: int
    reserved2: int
    data_fork: bytes    # 80 bytes HFSPlusForkData
    resource_fork: bytes # 80 bytes HFSPlusForkData
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusCatalogFile':
        """从字节序列解析
        
        按 TN1150 规范 (248 bytes):
        SInt16 recordType, UInt16 flags, UInt32 reserved1, UInt32 fileID,
        UInt32 createDate, UInt32 contentModDate, UInt32 attributeModDate,
        UInt32 accessDate, UInt32 backupDate,
        HFSPlusBSDInfo permissions (16 bytes),
        FileInfo userInfo (8 bytes), ExtendedFileInfo finderInfo (8 bytes),
        UInt32 textEncoding, UInt32 reserved2,
        HFSPlusForkData dataFork (80 bytes), HFSPlusForkData resourceFork (80 bytes)
        """
        # 前 40 字节: recordType(2) + flags(2) + reserved1(4) + fileID(4) + 5 dates(20) + padding?
        # 实际: recordType(2) + flags(2) + reserved1(4) + fileID(4) = 12
        #       createDate(4) + contentModDate(4) + attributeModDate(4) + accessDate(4) + backupDate(4) = 20
        # 总计: 32 字节
        (
            record_type,
            flags,
            reserved1,
            file_id,
            create_date,
            content_mod_date,
            attribute_mod_date,
            access_date,
            backup_date,
        ) = struct.unpack_from('>HHI I IIII', data, offset)
        
        # HFSPlusBSDInfo (16 bytes)
        permissions = bytes(data[offset + 32:offset + 48])
        
        # FileInfo (8 bytes) + ExtendedFileInfo (8 bytes)
        userInfo = bytes(data[offset + 48:offset + 56])
        finderInfo = bytes(data[offset + 56:offset + 64])
        
        # textEncoding (4 bytes) + reserved2 (4 bytes)
        text_encoding, reserved2 = struct.unpack_from('>II', data, offset + 64)
        
        # HFSPlusForkData dataFork (80 bytes): logicalSize(8) + clumpSize(4) + totalBlocks(4) + extents(64)
        data_fork = bytes(data[offset + 72:offset + 152])
        
        # HFSPlusForkData resourceFork (80 bytes)
        resource_fork = bytes(data[offset + 152:offset + 232])
        
        return cls(
            record_type=record_type,
            flags=flags,
            reserved1=reserved1,
            file_id=file_id,
            create_date=create_date,
            content_mod_date=content_mod_date,
            attribute_mod_date=attribute_mod_date,
            access_date=access_date,
            backup_date=backup_date,
            permissions=permissions,
            userInfo=userInfo,
            finderInfo=finderInfo,
            text_encoding=text_encoding,
            reserved2=reserved2,
            data_fork=data_fork,
            resource_fork=resource_fork
        )
    
    def get_data_fork_size(self) -> int:
        """获取数据分支逻辑大小"""
        return struct.unpack_from('>Q', self.data_fork, 0)[0]
    
    def get_data_fork_blocks(self) -> int:
        """获取数据分支总块数"""
        return struct.unpack_from('>I', self.data_fork, 12)[0]
    
    def get_data_fork_extents(self) -> list:
        """获取数据分支的 8 个 extent 描述符"""
        extents = []
        for i in range(8):
            start_block, block_count = struct.unpack_from('>II', self.data_fork, 16 + i * 8)
            extents.append((start_block, block_count))
        return extents
    
    def get_resource_fork_size(self) -> int:
        """获取资源分支逻辑大小"""
        return struct.unpack_from('>Q', self.resource_fork, 0)[0]
    
    def get_owner_id(self) -> int:
        """获取所有者 ID"""
        return struct.unpack_from('>I', self.permissions, 0)[0]
    
    def get_group_id(self) -> int:
        """获取组 ID"""
        return struct.unpack_from('>I', self.permissions, 4)[0]
    
    def get_file_mode(self) -> int:
        """获取文件模式"""
        return struct.unpack_from('>H', self.permissions, 10)[0]


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
        super().__init__(stream, start_offset, node_size, compare_fn=compare_extent_keys)
    
    def get_extents_for_fork(self, file_id: int, fork_type: int) -> List[HFSPlusExtentDescriptor]:
        """
        获取文件某个 fork 的所有 overflow extents
        
        Extents B-tree 中的记录按键 (forkType, fileID, startBlock) 排序。
        一个文件可能有多个 extent 记录（每个最多 8 个 extent）。
        
        Args:
            file_id: 文件 CNID
            fork_type: Fork 类型 (0=数据, 0xFF=资源)
        
        Returns:
            所有 overflow extent 描述符列表
        """
        extents = []
        
        # 遍历所有叶记录，查找匹配的 file_id 和 fork_type
        # 由于按键排序，同一文件的记录是连续的
        for node in self.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusExtentKey.from_bytes(data)
                
                # 如果 file_id 已经大于目标，可以提前退出
                if key.file_id > file_id:
                    return extents
                
                # 检查是否匹配
                if key.file_id == file_id and key.fork_type == fork_type:
                    # 解析 extent 记录（8 个 extent 描述符，64 字节）
                    record = HFSPlusExtentRecord.from_bytes(data, key.occupied_size)
                    extents.extend(record.extents)
        
        return extents
    
    def get_all_extents(self, file_id: int, fork_type: int,
                        initial_extents: List[HFSPlusExtentDescriptor]) -> List[HFSPlusExtentDescriptor]:
        """
        获取文件的完整 extent 列表（初始 + overflow）
        
        Args:
            file_id: 文件 CNID
            fork_type: Fork 类型 (0=数据, 0xFF=资源)
            initial_extents: 来自 catalog 记录的初始 8 个 extent
        
        Returns:
            完整的 extent 描述符列表
        """
        all_extents = list(initial_extents)
        
        # 只有当初始 extents 满 8 个时，才需要查找 overflow
        if len(initial_extents) >= 8:
            overflow = self.get_extents_for_fork(file_id, fork_type)
            all_extents.extend(overflow)
        
        return all_extents


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
        super().__init__(stream, start_offset, node_size, compare_fn=compare_catalog_keys)
    
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
                        'size': file.get_data_fork_size(),
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
    支持初始 extents (catalog 记录中) 和 overflow extents (extents B-tree 中)。
    
    Usage:
        reader = HFSPlusFileReader(stream, catalog_btree, extents_btree, block_size=4096)
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
        
        # 获取文件大小
        file_size = file_record.get_data_fork_size()
        if file_size == 0:
            return b''
        
        # 获取初始 extents（来自 catalog 记录的 data_fork 字段）
        initial_extents = file_record.get_data_fork_extents()
        
        # 转换为 HFSPlusExtentDescriptor 对象
        extent_descs = []
        for start_block, block_count in initial_extents:
            if block_count > 0:
                extent_descs.append(HFSPlusExtentDescriptor(start_block, block_count))
        
        # 获取所有 extents（包括 overflow）
        all_extents = self.extents_btree.get_all_extents(
            file_id, ForkType.DATA, extent_descs
        )
        
        # 读取数据
        return self._read_extents(all_extents, file_size)
    
    def read_resource_fork(self, file_id: int) -> bytes:
        """
        读取文件的资源分支
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            资源分支数据
        """
        # 查找文件记录
        file_record = self._find_file_record(file_id)
        if file_record is None:
            raise FileNotFoundError(f"文件未找到: {file_id}")
        
        # 获取资源分支大小
        fork_size = file_record.get_resource_fork_size()
        if fork_size == 0:
            return b''
        
        # 获取初始 extents（来自 catalog 记录的 resource_fork 字段）
        # resource_fork 在 file_record 中的偏移是 152 (72 + 80)
        resource_fork_data = file_record.resource_fork
        initial_extents = []
        for i in range(8):
            start_block, block_count = struct.unpack_from('>II', resource_fork_data, 16 + i * 8)
            if block_count > 0:
                initial_extents.append(HFSPlusExtentDescriptor(start_block, block_count))
        
        # 获取所有 extents（包括 overflow）
        all_extents = self.extents_btree.get_all_extents(
            file_id, ForkType.RESOURCE, initial_extents
        )
        
        # 读取数据
        return self._read_extents(all_extents, fork_size)
    
    def _read_extents(self, extents: List[HFSPlusExtentDescriptor], 
                      max_size: int) -> bytes:
        """
        从 extent 列表读取数据
        
        Args:
            extents: extent 描述符列表
            max_size: 最大读取字节数
        
        Returns:
            读取的数据
        """
        data = bytearray()
        bytes_remaining = max_size
        
        for ext in extents:
            if bytes_remaining <= 0:
                break
            
            # 计算这个 extent 要读取的字节数
            ext_bytes = ext.block_count * self.block_size
            read_bytes = min(ext_bytes, bytes_remaining)
            
            # 定位到 extent 的起始位置
            byte_offset = ext.start_block * self.block_size
            self.stream.seek(byte_offset)
            
            # 读取数据
            chunk = self.stream.read(read_bytes)
            data.extend(chunk)
            
            bytes_remaining -= len(chunk)
        
        return bytes(data)
    
    def _find_file_record(self, file_id: int) -> Optional[HFSPlusCatalogFile]:
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