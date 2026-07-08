"""
HFS+ 文件数据写入器

用于写入文件数据到 HFS+ 卷。
"""

import struct
from typing import Optional, List, BinaryIO
from dataclasses import dataclass

from .btree import (
    BTreeFile,
    HFSPlusCatalogKey,
    HFSPlusCatalogFile,
    HFSPlusExtentKey,
    HFSPlusExtentRecord,
    HFSPlusExtentDescriptor,
    CatalogRecordType,
)
from .structures import HFSPlusVolumeHeader
from .writer import WriteError, AllocationBitmap


@dataclass
class WriteResult:
    """
    写入结果
    
    Attributes:
        success: 是否成功
        bytes_written: 写入的字节数
        blocks_allocated: 分配的块数
        error: 错误信息（如果失败）
    """
    success: bool
    bytes_written: int = 0
    blocks_allocated: int = 0
    error: Optional[str] = None


class FileDataWriter:
    """
    文件数据写入器
    
    用于写入文件数据。
    
    Usage:
        writer = FileDataWriter(stream, catalog, volume_header, bitmap)
        result = writer.write_data(file_id, data)
    """
    
    def __init__(self, stream: BinaryIO, catalog: BTreeFile,
                 volume_header: HFSPlusVolumeHeader,
                 bitmap: AllocationBitmap):
        """
        初始化文件数据写入器
        
        Args:
            stream: 可读写的二进制流
            catalog: Catalog B-tree
            volume_header: 卷头
            bitmap: 分配位图
        """
        self.stream = stream
        self.catalog = catalog
        self.volume_header = volume_header
        self.bitmap = bitmap
        self.block_size = volume_header.block_size
    
    def write_data(self, file_id: int, data: bytes, 
                   offset: int = 0) -> WriteResult:
        """
        写入文件数据
        
        Args:
            file_id: 文件 CNID
            data: 要写入的数据
            offset: 写入偏移量
        
        Returns:
            写入结果
        """
        try:
            # 查找文件记录
            file_record, key = self._find_file_record(file_id)
            if file_record is None:
                return WriteResult(
                    success=False,
                    error=f"未找到文件: {file_id}"
                )
            
            # 计算需要的块数
            end_offset = offset + len(data)
            current_blocks = file_record.data_fork_blocks
            
            # 计算新的块数
            new_blocks_needed = (end_offset + self.block_size - 1) // self.block_size
            
            # 如果需要更多块，分配新块
            if new_blocks_needed > current_blocks:
                blocks_to_allocate = new_blocks_needed - current_blocks
                allocated_blocks = self._allocate_blocks(blocks_to_allocate)
                
                if len(allocated_blocks) < blocks_to_allocate:
                    return WriteResult(
                        success=False,
                        error="没有足够的空闲块"
                    )
                
                # 更新 extent 记录
                self._update_extents(file_id, allocated_blocks, current_blocks)
            
            # 写入数据
            bytes_written = self._write_data_blocks(data, offset)
            
            # 更新文件记录
            self._update_file_record(file_id, end_offset, new_blocks_needed)
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(
                success=True,
                bytes_written=bytes_written,
                blocks_allocated=max(0, new_blocks_needed - current_blocks)
            )
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def truncate_file(self, file_id: int, new_size: int) -> WriteResult:
        """
        截断文件
        
        Args:
            file_id: 文件 CNID
            new_size: 新的文件大小
        
        Returns:
            写入结果
        """
        try:
            # 查找文件记录
            file_record, key = self._find_file_record(file_id)
            if file_record is None:
                return WriteResult(
                    success=False,
                    error=f"未找到文件: {file_id}"
                )
            
            # 计算新的块数
            new_blocks_needed = (new_size + self.block_size - 1) // self.block_size
            current_blocks = file_record.data_fork_blocks
            
            # 如果需要释放块
            if new_blocks_needed < current_blocks:
                blocks_to_free = current_blocks - new_blocks_needed
                self._free_blocks(file_id, blocks_to_free, new_blocks_needed)
            
            # 更新文件记录
            self._update_file_record(file_id, new_size, new_blocks_needed)
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(
                success=True,
                bytes_written=0,
                blocks_allocated=0
            )
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def _find_file_record(self, file_id: int):
        """
        查找文件记录
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            (文件记录, 键)
        """
        for node in self.catalog.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusCatalogKey.from_bytes(data)
                
                # 解析记录类型
                record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                
                if record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                    if file.file_id == file_id:
                        return file, key
        
        return None, None
    
    def _allocate_blocks(self, count: int) -> List[int]:
        """
        分配块
        
        Args:
            count: 需要的块数
        
        Returns:
            分配的块号列表
        """
        return self.bitmap.find_free_blocks(count)
    
    def _free_blocks(self, file_id: int, count: int, start_block_index: int):
        """
        释放块
        
        Args:
            file_id: 文件 CNID
            count: 要释放的块数
            start_block_index: 起始块索引
        """
        # TODO: 实现块释放
        # 这需要：
        # 1. 读取 extent 记录
        # 2. 找到要释放的块
        # 3. 更新位图
        # 4. 更新 extent 记录
        pass
    
    def _update_extents(self, file_id: int, new_blocks: List[int], 
                       current_block_count: int):
        """
        更新 extent 记录
        
        Args:
            file_id: 文件 CNID
            new_blocks: 新分配的块号列表
            current_block_count: 当前块数
        """
        # TODO: 实现 extent 更新
        # 这需要：
        # 1. 读取现有的 extent 记录
        # 2. 添加新的 extent 描述符
        # 3. 如果超过 8 个 extent，写入溢出文件
        pass
    
    def _write_data_blocks(self, data: bytes, offset: int) -> int:
        """
        写入数据块
        
        Args:
            data: 数据
            offset: 偏移量
        
        Returns:
            写入的字节数
        """
        # 计算起始块和结束块
        start_block = offset // self.block_size
        end_block = (offset + len(data) + self.block_size - 1) // self.block_size
        
        bytes_written = 0
        data_offset = 0
        
        for block_number in range(start_block, end_block):
            # 计算块内的偏移和长度
            if block_number == start_block:
                block_offset = offset % self.block_size
                block_length = min(self.block_size - block_offset, len(data) - data_offset)
            else:
                block_offset = 0
                block_length = min(self.block_size, len(data) - data_offset)
            
            # 读取块（如果需要部分写入）
            if block_offset > 0 or block_length < self.block_size:
                # 部分写入，需要先读取现有数据
                # TODO: 实现部分写入
                pass
            else:
                # 完整块写入
                self.stream.seek(block_number * self.block_size)
                self.stream.write(data[data_offset:data_offset + block_length])
            
            data_offset += block_length
            bytes_written += block_length
        
        return bytes_written
    
    def _update_file_record(self, file_id: int, new_size: int, 
                           new_block_count: int):
        """
        更新文件记录
        
        Args:
            file_id: 文件 CNID
            new_size: 新的文件大小
            new_block_count: 新的块数
        """
        # TODO: 实现文件记录更新
        # 这需要：
        # 1. 查找文件记录
        # 2. 更新逻辑大小
        # 3. 更新总块数
        # 4. 更新修改日期
        # 5. 写入记录
        pass
    
    def _update_volume_header(self):
        """更新卷头"""
        # 更新写入计数
        self.volume_header.write_count += 1
        
        # 写入卷头
        self.stream.seek(1024)
        self.stream.write(self.volume_header.to_bytes())
        
        # 写入备份卷头
        backup_offset = (self.volume_header.total_blocks * 
                        self.volume_header.block_size - 512)
        self.stream.seek(backup_offset)
        self.stream.write(self.volume_header.to_bytes())


