"""
HFS+ 写入功能集成测试

测试完整的写入流程：创建文件、删除文件、重命名等。
"""

import pytest
import struct
import time
from io import BytesIO

from src.core.hfs.btree import (
    BTNodeDescriptor,
    BTHeaderRec,
    BTreeFile,
    CatalogBTree,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    CatalogRecordType,
)
from src.core.hfs.btree_mutator import (
    BTreeMutator,
    CatalogMutator,
)
from src.core.hfs.writer import (
    AllocationBitmap,
    CatalogWriter,
    WriteError,
)
from src.core.hfs.structures import HFSPlusVolumeHeader
from src.core.hfs.constants import BTreeNodeKind, HFS_EPOCH_OFFSET, BTREE_NODE_DESCRIPTOR_SIZE


class TestCatalogWriterIntegration:
    """Catalog 写入器集成测试"""
    
    def _create_test_volume(self) -> tuple:
        """创建一个测试用的 HFS+ 卷"""
        from src.core.hfs.structures import FinderInfo, ForkData
        
        # 创建空的 ForkData
        empty_fork = ForkData(
            logical_size=0,
            clump_size=0,
            total_blocks=0,
            extents=[]
        )
        
        # 创建空的 FinderInfo
        empty_finder = FinderInfo()
        
        # 创建卷头
        volume_header = HFSPlusVolumeHeader(
            signature=0x482B,  # HFS+
            version=4,
            attributes=0,
            last_mounted_version='10.0',
            journal_info_block=0,
            create_date=1000000,
            modify_date=1000000,
            backup_date=0,
            checked_date=1000000,
            file_count=0,
            folder_count=1,  # 根目录
            block_size=4096,
            total_blocks=1000,
            free_blocks=999,
            next_allocation=100,
            rsrc_clump_size=0,
            data_clump_size=0,
            next_catalog_id=16,  # 第一个用户 CNID
            write_count=1,
            encodings_bitmap=0,
            finder_info=empty_finder,
            allocation_file=empty_fork,
            extents_file=empty_fork,
            catalog_file=empty_fork,
            attributes_file=empty_fork,
            startup_file=empty_fork
        )
        
        # 创建 B-tree 数据
        node_size = 4096
        data = bytearray(node_size * 10)  # 10 个节点
        
        # 节点 0: 头节点
        header_desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=BTreeNodeKind.HEADER,
            height=0,
            numRecords=3,
            reserved=0
        )
        data[0:14] = header_desc.to_bytes()
        
        # 头记录
        btree_header = BTHeaderRec(
            treeDepth=1,
            rootNode=1,
            leafRecords=0,
            firstLeafNode=1,
            lastLeafNode=1,
            nodeSize=node_size,
            maxKeyLength=255,
            totalNodes=10,
            freeNodes=8,
            reserved1=0,
            clumpSize=0,
            btreeType=0,
            keyCompareType=0xBC,
            attributes=0
        )
        header_data = btree_header.to_bytes()
        data[14:14 + len(header_data)] = header_data
        
        # 节点 1: 叶节点（空）
        leaf_desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=BTreeNodeKind.LEAF,
            height=1,
            numRecords=0,
            reserved=0
        )
        data[node_size:node_size + 14] = leaf_desc.to_bytes()
        
        # 写入偏移表（空节点只有1个偏移条目，指向空闲空间开始位置）
        struct.pack_into('>H', data, node_size * 2 - 2, BTREE_NODE_DESCRIPTOR_SIZE)
        
        # 创建 BytesIO 对象
        stream = BytesIO(data)
        
        # 创建 Catalog B-tree
        catalog = CatalogBTree(stream, start_offset=0, node_size=node_size)
        
        return catalog, volume_header, stream, data
    
    def test_create_file_in_catalog(self):
        """测试在 Catalog 中创建文件"""
        catalog, volume_header, stream, data = self._create_test_volume()
        
        # 创建 Catalog 写入器
        writer = CatalogWriter(catalog, volume_header, stream)
        
        # 记录初始 CNID
        initial_cnid = volume_header.next_catalog_id
        
        # 创建文件
        file_id = writer.create_file(2, "test.txt", b"Hello, World!")
        
        # 验证 CNID 分配
        assert file_id == initial_cnid
        assert volume_header.next_catalog_id == initial_cnid + 1
    
    def test_create_folder_in_catalog(self):
        """测试在 Catalog 中创建文件夹"""
        catalog, volume_header, stream, data = self._create_test_volume()
        
        writer = CatalogWriter(catalog, volume_header, stream)
        
        initial_cnid = volume_header.next_catalog_id
        
        # 创建文件夹
        folder_id = writer.create_folder(2, "New Folder")
        
        # 验证 CNID 分配
        assert folder_id == initial_cnid
        assert volume_header.next_catalog_id == initial_cnid + 1
    
    def test_catalog_key_construction(self):
        """测试 Catalog 键构建"""
        catalog, volume_header, stream, data = self._create_test_volume()
        
        writer = CatalogWriter(catalog, volume_header, stream)
        
        # 测试不同名称的键构建
        test_cases = [
            (2, "test.txt"),
            (100, "My Folder"),
            (50, "日本語ファイル"),  # Unicode 文件名
        ]
        
        for parent_id, name in test_cases:
            # 构造键
            name_bytes = name.encode('utf-16-be')
            key_length = 4 + len(name_bytes)
            
            # 使用内部方法构建键（通过 CatalogMutator）
            mutator = CatalogMutator(catalog, stream)
            key = mutator._build_catalog_key(parent_id, name)
            
            # 验证键格式
            assert len(key) > 0
            
            # 解析键
            parsed_key_length = struct.unpack_from('>H', key, 0)[0]
            parsed_parent_id = struct.unpack_from('>I', key, 2)[0]
            
            assert parsed_parent_id == parent_id
            assert parsed_key_length == key_length


