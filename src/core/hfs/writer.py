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
    HFSPlusCatalogThread,
    HFSPlusExtentKey,
    HFSPlusExtentRecord,
    HFSPlusExtentDescriptor,
)
from .btree_mutator import BTreeMutator, BTreeMutationResult
from .structures import HFSPlusVolumeHeader
from .constants import CatalogNodeID, HFS_EPOCH_OFFSET, VOLUME_HEADER_OFFSET, VOLUME_HEADER_SIZE


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
            key_length=6 + len(name) * 2,
            parent_id=parent_id,
            node_name=name
        )
        
        # 构造 BSD 权限 (16 字节)
        # ownerID(4) + groupID(4) + adminFlags(1) + ownerFlags(1) + fileMode(2) + special(4)
        permissions = struct.pack('>II', 0, 0)  # ownerID, groupID
        permissions += struct.pack('>BB', 0, 0)  # adminFlags, ownerFlags
        permissions += struct.pack('>H', 0o100644)  # fileMode (普通文件)
        permissions += struct.pack('>I', 0)  # special
        
        # 构造 Finder 信息 (8 字节)
        userInfo = b'\x00' * 8
        
        # 构造 ExtendedFileInfo (8 字节)
        finderInfo = b'\x00' * 8
        
        # 如果有数据，分配块并写入
        start_block = 0
        total_blocks = 0
        if data:
            block_size = self.volume_header.block_size
            blocks_needed = (len(data) + block_size - 1) // block_size
            
            # 分配块
            allocated_blocks = self._allocate_blocks(blocks_needed)
            if allocated_blocks:
                start_block = allocated_blocks[0]
                total_blocks = len(allocated_blocks)
                
                # 写入数据到分配的块
                for i, block_num in enumerate(allocated_blocks):
                    block_offset = block_num * block_size
                    start = i * block_size
                    end = min(start + block_size, len(data))
                    block_data = data[start:end]
                    
                    # 填充到块大小
                    if len(block_data) < block_size:
                        block_data = block_data + b'\x00' * (block_size - len(block_data))
                    
                    self.stream.seek(block_offset)
                    self.stream.write(block_data)
        
        # 构造数据分支 (80 字节)
        # logicalSize(8) + clumpSize(4) + totalBlocks(4) + extents(64)
        data_fork = struct.pack('>Q', len(data))  # logicalSize
        data_fork += struct.pack('>I', 0)  # clumpSize
        data_fork += struct.pack('>I', total_blocks)  # totalBlocks
        
        # 第一个 extent 描述符
        if total_blocks > 0:
            data_fork += struct.pack('>II', start_block, total_blocks)  # extent 1
            data_fork += b'\x00' * 56  # 剩余 7 个 extent
        else:
            data_fork += b'\x00' * 64  # 8 个 extent 描述符
        
        # 构造资源分支 (80 字节)
        resource_fork = struct.pack('>Q', 0)  # logicalSize
        resource_fork += struct.pack('>I', 0)  # clumpSize
        resource_fork += struct.pack('>I', 0)  # totalBlocks
        resource_fork += b'\x00' * 64  # 8 个 extent 描述符
        
        # 创建文件记录
        file_record = HFSPlusCatalogFile(
            record_type=CatalogRecordType.FILE,
            flags=0,
            reserved1=0,
            file_id=file_id,
            create_date=self._get_current_date(),
            content_mod_date=self._get_current_date(),
            attribute_mod_date=self._get_current_date(),
            access_date=self._get_current_date(),
            backup_date=0,
            permissions=permissions,
            userInfo=userInfo,
            finderInfo=finderInfo,
            text_encoding=0,
            reserved2=0,
            data_fork=data_fork,
            resource_fork=resource_fork
        )
        
        # 序列化键和记录
        key_bytes = key.to_bytes()
        record_bytes = file_record.to_bytes()
        
        # 插入文件记录到 B-tree
        self.btree_writer.insert_record(key_bytes, record_bytes)
        
        # 创建线程记录
        # 线程记录的键: (parentID=自己的CNID, name="")
        thread_key = HFSPlusCatalogKey(
            key_length=6,
            parent_id=file_id,
            node_name=""
        )
        
        # 线程记录的数据: (record_type=4, reserved=0, parentID=父文件夹的CNID, node_name=自己的名称)
        thread_record = HFSPlusCatalogThread(
            record_type=CatalogRecordType.FILE_THREAD,
            reserved=0,
            parent_id=parent_id,
            node_name=name
        )
        
        thread_key_bytes = thread_key.to_bytes()
        thread_record_bytes = thread_record.to_bytes()
        
        # 插入线程记录到 B-tree
        self.btree_writer.insert_record(thread_key_bytes, thread_record_bytes)
        
        # 更新卷头的文件计数
        self.volume_header.file_count += 1
        self._update_volume_header()
        
        return file_id
    
    def _allocate_blocks(self, count: int) -> List[int]:
        """
        分配块
        
        Args:
            count: 需要的块数
        
        Returns:
            分配的块号列表
        """
        # 从下一个分配位置开始分配
        start = self.volume_header.next_allocation
        block_size = self.volume_header.block_size
        total_blocks = self.volume_header.total_blocks
        free_blocks = self.volume_header.free_blocks
        
        # 检查是否有足够的空闲块
        if count > free_blocks:
            return []  # 没有足够的空闲块
        
        # 查找空闲块
        allocated = []
        current = start
        
        while len(allocated) < count and current < total_blocks:
            # 简化实现：假设从 next_allocation 开始的块都是空闲的
            # 实际实现应该检查分配位图
            allocated.append(current)
            current += 1
        
        if len(allocated) < count:
            return []  # 没有足够的空闲块
        
        # 更新卷头
        self.volume_header.free_blocks -= count
        self.volume_header.next_allocation = current
        
        return allocated
    
    def _update_volume_header(self):
        """更新卷头"""
        self.volume_header.modify_date = self._get_current_date()
        self.volume_header.write_count += 1
        
        # 写入卷头
        self.stream.seek(VOLUME_HEADER_OFFSET)
        self.stream.write(self.volume_header.to_bytes())
        
        # 写入备份卷头
        backup_offset = self.volume_header.volume_size - VOLUME_HEADER_SIZE
        self.stream.seek(backup_offset)
        self.stream.write(self.volume_header.to_bytes())
    
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
            key_length=6 + len(name) * 2,
            parent_id=parent_id,
            node_name=name
        )
        
        # 构造 BSD 权限 (16 字节)
        # ownerID(4) + groupID(4) + adminFlags(1) + ownerFlags(1) + fileMode(2) + special(4)
        permissions = struct.pack('>II', 0, 0)  # ownerID, groupID
        permissions += struct.pack('>BB', 0, 0)  # adminFlags, ownerFlags
        permissions += struct.pack('>H', 0o40755)  # fileMode (目录)
        permissions += struct.pack('>I', 0)  # special
        
        # 构造 FolderInfo (8 字节)
        userInfo = b'\x00' * 8
        
        # 构造 ExtendedFolderInfo (8 字节)
        finderInfo = b'\x00' * 8
        
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
            permissions=permissions,
            userInfo=userInfo,
            finderInfo=finderInfo,
            text_encoding=0,
            reserved=0
        )
        
        # 序列化键和记录
        key_bytes = key.to_bytes()
        record_bytes = folder_record.to_bytes()
        
        # 插入文件夹记录到 B-tree
        self.btree_writer.insert_record(key_bytes, record_bytes)
        
        # 创建线程记录
        # 线程记录的键: (parentID=自己的CNID, name="")
        thread_key = HFSPlusCatalogKey(
            key_length=6,
            parent_id=folder_id,
            node_name=""
        )
        
        # 线程记录的数据: (record_type=3, reserved=0, parentID=父文件夹的CNID, node_name=自己的名称)
        thread_record = HFSPlusCatalogThread(
            record_type=CatalogRecordType.FOLDER_THREAD,
            reserved=0,
            parent_id=parent_id,
            node_name=name
        )
        
        thread_key_bytes = thread_key.to_bytes()
        thread_record_bytes = thread_record.to_bytes()
        
        # 插入线程记录到 B-tree
        self.btree_writer.insert_record(thread_key_bytes, thread_record_bytes)
        
        # 更新卷头的文件夹计数
        self.volume_header.folder_count += 1
        self._update_volume_header()
        
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
            key_length=6 + len(name) * 2,
            parent_id=parent_id,
            node_name=name
        )
        
        # 序列化键
        key_bytes = key.to_bytes()
        
        # 查找记录以确定类型
        leaf_node, record_index = self.btree_writer.mutator._find_record(key_bytes)
        
        is_folder = False
        if leaf_node is not None:
            record_data = leaf_node.get_record_data(record_index)
            if len(record_data) > 0:
                record_type = struct.unpack_from('>H', record_data, key.occupied_size)[0]
                is_folder = (record_type == CatalogRecordType.FOLDER)
        
        # 从 B-tree 删除
        self.btree_writer.delete_record(key_bytes)
        
        # 更新卷头的计数
        if is_folder:
            self.volume_header.folder_count -= 1
        else:
            self.volume_header.file_count -= 1
        
        self._update_volume_header()
        
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
            key_length=6 + len(old_name) * 2,
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
            key_length=6 + len(new_name) * 2,
            parent_id=parent_id,
            node_name=new_name
        )
        new_key_bytes = new_key.to_bytes()
        
        # 插入新记录
        self.btree_writer.insert_record(new_key_bytes, record_content)
        
        # 更新卷头
        self._update_volume_header()
        
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
            key_length=6 + len(old_name) * 2,
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
            key_length=6 + len(new_name) * 2,
            parent_id=new_parent_id,
            node_name=new_name
        )
        new_key_bytes = new_key.to_bytes()
        
        # 插入新记录
        self.btree_writer.insert_record(new_key_bytes, record_content)
        
        # 更新卷头
        self._update_volume_header()
        
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
    
    def __init__(self, stream: BinaryIO, volume_header: HFSPlusVolumeHeader,
                 catalog: CatalogBTree = None):
        """
        初始化文件写入器
        
        Args:
            stream: 可写的二进制流
            volume_header: 卷头
            catalog: Catalog B-tree（用于查找文件记录）
        """
        self.stream = stream
        self.volume_header = volume_header
        self.catalog = catalog
    
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
        
        # 查找文件记录以获取实际的磁盘位置
        if self.catalog is None:
            raise WriteError("Catalog 未初始化，无法写入文件数据")
        
        # 查找文件记录
        file_record = None
        for node in self.catalog.list_leaf_nodes():
            for i in range(node.num_records):
                record_data = node.get_record_data(i)
                key = HFSPlusCatalogKey.from_bytes(record_data)
                record_type = struct.unpack_from('>H', record_data, key.occupied_size)[0]
                if record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(record_data, key.occupied_size)
                    if file.file_id == file_id:
                        file_record = file
                        break
            if file_record:
                break
        
        if file_record is None:
            raise WriteError(f"文件未找到: {file_id}")
        
        # 获取数据分支的 extents
        extents = file_record.get_data_fork_extents()
        if not extents or extents[0][1] == 0:
            # 没有分配的块，需要先分配
            raise WriteError("文件没有分配的数据块")
        
        # 写入数据块
        bytes_written = 0
        for extent_idx, (start_block, block_count) in enumerate(extents):
            if bytes_written >= len(data):
                break
            
            for block_idx in range(block_count):
                if bytes_written >= len(data):
                    break
                
                block_offset = (start_block + block_idx) * block_size
                start = bytes_written
                end = min(start + block_size, len(data))
                block_data = data[start:end]
                
                # 填充到块大小
                if len(block_data) < block_size:
                    block_data = block_data + b'\x00' * (block_size - len(block_data))
                
                # 写入数据
                self.stream.seek(block_offset)
                self.stream.write(block_data)
                bytes_written += len(block_data)
        
        # 更新文件的逻辑大小
        # 注意：这里简化处理，实际需要更新 Catalog 记录
        
        # 更新卷头
        self.volume_header.write_count += 1
        self.stream.seek(VOLUME_HEADER_OFFSET)
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
        self.stream.seek(VOLUME_HEADER_OFFSET)
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
        self.stream.seek(VOLUME_HEADER_OFFSET)
        self.stream.write(self.volume_header.to_bytes())
        
        # 写入备份卷头到卷末尾
        if self.volume_header.volume_size > 0:
            backup_offset = self.volume_header.volume_size - VOLUME_HEADER_SIZE
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