class ExtentWriter:
    """
    Extent 写入器
    
    用于管理文件的 extent。
    
    Usage:
        writer = ExtentWriter(stream, extents_btree, volume_header, bitmap)
        writer.allocate_extents(file_id, fork_type, count)
    """
    
    def __init__(self, stream: BinaryIO, extents_btree: BTreeFile,
                 volume_header: HFSPlusVolumeHeader,
                 bitmap: AllocationBitmap):
        """
        初始化 Extent 写入器
        
        Args:
            stream: 可读写的二进制流
            extents_btree: Extents B-tree
            volume_header: 卷头
            bitmap: 分配位图
        """
        self.stream = stream
        self.extents_btree = extents_btree
        self.volume_header = volume_header
        self.bitmap = bitmap
        self.block_size = volume_header.block_size
    
    def allocate_extents(self, file_id: int, fork_type: int,
                        count: int) -> List[HFSPlusExtentDescriptor]:
        """
        分配 extent
        
        Args:
            file_id: 文件 CNID
            fork_type: Fork 类型 (0=数据, 0xFF=资源)
            count: 需要的块数
        
        Returns:
            分配的 extent 列表
        """
        # 分配块
        blocks = self.bitmap.find_free_blocks(count)
        
        if len(blocks) < count:
            raise WriteError("没有足够的空闲块")
        
        # 创建 extent 描述符
        extents = self._create_extents_from_blocks(blocks)
        
        # 写入 extent 记录
        self._write_extents(file_id, fork_type, 0, extents)
        
        return extents
    
    def _create_extents_from_blocks(self, blocks: List[int]) -> List[HFSPlusExtentDescriptor]:
        """
        从块列表创建 extent 描述符
        
        Args:
            blocks: 块号列表
        
        Returns:
            extent 描述符列表
        """
        if not blocks:
            return []
        
        extents = []
        current_start = blocks[0]
        current_count = 1
        
        for i in range(1, len(blocks)):
            if blocks[i] == current_start + current_count:
                # 连续块
                current_count += 1
            else:
                # 不连续，创建新的 extent
                extents.append(HFSPlusExtentDescriptor(
                    start_block=current_start,
                    block_count=current_count
                ))
                current_start = blocks[i]
                current_count = 1
        
        # 添加最后一个 extent
        extents.append(HFSPlusExtentDescriptor(
            start_block=current_start,
            block_count=current_count
        ))
        
        return extents
    
    def _write_extents(self, file_id: int, fork_type: int,
                      start_block: int, extents: List[HFSPlusExtentDescriptor]):
        """
        写入 extent 记录
        
        Args:
            file_id: 文件 CNID
            fork_type: Fork 类型
            start_block: 起始块号
            extents: extent 描述符列表
        """
        # 创建 extent 键
        key = HFSPlusExtentKey(
            key_length=10,
            fork_type=fork_type,
            pad=0,
            file_id=file_id,
            start_block=start_block
        )
        
        # 创建 extent 记录
        record = HFSPlusExtentRecord(extents=extents)
        
        # TODO: 写入 Extents B-tree
        # 这需要使用 BTreeMutator 来插入记录
        pass


