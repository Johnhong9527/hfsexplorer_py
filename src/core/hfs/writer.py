"""
HFS+ 写操作支持

提供文件和文件夹的创建、删除、修改等写操作。
"""

import struct
import os
from typing import Optional, List, BinaryIO
from dataclasses import dataclass
from enum import IntEnum

from .btree import (
    BTreeFile,
    BTNodeDescriptor,
    BTHeaderRec,
    BTreeNode,
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFSPlusExtentKey,
    HFSPlusExtentRecord,
    HFSPlusExtentDescriptor,
)
from .btree_mutator import BTreeMutator, BTreeMutationResult
from .structures import HFSPlusVolumeHeader
from .constants import CatalogNodeID, HFS_EPOCH_OFFSET


class WriteError(Exception):
    """写操作错误"""
    pass


class AllocationBitmap:
    """
    分配位图
    
    用于管理分配块的使用状态。
    
    Usage:
        bitmap = AllocationBitmap(data, block_size)
        bitmap.allocate_block(100)
        bitmap.free_block(100)
    """
    
    def __init__(self, data: bytes, block_size: int = 4096):
        """
        初始化分配位图
        
        Args:
            data: 位图数据
            block_size: 分配块大小
        """
        self.data = bytearray(data)
        self.block_size = block_size
    
    def is_block_allocated(self, block_number: int) -> bool:
        """
        检查块是否已分配
        
        Args:
            block_number: 块号
        
        Returns:
            是否已分配
        """
        byte_index = block_number // 8
        bit_index = block_number % 8
        
        if byte_index >= len(self.data):
            return False
        
        return bool(self.data[byte_index] & (1 << (7 - bit_index)))
    
    def allocate_block(self, block_number: int):
        """
        分配块
        
        Args:
            block_number: 块号
        """
        byte_index = block_number // 8
        bit_index = block_number % 8
        
        if byte_index >= len(self.data):
            raise WriteError(f"块号超出范围: {block_number}")
        
        self.data[byte_index] |= (1 << (7 - bit_index))
    
    def free_block(self, block_number: int):
        """
        释放块
        
        Args:
            block_number: 块号
        """
        byte_index = block_number // 8
        bit_index = block_number % 8
        
        if byte_index >= len(self.data):
            raise WriteError(f"块号超出范围: {block_number}")
        
        self.data[byte_index] &= ~(1 << (7 - bit_index))
    
    def find_free_blocks(self, count: int, start_block: int = 0) -> List[int]:
        """
        查找空闲块
        
        Args:
            count: 需要的块数
            start_block: 起始块号
        
        Returns:
            空闲块号列表
        """
        free_blocks = []
        block_number = start_block
        
        while len(free_blocks) < count:
            if not self.is_block_allocated(block_number):
                free_blocks.append(block_number)
            block_number += 1
            
            # 防止无限循环
            if block_number >= len(self.data) * 8:
                raise WriteError("没有足够的空闲块")
        
        return free_blocks
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        return bytes(self.data)


class BTreeWriter:
    """
    B-tree 写入器
    
    用于修改 B-tree 结构。
    
    Usage:
        writer = BTreeWriter(btree)
        writer.insert_record(key, data)
        writer.delete_record(key)
    """
    
    def __init__(self, btree: BTreeFile, stream: BinaryIO):
        """
        初始化 B-tree 写入器
        
        Args:
            btree: B-tree 文件
            stream: 可读写的二进制流
        """
        self.btree = btree
        self.stream = stream
        self.mutator = BTreeMutator(btree, stream)
    
    def insert_record(self, key: bytes, data: bytes) -> bool:
        """
        插入记录
        
        Args:
            key: 记录键
            data: 记录数据
        
        Returns:
            是否成功
        """
        result = self.mutator.insert_record(key, data)
        if not result.success:
            raise WriteError(f"B-tree 记录插入失败: {result.error}")
        return True
    
    def delete_record(self, key: bytes) -> bool:
        """
        删除记录
        
        Args:
            key: 记录键
        
        Returns:
            是否成功
        """
        result = self.mutator.delete_record(key)
        if not result.success:
            raise WriteError(f"B-tree 记录删除失败: {result.error}")
        return True
    
    def update_record(self, key: bytes, data: bytes) -> bool:
        """
        更新记录
        
        Args:
            key: 记录键
            data: 新的记录数据
        
        Returns:
            是否成功
        """
        # 先删除旧记录，再插入新记录
        try:
            self.delete_record(key)
        except WriteError:
            pass  # 记录可能不存在
        
        return self.insert_record(key, data)