class TestAllocationBitmapIntegration:
    """分配位图集成测试"""
    
    def test_bitmap_with_real_blocks(self):
        """测试位图与真实块操作"""
        # 创建一个足够大的位图
        bitmap_size = 1024  # 字节 = 8192 位
        data = bytearray(bitmap_size)
        bitmap = AllocationBitmap(bytes(data), block_size=4096)
        
        # 模拟文件系统操作
        # 1. 分配一些块（模拟创建文件）
        file1_blocks = bitmap.find_free_blocks(10, start_block=100)
        for block in file1_blocks:
            bitmap.allocate_block(block)
        
        file2_blocks = bitmap.find_free_blocks(5, start_block=200)
        for block in file2_blocks:
            bitmap.allocate_block(block)
        
        # 验证分配
        for block in file1_blocks:
            assert bitmap.is_block_allocated(block)
        for block in file2_blocks:
            assert bitmap.is_block_allocated(block)
        
        # 2. 释放一些块（模拟删除文件）
        for block in file1_blocks[:5]:
            bitmap.free_block(block)
        
        # 验证部分释放
        for block in file1_blocks[:5]:
            assert not bitmap.is_block_allocated(block)
        for block in file1_blocks[5:]:
            assert bitmap.is_block_allocated(block)
        
        # 3. 重新分配释放的块
        new_blocks = bitmap.find_free_blocks(3, start_block=100)
        assert len(new_blocks) == 3
        
        # 验证新分配的块是之前释放的块
        for block in new_blocks:
            assert block in file1_blocks[:5]
    
    def test_bitmap_exhaustion(self):
        """测试位图耗尽情况"""
        # 创建一个小位图
        data = bytearray(4)  # 32 位
        bitmap = AllocationBitmap(bytes(data), block_size=4096)
        
        # 分配所有块
        for i in range(32):
            bitmap.allocate_block(i)
        
        # 尝试查找空闲块，应该失败
        with pytest.raises(WriteError, match="没有足够的空闲块"):
            bitmap.find_free_blocks(1)