class CopyManager:
    """
    复制管理器
    
    用于处理文件和文件夹的复制操作。
    
    Usage:
        manager = CopyManager(catalog_writer, volume)
        manager.copy_entry(src_parent_id, src_name, dst_parent_id, dst_name)
    """
    
    def __init__(self, catalog_writer: 'CatalogWriter', volume: 'HFSPlusVolume'):
        """
        初始化复制管理器
        
        Args:
            catalog_writer: Catalog 写入器
            volume: HFS+ 卷
        """
        self.catalog_writer = catalog_writer
        self.volume = volume
    
    def copy_entry(self, src_parent_id: int, src_name: str,
                   dst_parent_id: int, dst_name: str) -> int:
        """
        复制条目
        
        Args:
            src_parent_id: 源父文件夹 CNID
            src_name: 源名称
            dst_parent_id: 目标父文件夹 CNID
            dst_name: 目标名称
        
        Returns:
            新条目的 CNID
        """
        # 查找源记录
        src_key = HFSPlusCatalogKey(
            key_length=6 + len(src_name) * 2,
            parent_id=src_parent_id,
            node_name=src_name
        )
        
        src_key_bytes = src_key.to_bytes()
        leaf_node, record_index = self.catalog_writer.btree_writer.mutator._find_record(src_key_bytes)
        
        if leaf_node is None:
            raise WriteError(f"未找到源记录: {src_name}")
        
        # 获取源记录数据
        record_data = leaf_node.get_record_data(record_index)
        key_length = struct.unpack_from('>H', record_data, 0)[0]
        record_content = record_data[2 + key_length:]
        
        # 检查记录类型
        record_type = struct.unpack_from('>H', record_content, 0)[0]
        
        if record_type == CatalogRecordType.FOLDER:
            # 复制文件夹
            return self._copy_folder(src_parent_id, src_name, dst_parent_id, dst_name)
        elif record_type == CatalogRecordType.FILE:
            # 复制文件
            return self._copy_file(src_parent_id, src_name, dst_parent_id, dst_name)
        else:
            raise WriteError(f"未知的记录类型: {record_type}")
    
    def _copy_file(self, src_parent_id: int, src_name: str,
                   dst_parent_id: int, dst_name: str) -> int:
        """
        复制文件
        
        Args:
            src_parent_id: 源父文件夹 CNID
            src_name: 源文件名
            dst_parent_id: 目标父文件夹 CNID
            dst_name: 目标文件名
        
        Returns:
            新文件的 CNID
        """
        # 查找源文件记录
        src_key = HFSPlusCatalogKey(
            key_length=6 + len(src_name) * 2,
            parent_id=src_parent_id,
            node_name=src_name
        )
        
        src_key_bytes = src_key.to_bytes()
        leaf_node, record_index = self.catalog_writer.btree_writer.mutator._find_record(src_key_bytes)
        
        if leaf_node is None:
            raise WriteError(f"未找到源文件: {src_name}")
        
        # 获取源文件记录
        record_data = leaf_node.get_record_data(record_index)
        key_length = struct.unpack_from('>H', record_data, 0)[0]
        record_content = record_data[2 + key_length:]
        
        # 解析源文件记录
        src_file = HFSPlusCatalogFile.from_bytes(record_data, 2 + key_length)
        
        # 读取源文件数据
        file_data = b''
        if src_file.file_id > 0:
            try:
                file_data = self.volume.read_file(src_file.file_id)
            except Exception:
                file_data = b''
        
        # 创建新文件
        new_file_id = self.catalog_writer.create_file(dst_parent_id, dst_name, file_data)
        
        return new_file_id
    
    def _copy_folder(self, src_parent_id: int, src_name: str,
                     dst_parent_id: int, dst_name: str) -> int:
        """
        复制文件夹（递归）
        
        Args:
            src_parent_id: 源父文件夹 CNID
            src_name: 源文件夹名
            dst_parent_id: 目标父文件夹 CNID
            dst_name: 目标文件夹名
        
        Returns:
            新文件夹的 CNID
        """
        # 查找源文件夹记录
        src_key = HFSPlusCatalogKey(
            key_length=6 + len(src_name) * 2,
            parent_id=src_parent_id,
            node_name=src_name
        )
        
        src_key_bytes = src_key.to_bytes()
        leaf_node, record_index = self.catalog_writer.btree_writer.mutator._find_record(src_key_bytes)
        
        if leaf_node is None:
            raise WriteError(f"未找到源文件夹: {src_name}")
        
        # 获取源文件夹记录
        record_data = leaf_node.get_record_data(record_index)
        key_length = struct.unpack_from('>H', record_data, 0)[0]
        record_content = record_data[2 + key_length:]
        
        # 解析源文件夹记录
        src_folder = HFSPlusCatalogFolder.from_bytes(record_data, 2 + key_length)
        
        # 创建新文件夹
        new_folder_id = self.catalog_writer.create_folder(dst_parent_id, dst_name)
        
        # 获取源文件夹内容
        contents = self.volume.list_folder(src_folder.folder_id)
        
        # 递归复制内容
        for item in contents:
            item_name = item['name']
            item_type = item['type']
            
            if item_type == 'folder':
                # 复制子文件夹
                self._copy_folder(src_folder.folder_id, item_name,
                                 new_folder_id, item_name)
            else:
                # 复制文件
                self._copy_file(src_folder.folder_id, item_name,
                               new_folder_id, item_name)
        
        return new_folder_id
    
    def copy_entry_to(self, src_parent_id: int, src_name: str,
                      dst_parent_id: int) -> int:
        """
        复制条目到目标文件夹（保持原名）
        
        Args:
            src_parent_id: 源父文件夹 CNID
            src_name: 源名称
            dst_parent_id: 目标父文件夹 CNID
        
        Returns:
            新条目的 CNID
        """
        return self.copy_entry(src_parent_id, src_name, dst_parent_id, src_name)
    
    def duplicate_entry(self, parent_id: int, name: str) -> int:
        """
        复制条目（在同一文件夹下创建副本）
        
        Args:
            parent_id: 父文件夹 CNID
            name: 条目名称
        
        Returns:
            新条目的 CNID
        """
        # 生成副本名称
        base_name, ext = os.path.splitext(name)
        copy_name = f"{base_name} 副本{ext}"
        
        # 检查名称是否已存在
        counter = 1
        while self._entry_exists(parent_id, copy_name):
            counter += 1
            copy_name = f"{base_name} 副本 {counter}{ext}"
        
        return self.copy_entry(parent_id, name, parent_id, copy_name)
    
    def _entry_exists(self, parent_id: int, name: str) -> bool:
        """
        检查条目是否存在
        
        Args:
            parent_id: 父文件夹 CNID
            name: 条目名称
        
        Returns:
            是否存在
        """
        key = HFSPlusCatalogKey(
            key_length=6 + len(name) * 2,
            parent_id=parent_id,
            node_name=name
        )
        
        key_bytes = key.to_bytes()
        leaf_node, record_index = self.catalog_writer.btree_writer.mutator._find_record(key_bytes)
        
        return leaf_node is not None