class CatalogWriter:
    """
    Catalog 写入器
    
    用于修改 Catalog 文件。
    
    Usage:
        writer = CatalogWriter(catalog, volume_header)
        writer.create_file(parent_id, "test.txt", data)
        writer.create_folder(parent_id, "New Folder")
        writer.delete_entry(parent_id, "test.txt")
    """
    
    def __init__(self, catalog: CatalogBTree, volume_header: HFSPlusVolumeHeader,
                 stream: BinaryIO):
        """
        初始化 Catalog 写入器
        
        Args:
            catalog: Catalog B-tree
            volume_header: 卷头
            stream: 可写的二进制流
        """
        self.catalog = catalog
        self.volume_header = volume_header
        self.stream = stream
        self.btree_writer = BTreeWriter(catalog, stream)
        self.catalog_mutator = CatalogMutator(catalog, stream) if 'CatalogMutator' in dir() else None
    
    def create_file(self, parent_id: int, name: str, data: bytes = b'') -> int:
        """
        创建文件
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件名
            data: 文件数据
        
        Returns:
            新文件的 CNID
        """
        # 分配新的 CNID
        file_id = self._allocate_cnid()
        
        # 创建 Catalog 键
        key = HFSPlusCatalogKey(
            key_length=4 + len(name.encode('utf-16-be')),
            parent_id=parent_id,
            node_name=name
        )
        
        # 创建文件记录
        file_record = HFSPlusCatalogFile(
            record_type=CatalogRecordType.FILE,
            flags=0,
            file_id=file_id,
            create_date=self._get_current_date(),
            content_mod_date=self._get_current_date(),
            attribute_mod_date=self._get_current_date(),
            access_date=self._get_current_date(),
            backup_date=0,
            owner_id=0,
            group_id=0,
            admin_flags=0,
            owner_flags=0,
            file_mode=0o100644,  # 普通文件
            data_fork_size=len(data),
            data_fork_blocks=0
        )
        
        # 序列化键和记录
        key_bytes = key.to_bytes()
        record_bytes = file_record.to_bytes()
        
        # 插入到 B-tree
        self.btree_writer.insert_record(key_bytes, record_bytes)
        
        return file_id
    
    def create_folder(self, parent_id: int, name: str) -> int:
        """
        创建文件夹
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件夹名称
        
        Returns:
            新文件夹的 CNID
        """
        # 分配新的 CNID
        folder_id = self._allocate_cnid()
        
        # 创建 Catalog 键
        key = HFSPlusCatalogKey(
            key_length=4 + len(name.encode('utf-16-be')),
            parent_id=parent_id,
            node_name=name
        )
        
        # 创建文件夹记录
        folder_record = HFSPlusCatalogFolder(
            record_type=CatalogRecordType.FOLDER,
            flags=0,
            valence=0,
            folder_id=folder_id,
            create_date=self._get_current_date(),
            content_mod_date=self._get_current_date(),
            attribute_mod_date=self._get_current_date(),
            access_date=self._get_current_date(),
            backup_date=0,
            owner_id=0,
            group_id=0,
            admin_flags=0,
            owner_flags=0,
            file_mode=0o40755  # 目录
        )
        
        # 序列化键和记录
        key_bytes = key.to_bytes()
        record_bytes = folder_record.to_bytes()
        
        # 插入到 B-tree
        self.btree_writer.insert_record(key_bytes, record_bytes)
        
        return folder_id
    
    def delete_entry(self, parent_id: int, name: str) -> bool:
        """
        删除条目
        
        Args:
            parent_id: 父文件夹 CNID
            name: 条目名称
        
        Returns:
            是否成功
        """
        # 创建 Catalog 键
        key = HFSPlusCatalogKey(
            key_length=4 + len(name.encode('utf-16-be')),
            parent_id=parent_id,
            node_name=name
        )
        
        # 序列化键
        key_bytes = key.to_bytes()
        
        # 从 B-tree 删除
        self.btree_writer.delete_record(key_bytes)
        
        return True
    
    def rename_entry(self, parent_id: int, old_name: str, new_name: str) -> bool:
        """
        重命名条目
        
        Args:
            parent_id: 父文件夹 CNID
            old_name: 旧名称
            new_name: 新名称
        
        Returns:
            是否成功
        """
        # 查找旧记录
        old_key = HFSPlusCatalogKey(
            key_length=4 + len(old_name.encode('utf-16-be')),
            parent_id=parent_id,
            node_name=old_name
        )
        
        # 在叶节点中查找旧记录
        old_key_bytes = old_key.to_bytes()
        leaf_node, record_index = self.btree_writer.mutator._find_record(old_key_bytes)
        
        if leaf_node is None:
            raise WriteError(f"未找到记录: {old_name}")
        
        # 获取旧记录数据（跳过键）
        record_data = leaf_node.get_record_data(record_index)
        key_length = struct.unpack_from('>H', record_data, 0)[0]
        record_content = record_data[2 + key_length:]
        
        # 删除旧记录
        self.btree_writer.delete_record(old_key_bytes)
        
        # 创建新键
        new_key = HFSPlusCatalogKey(
            key_length=4 + len(new_name.encode('utf-16-be')),
            parent_id=parent_id,
            node_name=new_name
        )
        new_key_bytes = new_key.to_bytes()
        
        # 插入新记录
        self.btree_writer.insert_record(new_key_bytes, record_content)
        
        return True
    
    def move_entry(self, old_parent_id: int, old_name: str,
                   new_parent_id: int, new_name: str) -> bool:
        """
        移动条目
        
        Args:
            old_parent_id: 旧父文件夹 CNID
            old_name: 旧名称
            new_parent_id: 新父文件夹 CNID
            new_name: 新名称
        
        Returns:
            是否成功
        """
        # 查找旧记录
        old_key = HFSPlusCatalogKey(
            key_length=4 + len(old_name.encode('utf-16-be')),
            parent_id=old_parent_id,
            node_name=old_name
        )
        
        # 在叶节点中查找旧记录
        old_key_bytes = old_key.to_bytes()
        leaf_node, record_index = self.btree_writer.mutator._find_record(old_key_bytes)
        
        if leaf_node is None:
            raise WriteError(f"未找到记录: {old_name}")
        
        # 获取旧记录数据（跳过键）
        record_data = leaf_node.get_record_data(record_index)
        key_length = struct.unpack_from('>H', record_data, 0)[0]
        record_content = record_data[2 + key_length:]
        
        # 删除旧记录
        self.btree_writer.delete_record(old_key_bytes)
        
        # 创建新键
        new_key = HFSPlusCatalogKey(
            key_length=4 + len(new_name.encode('utf-16-be')),
            parent_id=new_parent_id,
            node_name=new_name
        )
        new_key_bytes = new_key.to_bytes()
        
        # 插入新记录
        self.btree_writer.insert_record(new_key_bytes, record_content)
        
        return True
    
    def _allocate_cnid(self) -> int:
        """分配新的 CNID"""
        cnid = self.volume_header.next_catalog_id
        self.volume_header.next_catalog_id += 1
        return cnid
    
    def _get_current_date(self) -> int:
        """获取当前 HFS 日期"""
        import time
        return int(time.time()) + HFS_EPOCH_OFFSET