class TestBTreeMutationIntegration:
    """B-tree 变异集成测试"""
    
    def test_btree_header_update(self):
        """测试 B-tree 头更新"""
        node_size = 512
        data = bytearray(node_size * 3)
        
        # 创建头节点
        header_desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=BTreeNodeKind.HEADER,
            height=0,
            numRecords=3,
            reserved=0
        )
        data[0:14] = header_desc.to_bytes()
        
        # 创建头记录
        header = BTHeaderRec(
            treeDepth=1,
            rootNode=1,
            leafRecords=0,
            firstLeafNode=1,
            lastLeafNode=1,
            nodeSize=node_size,
            maxKeyLength=255,
            totalNodes=3,
            freeNodes=1,
            reserved1=0,
            clumpSize=0,
            btreeType=0,
            keyCompareType=0xBC,
            attributes=0
        )
        header_data = header.to_bytes()
        data[14:14 + len(header_data)] = header_data
        
        # 创建叶节点
        leaf_desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=BTreeNodeKind.LEAF,
            height=1,
            numRecords=0,
            reserved=0
        )
        data[node_size:node_size + 14] = leaf_desc.to_bytes()
        
        stream = BytesIO(data)
        btree = BTreeFile(stream, start_offset=0, node_size=node_size)
        
        # 验证头记录
        h = btree.header
        assert h.treeDepth == 1
        assert h.rootNode == 1
        assert h.nodeSize == node_size
        assert h.totalNodes == 3
        assert h.freeNodes == 1
        
        # 修改头记录
        h.leafRecords = 10
        h.freeNodes = 0
        
        # 写入修改后的头记录
        stream.seek(14)
        stream.write(h.to_bytes())
        
        # 重新读取验证
        stream.seek(0)
        btree2 = BTreeFile(stream, start_offset=0, node_size=node_size)
        h2 = btree2.header
        
        assert h2.leafRecords == 10
        assert h2.freeNodes == 0


class TestWriteErrorHandling:
    """写入错误处理测试"""
    
    def test_write_error_hierarchy(self):
        """测试写入错误层次结构"""
        from src.core.hfs.writer import WriteError
        
        # 验证 WriteError 是 Exception 的子类
        assert issubclass(WriteError, Exception)
        
        # 创建不同类型的错误
        errors = [
            WriteError("简单的错误"),
            WriteError("带有详情的错误"),
            WriteError(""),  # 空消息
        ]
        
        for error in errors:
            assert isinstance(error, Exception)
            assert isinstance(error, WriteError)
    
    def test_bitmap_error_handling(self):
        """测试位图错误处理"""
        data = bytearray(4)  # 32 位
        bitmap = AllocationBitmap(bytes(data), block_size=4096)
        
        # 测试超出范围的块号
        with pytest.raises(WriteError):
            bitmap.allocate_block(100)  # 超出 32 位范围
        
        with pytest.raises(WriteError):
            bitmap.free_block(100)  # 超出 32 位范围


class TestWritePerformance:
    """写入性能测试"""
    
    def test_bitmap_performance(self):
        """测试位图性能"""
        # 创建一个大位图
        bitmap_size = 1024 * 1024  # 1MB = 8M 位
        data = bytearray(bitmap_size)
        bitmap = AllocationBitmap(bytes(data), block_size=4096)
        
        # 测试批量分配性能
        start_time = time.time()
        
        blocks_allocated = []
        for i in range(0, 10000, 100):
            block = bitmap.find_free_blocks(1, start_block=i)[0]
            bitmap.allocate_block(block)
            blocks_allocated.append(block)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 验证分配成功
        assert len(blocks_allocated) == 100
        
        # 性能应该很快（小于 1 秒）
        assert elapsed < 1.0
        
        # 测试批量释放性能
        start_time = time.time()
        
        for block in blocks_allocated:
            bitmap.free_block(block)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 验证释放成功
        for block in blocks_allocated:
            assert not bitmap.is_block_allocated(block)
        
        # 性能应该很快
        assert elapsed < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