class FileWriter:
    """
    文件写入器
    
    用于创建和修改文件。
    
    Usage:
        writer = FileWriter(stream, catalog, extents, volume_header, bitmap)
        writer.create_file(parent_id, "test.txt", data)
    """
    
    def __init__(self, stream: BinaryIO, catalog: BTreeFile,
                 extents: BTreeFile, volume_header: HFSPlusVolumeHeader,
                 bitmap: AllocationBitmap):
        """
        初始化文件写入器
        
        Args:
            stream: 可读写的二进制流
            catalog: Catalog B-tree
            extents: Extents B-tree
            volume_header: 卷头
            bitmap: 分配位图
        """
        self.stream = stream
        self.catalog = catalog
        self.extents = extents
        self.volume_header = volume_header
        self.bitmap = bitmap
        self.data_writer = FileDataWriter(stream, catalog, volume_header, bitmap)
        self.extent_writer = ExtentWriter(stream, extents, volume_header, bitmap)
    
    def create_file(self, parent_id: int, name: str, 
                    data: bytes = b'') -> WriteResult:
        """
        创建文件
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件名
            data: 文件数据
        
        Returns:
            写入结果
        """
        try:
            # 分配新的 CNID
            file_id = self._allocate_cnid()
            
            # 创建 Catalog 记录
            # TODO: 使用 CatalogMutator 创建记录
            
            # 如果有数据，写入数据
            if data:
                result = self.data_writer.write_data(file_id, data)
                if not result.success:
                    return result
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(
                success=True,
                bytes_written=len(data)
            )
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def create_folder(self, parent_id: int, name: str) -> WriteResult:
        """
        创建文件夹
        
        Args:
            parent_id: 父文件夹 CNID
            name: 文件夹名称
        
        Returns:
            写入结果
        """
        try:
            # 分配新的 CNID
            folder_id = self._allocate_cnid()
            
            # 创建 Catalog 记录
            # TODO: 使用 CatalogMutator 创建记录
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(success=True)
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def delete_file(self, file_id: int) -> WriteResult:
        """
        删除文件
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            写入结果
        """
        try:
            # 释放块
            # TODO: 释放文件占用的块
            
            # 删除 Catalog 记录
            # TODO: 使用 CatalogMutator 删除记录
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(success=True)
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def delete_folder(self, folder_id: int, recursive: bool = False) -> WriteResult:
        """
        删除文件夹
        
        Args:
            folder_id: 文件夹 CNID
            recursive: 是否递归删除
        
        Returns:
            写入结果
        """
        try:
            # 检查文件夹是否为空
            # TODO: 检查文件夹内容
            
            # 如果递归删除，删除所有子项
            if recursive:
                # TODO: 实现递归删除
                pass
            
            # 删除 Catalog 记录
            # TODO: 使用 CatalogMutator 删除记录
            
            # 更新卷头
            self._update_volume_header()
            
            return WriteResult(success=True)
        
        except Exception as e:
            return WriteResult(
                success=False,
                error=str(e)
            )
    
    def _allocate_cnid(self) -> int:
        """分配新的 CNID"""
        cnid = self.volume_header.next_catalog_id
        self.volume_header.next_catalog_id += 1
        return cnid
    
    def _update_volume_header(self):
        """更新卷头"""
        self.volume_header.write_count += 1
        
        self.stream.seek(1024)
        self.stream.write(self.volume_header.to_bytes())
        
        backup_offset = (self.volume_header.total_blocks * 
                        self.volume_header.block_size - 512)
        self.stream.seek(backup_offset)
        self.stream.write(self.volume_header.to_bytes())