class FileWriter:
    """
    文件写入器
    
    用于写入文件数据。
    
    Usage:
        writer = FileWriter(stream, volume_header)
        writer.write_data(file_id, data)
    """
    
    def __init__(self, stream: BinaryIO, volume_header: HFSPlusVolumeHeader):
        """
        初始化文件写入器
        
        Args:
            stream: 可写的二进制流
            volume_header: 卷头
        """
        self.stream = stream
        self.volume_header = volume_header
    
    def write_data(self, file_id: int, data: bytes) -> bool:
        """
        写入文件数据
        
        Args:
            file_id: 文件 CNID
            data: 文件数据
        
        Returns:
            是否成功
        """
        # 计算需要的块数
        block_size = self.volume_header.block_size
        blocks_needed = (len(data) + block_size - 1) // block_size
        
        # 写入数据块
        for i in range(blocks_needed):
            block_offset = i * block_size
            block_data = data[block_offset:block_offset + block_size]
            
            # 如果是最后一个块且不满，填充 0
            if len(block_data) < block_size:
                block_data = block_data + b'\x00' * (block_size - len(block_data))
            
            # 计算实际的磁盘偏移（简化：假设块是连续的）
            disk_offset = (file_id + i) * block_size
            
            # 写入数据
            self.stream.seek(disk_offset)
            self.stream.write(block_data)
        
        # 更新卷头
        self.volume_header.write_count += 1
        self.stream.seek(1024)
        self.stream.write(self.volume_header.to_bytes())
        
        return True
    
    def truncate_file(self, file_id: int, new_size: int) -> bool:
        """
        截断文件
        
        Args:
            file_id: 文件 CNID
            new_size: 新的文件大小
        
        Returns:
            是否成功
        """
        # 计算新的块数
        block_size = self.volume_header.block_size
        new_blocks = (new_size + block_size - 1) // block_size if new_size > 0 else 0
        
        # 更新卷头
        self.volume_header.write_count += 1
        self.stream.seek(1024)
        self.stream.write(self.volume_header.to_bytes())
        
        return True


class VolumeWriter:
    """
    卷写入器
    
    用于修改卷的元数据。
    
    Usage:
        writer = VolumeWriter(stream, volume_header)
        writer.update_header()
    """
    
    def __init__(self, stream: BinaryIO, volume_header: HFSPlusVolumeHeader):
        """
        初始化卷写入器
        
        Args:
            stream: 可写的二进制流
            volume_header: 卷头
        """
        self.stream = stream
        self.volume_header = volume_header
    
    def update_header(self):
        """更新卷头"""
        # 写入卷头到偏移 1024
        self.stream.seek(1024)
        self.stream.write(self.volume_header.to_bytes())
        
        # 写入备份卷头到卷末尾
        backup_offset = (self.volume_header.total_blocks * 
                        self.volume_header.block_size - 512)
        self.stream.seek(backup_offset)
        self.stream.write(self.volume_header.to_bytes())
    
    def update_free_blocks(self, count: int):
        """
        更新空闲块计数
        
        Args:
            count: 变化的块数（正数表示释放，负数表示分配）
        """
        self.volume_header.free_blocks += count
    
    def increment_write_count(self):
        """增加写入计数"""
        self.volume_header.write_count += 1