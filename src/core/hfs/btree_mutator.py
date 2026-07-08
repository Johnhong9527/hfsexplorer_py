"""
HFS+ B-tree 变异引擎

实现 B-tree 的插入、删除、分裂、合并等变异操作。
"""

import struct
from typing import Optional, List, Tuple, BinaryIO
from dataclasses import dataclass

from .btree import (
    BTreeFile,
    BTNodeDescriptor,
    BTHeaderRec,
    BTreeNode,
    BTIndexRecord,
    BTLeafRecord,
)
from .constants import BTreeNodeKind


class BTreeMutationError(Exception):
    """B-tree 变异错误"""
    pass


@dataclass
class BTreeMutationResult:
    """
    B-tree 变异结果
    
    Attributes:
        success: 是否成功
        new_root: 新的根节点号（如果根节点分裂）
        nodes_modified: 修改的节点列表
        error: 错误信息（如果失败）
    """
    success: bool
    new_root: Optional[int] = None
    nodes_modified: List[int] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.nodes_modified is None:
            self.nodes_modified = []


class BTreeMutator:
    """
    B-tree 变异器
    
    用于修改 B-tree 结构。
    
    Usage:
        mutator = BTreeMutator(btree, stream)
        result = mutator.insert_record(key_data, record_data)
    """
    
    def __init__(self, btree: BTreeFile, stream: BinaryIO):
        """
        初始化 B-tree 变异器
        
        Args:
            btree: B-tree 文件
            stream: 可读写的二进制流
        """
        self.btree = btree
        self.stream = stream
        self.header = btree.header
        self.node_size = self.header.nodeSize
    
    def insert_record(self, key_data: bytes, record_data: bytes) -> BTreeMutationResult:
        """
        插入记录
        
        Args:
            key_data: 键数据
            record_data: 记录数据
        
        Returns:
            变异结果
        """
        try:
            # 查找插入位置
            leaf_node, insert_index = self._find_insert_position(key_data)
            
            if leaf_node is None:
                return BTreeMutationResult(
                    success=False,
                    error="无法找到插入位置"
                )
            
            # 计算记录大小
            record_size = len(key_data) + len(record_data)
            
            # 检查节点是否有足够空间
            if self._node_has_space(leaf_node, record_size):
                # 直接插入
                self._insert_into_node(leaf_node, insert_index, key_data, record_data)
                
                # 更新节点
                self._write_node(leaf_node)
                
                return BTreeMutationResult(
                    success=True,
                    nodes_modified=[leaf_node.descriptor.fLink]
                )
            else:
                # 需要分裂节点
                return self._insert_with_split(leaf_node, insert_index, 
                                              key_data, record_data)
        
        except Exception as e:
            return BTreeMutationResult(
                success=False,
                error=str(e)
            )
    
    def delete_record(self, key_data: bytes) -> BTreeMutationResult:
        """
        删除记录
        
        Args:
            key_data: 键数据
        
        Returns:
            变异结果
        """
        try:
            # 查找记录
            leaf_node, record_index = self._find_record(key_data)
            
            if leaf_node is None:
                return BTreeMutationResult(
                    success=False,
                    error="未找到记录"
                )
            
            # 获取记录大小
            record_size = leaf_node.get_record_length(record_index)
            
            # 删除记录
            self._delete_from_node(leaf_node, record_index)
            
            # 更新节点
            self._write_node(leaf_node)
            
            # 检查是否需要合并
            if self._node_underflow(leaf_node):
                self._handle_underflow(leaf_node)
            
            return BTreeMutationResult(
                success=True,
                nodes_modified=[leaf_node.descriptor.fLink]
            )
        
        except Exception as e:
            return BTreeMutationResult(
                success=False,
                error=str(e)
            )
    
    def _find_insert_position(self, key_data: bytes) -> Tuple[Optional[BTreeNode], int]:
        """
        查找插入位置
        
        Args:
            key_data: 键数据
        
        Returns:
            (叶节点, 插入索引)
        """
        # 从根节点开始遍历
        root_number = self.header.rootNode
        if root_number == 0:
            return None, -1
        
        current_node = self.btree.get_node(root_number)
        
        # 下降到叶节点
        while current_node.descriptor.is_index:
            # 查找子节点
            child_number = self._find_child_for_key(current_node, key_data)
            current_node = self.btree.get_node(child_number)
        
        # 在叶节点中查找插入位置
        insert_index = self._find_insert_index_in_leaf(current_node, key_data)
        
        return current_node, insert_index
    
    def _find_record(self, key_data: bytes) -> Tuple[Optional[BTreeNode], int]:
        """
        查找记录
        
        Args:
            key_data: 键数据
        
        Returns:
            (叶节点, 记录索引)
        """
        # 从根节点开始遍历
        root_number = self.header.rootNode
        if root_number == 0:
            return None, -1
        
        current_node = self.btree.get_node(root_number)
        
        # 下降到叶节点
        while current_node.descriptor.is_index:
            child_number = self._find_child_for_key(current_node, key_data)
            current_node = self.btree.get_node(child_number)
        
        # 在叶节点中查找记录
        for i in range(current_node.num_records):
            record_data = current_node.get_record_data(i)
            record_key = record_data[:len(key_data)]
            
            if record_key == key_data:
                return current_node, i
        
        return None, -1
    
    def _find_child_for_key(self, node: BTreeNode, key_data: bytes) -> int:
        """
        查找键对应的子节点
        
        Args:
            node: 索引节点
            key_data: 键数据
        
        Returns:
            子节点号
        """
        best_child = None
        best_key = None
        
        for i in range(node.num_records):
            data = node.get_record_data(i)
            
            # 解析键长度
            key_length = struct.unpack_from('>H', data, 0)[0]
            key = data[:2 + key_length]
            
            # 子节点号在键之后
            child_node = struct.unpack_from('>I', data, 2 + key_length)[0]
            
            # 如果键 <= 搜索键
            if key <= key_data:
                if best_key is None or key > best_key:
                    best_key = key
                    best_child = child_node
        
        return best_child
    
    def _find_insert_index_in_leaf(self, node: BTreeNode, key_data: bytes) -> int:
        """
        在叶节点中查找插入位置
        
        Args:
            node: 叶节点
            key_data: 键数据
        
        Returns:
            插入索引
        """
        for i in range(node.num_records):
            data = node.get_record_data(i)
            
            # 解析键长度
            key_length = struct.unpack_from('>H', data, 0)[0]
            key = data[:2 + key_length]
            
            # 如果当前键大于插入键
            if key > key_data:
                return i
        
        return node.num_records
    
    def _node_has_space(self, node: BTreeNode, record_size: int) -> bool:
        """
        检查节点是否有足够空间
        
        Args:
            node: 节点
            record_size: 记录大小
        
        Returns:
            是否有足够空间
        """
        # 计算空闲空间
        if node.num_records == 0:
            free_space = self.node_size - BTNodeDescriptor.STRUCT_SIZE - 2  # 2 for offset table
        else:
            last_offset = node.offsets[-1]
            offset_table_size = (node.num_records + 1) * 2
            free_space = self.node_size - last_offset - offset_table_size
        
        # 需要额外 2 字节用于新的偏移表条目
        return free_space >= record_size + 2
    
    def _insert_into_node(self, node: BTreeNode, index: int, 
                         key_data: bytes, record_data: bytes):
        """
        插入记录到节点
        
        Args:
            node: 节点
            index: 插入索引
            key_data: 键数据
            record_data: 记录数据
        """
        # 构造完整记录
        full_record = key_data + record_data
        record_size = len(full_record)
        
        # 计算插入偏移量
        if index < len(node.offsets):
            insert_offset = node.offsets[index]
        else:
            insert_offset = node.offsets[-1]
        
        # 移动现有数据
        # 注意：这里简化了实现，实际需要更复杂的数据移动
        
        # 插入新记录
        node.raw_data[insert_offset:insert_offset + record_size] = full_record
        
        # 更新偏移表
        # 注意：这里简化了实现，实际需要更新所有后续偏移
        
        # 更新记录数
        node.descriptor.numRecords += 1
    
    def _delete_from_node(self, node: BTreeNode, index: int):
        """
        从节点删除记录
        
        Args:
            node: 节点
            index: 记录索引
        """
        # 获取记录大小
        record_size = node.get_record_length(index)
        
        # 获取记录偏移量
        record_offset = node.get_record_offset(index)
        
        # 移动后续记录
        # 注意：这里简化了实现，实际需要更复杂的数据移动
        
        # 更新偏移表
        # 注意：这里简化了实现，实际需要更新所有后续偏移
        
        # 更新记录数
        node.descriptor.numRecords -= 1
    
    def _insert_with_split(self, node: BTreeNode, index: int,
                          key_data: bytes, record_data: bytes) -> BTreeMutationResult:
        """
        插入记录并分裂节点
        
        Args:
            node: 节点
            index: 插入索引
            key_data: 键数据
            record_data: 记录数据
        
        Returns:
            变异结果
        """
        # TODO: 实现节点分裂
        # 这需要：
        # 1. 创建新节点
        # 2. 将一半记录移动到新节点
        # 3. 插入新记录
        # 4. 更新父节点
        # 5. 如果父节点满，递归分裂
        
        return BTreeMutationResult(
            success=False,
            error="节点分裂尚未实现"
        )
    
    def _handle_underflow(self, node: BTreeNode):
        """
        处理节点下溢
        
        Args:
            node: 下溢的节点
        """
        # TODO: 实现节点合并或重新分配
        # 这需要：
        # 1. 检查兄弟节点是否有足够空间
        # 2. 如果有，重新分配记录
        # 3. 如果没有，合并节点
        # 4. 更新父节点
        pass
    
    def _write_node(self, node: BTreeNode):
        """
        写入节点到磁盘
        
        Args:
            node: 节点
        """
        # TODO: 实现节点写入
        # 这需要：
        # 1. 计算节点在文件中的偏移量
        # 2. 写入节点数据
        pass
    
    def _allocate_node(self) -> int:
        """
        分配新节点
        
        Returns:
            新节点号
        """
        # TODO: 实现节点分配
        # 这需要：
        # 1. 查找空闲节点
        # 2. 更新空闲节点列表
        # 3. 返回新节点号
        return -1
    
    def _free_node(self, node_number: int):
        """
        释放节点
        
        Args:
            node_number: 节点号
        """
        # TODO: 实现节点释放
        # 这需要：
        # 1. 将节点添加到空闲列表
        # 2. 更新空闲节点计数
        pass


