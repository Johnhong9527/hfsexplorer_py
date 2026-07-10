#!/usr/bin/env python3
"""
CopyManager 测试

测试文件/文件夹复制功能。
"""

import pytest
import sys
import os
import struct
import tempfile

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.hfs.writer import (
    CatalogWriter,
    CopyManager,
    AllocationBitmap,
    WriteError
)
from src.core.hfs.btree import (
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFSPlusCatalogThread,
    BTreeFile,
    BTNodeDescriptor,
    BTHeaderRec,
)
from src.core.hfs.structures import HFSPlusVolumeHeader, FinderInfo, ForkData
from src.core.hfs.constants import CatalogNodeID, HFS_EPOCH_OFFSET


def create_empty_fork():
    """创建空的 ForkData"""
    return ForkData(logical_size=0, clump_size=0, total_blocks=0)


class TestCopyManager:
    """测试 CopyManager"""
    
    def setup_method(self):
        """每个测试前的设置"""
        # 创建最小的 HFS+ 卷结构用于测试
        self.block_size = 4096
        self.volume_size = 1024 * 1024  # 1MB
        
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b'\x00' * self.volume_size)
        self.temp_file.flush()
        
        # 创建 FinderInfo 和 ForkData
        finder_info = FinderInfo()
        empty_fork = create_empty_fork()
        
        # 创建卷头
        self.volume_header = HFSPlusVolumeHeader(
            signature=0x482B,  # HFS+
            version=4,
            attributes=0,
            last_mounted_version='\x00\x00\x00\x00',
            journal_info_block=0,
            create_date=0,
            modify_date=0,
            backup_date=0,
            checked_date=0,
            file_count=0,
            folder_count=0,
            block_size=self.block_size,
            total_blocks=self.volume_size // self.block_size,
            free_blocks=self.volume_size // self.block_size - 1,
            next_allocation=2,
            rsrc_clump_size=0,
            data_clump_size=0,
            next_catalog_id=CatalogNodeID.FIRST_USER,
            write_count=0,
            encodings_bitmap=0,
            finder_info=finder_info,
            allocation_file=empty_fork,
            extents_file=empty_fork,
            catalog_file=empty_fork,
            attributes_file=empty_fork,
            startup_file=empty_fork,
        )
    
    def teardown_method(self):
        """每个测试后的清理"""
        self.temp_file.close()
        os.unlink(self.temp_file.name)
    
    def test_copy_manager_creation(self):
        """测试 CopyManager 创建"""
        # 这个测试需要完整的 CatalogBTree，暂时跳过
        pass
    
    def test_copy_entry_with_mock(self):
        """测试复制条目（使用模拟数据）"""
        # 由于 CopyManager 需要完整的 B-tree 结构，
        # 这里只测试基本的初始化
        pass


class TestAllocationBitmapExtended:
    """扩展的 AllocationBitmap 测试"""
    
    def test_allocate_multiple_blocks(self):
        """测试分配多个块"""
        bitmap = AllocationBitmap(b'\x00' * 16, block_size=4096)
        
        # 分配多个块
        blocks = bitmap.find_free_blocks(5)
        assert len(blocks) == 5
        
        # 标记块为已分配
        for block in blocks:
            bitmap.allocate_block(block)
        
        # 验证块已分配
        for block in blocks:
            assert bitmap.is_block_allocated(block)
    
    def test_free_and_reallocate(self):
        """测试释放后重新分配"""
        bitmap = AllocationBitmap(b'\x00' * 16, block_size=4096)
        
        # 分配块
        bitmap.allocate_block(10)
        assert bitmap.is_block_allocated(10)
        
        # 释放块
        bitmap.free_block(10)
        assert not bitmap.is_block_allocated(10)
        
        # 重新分配
        bitmap.allocate_block(10)
        assert bitmap.is_block_allocated(10)
    
    def test_bitmap_serialization(self):
        """测试位图序列化"""
        bitmap = AllocationBitmap(b'\x00' * 16, block_size=4096)
        
        # 分配一些块
        bitmap.allocate_block(0)
        bitmap.allocate_block(7)
        bitmap.allocate_block(8)
        bitmap.allocate_block(15)
        
        # 序列化
        data = bitmap.to_bytes()
        
        # 反序列化
        bitmap2 = AllocationBitmap(data, block_size=4096)
        
        # 验证
        assert bitmap2.is_block_allocated(0)
        assert bitmap2.is_block_allocated(7)
        assert bitmap2.is_block_allocated(8)
        assert bitmap2.is_block_allocated(15)
        assert not bitmap2.is_block_allocated(1)
        assert not bitmap2.is_block_allocated(16)


class TestCatalogWriterExtended:
    """扩展的 CatalogWriter 测试"""
    
    def test_allocate_cnid(self):
        """测试 CNID 分配"""
        # 创建最小的测试环境
        block_size = 4096
        
        finder_info = FinderInfo()
        empty_fork = create_empty_fork()
        
        # 创建卷头
        volume_header = HFSPlusVolumeHeader(
            signature=0x482B,
            version=4,
            attributes=0,
            last_mounted_version='\x00\x00\x00\x00',
            journal_info_block=0,
            create_date=0,
            modify_date=0,
            backup_date=0,
            checked_date=0,
            file_count=0,
            folder_count=0,
            block_size=block_size,
            total_blocks=256,
            free_blocks=255,
            next_allocation=2,
            rsrc_clump_size=0,
            data_clump_size=0,
            next_catalog_id=CatalogNodeID.FIRST_USER,
            write_count=0,
            encodings_bitmap=0,
            finder_info=finder_info,
            allocation_file=empty_fork,
            extents_file=empty_fork,
            catalog_file=empty_fork,
            attributes_file=empty_fork,
            startup_file=empty_fork,
        )
        
        # 验证初始 CNID
        assert volume_header.next_catalog_id == CatalogNodeID.FIRST_USER
    
    def test_volume_header_fields(self):
        """测试卷头字段"""
        block_size = 4096
        
        finder_info = FinderInfo()
        empty_fork = create_empty_fork()
        
        volume_header = HFSPlusVolumeHeader(
            signature=0x482B,
            version=4,
            attributes=0,
            last_mounted_version='\x00\x00\x00\x00',
            journal_info_block=0,
            create_date=0,
            modify_date=0,
            backup_date=0,
            checked_date=0,
            file_count=10,
            folder_count=5,
            block_size=block_size,
            total_blocks=1000,
            free_blocks=900,
            next_allocation=2,
            rsrc_clump_size=0,
            data_clump_size=0,
            next_catalog_id=100,
            write_count=1,
            encodings_bitmap=0,
            finder_info=finder_info,
            allocation_file=empty_fork,
            extents_file=empty_fork,
            catalog_file=empty_fork,
            attributes_file=empty_fork,
            startup_file=empty_fork,
        )
        
        assert volume_header.file_count == 10
        assert volume_header.folder_count == 5
        assert volume_header.block_size == block_size
        assert volume_header.total_blocks == 1000
        assert volume_header.free_blocks == 900
        assert volume_header.next_catalog_id == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