class CatalogMutator:
    """
    Catalog 变异器
    
    用于修改 Catalog 文件。
    
    Usage:
        mutator = CatalogMutator(catalog, stream)
        result = mutator.create_file(parent_id, "test.txt")
    """
    
    def __init__(self, catalog: BTreeFile, stream: BinaryIO):
        """
        初始化 Catalog 变异器
        
        Args:
            catalog: Catalog B-tree
            stream: 可读写的二进制流
        """
        self.catalog = catalog
        self.stream = stream
        self.btree_mutator = BTreeMutator(catalog, stream)
    
    def create_file(self, parent_id: int, name: str, 
                    file_id: int, create_date: int) -> BTreeMutationResult:
        """
        创建文件
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件名
            file_id: 文件 CNID
            create_date: 创建日期
        
        Returns:
            变异结果
        """
        # 构造 Catalog 键
        key_data = self._build_catalog_key(parent_id, name)
        
        # 构造文件记录
        record_data = self._build_file_record(file_id, create_date)
        
        # 插入记录
        return self.btree_mutator.insert_record(key_data, record_data)
    
    def create_folder(self, parent_id: int, name: str,
                     folder_id: int, create_date: int) -> BTreeMutationResult:
        """
        创建文件夹
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件夹名称
            folder_id: 文件夹 CNID
            create_date: 创建日期
        
        Returns:
            变异结果
        """
        # 构造 Catalog 键
        key_data = self._build_catalog_key(parent_id, name)
        
        # 构造文件夹记录
        record_data = self._build_folder_record(folder_id, create_date)
        
        # 插入记录
        return self.btree_mutator.insert_record(key_data, record_data)
    
    def delete_entry(self, parent_id: int, name: str) -> BTreeMutationResult:
        """
        删除条目
        
        Args:
            parent_id: 父文件夹 CNID
            name: 条目名称
        
        Returns:
            变异结果
        """
        # 构造 Catalog 键
        key_data = self._build_catalog_key(parent_id, name)
        
        # 删除记录
        return self.btree_mutator.delete_record(key_data)
    
    def _build_catalog_key(self, parent_id: int, name: str) -> bytes:
        """
        构造 Catalog 键
        
        Args:
            parent_id: 父文件夹 CNID
            name: 名称
        
        Returns:
            键数据
        """
        # 编码名称
        name_bytes = name.encode('utf-16-be')
        
        # 计算键长度
        key_length = 4 + len(name_bytes)
        
        # 构造键
        key = struct.pack('>HI', key_length, parent_id) + name_bytes
        
        return key
    
    def _build_file_record(self, file_id: int, create_date: int) -> bytes:
        """
        构造文件记录
        
        Args:
            file_id: 文件 CNID
            create_date: 创建日期
        
        Returns:
            记录数据
        """
        # 记录类型
        record_type = 0x0002  # 文件记录
        
        # 构造记录
        record = struct.pack('>H', record_type)
        record += struct.pack('>H', 0)  # 标志
        record += struct.pack('>I', file_id)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', 0)  # 备份日期
        record += struct.pack('>I', 0)  # 所有者 ID
        record += struct.pack('>I', 0)  # 组 ID
        record += struct.pack('>B', 0)  # 管理员标志
        record += struct.pack('>B', 0)  # 所有者标志
        record += struct.pack('>H', 0o100644)  # 文件模式
        
        # 数据分支
        record += struct.pack('>Q', 0)  # 逻辑大小
        record += struct.pack('>I', 0)  # Clump 大小
        record += struct.pack('>I', 0)  # 总块数
        
        # Extents
        for _ in range(8):
            record += struct.pack('>II', 0, 0)
        
        # 资源分支
        record += struct.pack('>Q', 0)  # 逻辑大小
        record += struct.pack('>I', 0)  # Clump 大小
        record += struct.pack('>I', 0)  # 总块数
        
        # Extents
        for _ in range(8):
            record += struct.pack('>II', 0, 0)
        
        return record
    
    def _build_folder_record(self, folder_id: int, create_date: int) -> bytes:
        """
        构造文件夹记录
        
        Args:
            folder_id: 文件夹 CNID
            create_date: 创建日期
        
        Returns:
            记录数据
        """
        # 记录类型
        record_type = 0x0001  # 文件夹记录
        
        # 构造记录
        record = struct.pack('>H', record_type)
        record += struct.pack('>H', 0)  # 标志
        record += struct.pack('>I', 0)  # Valence
        record += struct.pack('>I', folder_id)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', create_date)
        record += struct.pack('>I', 0)  # 备份日期
        record += struct.pack('>I', 0)  # 所有者 ID
        record += struct.pack('>I', 0)  # 组 ID
        record += struct.pack('>B', 0)  # 管理员标志
        record += struct.pack('>B', 0)  # 所有者标志
        record += struct.pack('>H', 0o40755)  # 文件模式
        
        # Finder 信息
        for _ in range(8):
            record += struct.pack('>I', 0)
        
        return record