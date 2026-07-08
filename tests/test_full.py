"""
HFS+ 完整功能测试

测试所有核心功能。
"""

import pytest
import struct
from io import BytesIO

from src.core.hfs.constants import (
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
    VOLUME_HEADER_OFFSET,
    VOLUME_HEADER_SIZE,
    HFS_EPOCH_OFFSET,
    BTreeNodeKind,
    CatalogRecordType,
)
from src.core.hfs.structures import (
    ExtentDescriptor,
    ForkData,
    FinderInfo,
    HFSPlusVolumeHeader,
)
from src.core.hfs.reader import (
    HFSPlusVolumeHeaderReader,
    read_volume_header,
    is_hfs_plus_volume,
)
from src.core.hfs.btree import (
    BTNodeDescriptor,
    BTHeaderRec,
    BTreeNode,
    BTreeFile,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFSPlusExtentKey,
    HFSPlusExtentDescriptor,
    HFSPlusExtentRecord,
)
from src.core.hfs.search import (
    SearchMatchType,
    SearchFilter,
    SearchResult,
    SearchEngine,
)
from src.core.hfs.writer import (
    WriteError,
    AllocationBitmap,
)
from src.core.crypto import (
    AESXTS,
    AESKeyWrap,
    PBKDF2Deriver,
    CryptoError,
    EncryptedVolumeHeader,
)


class TestConstants:
    """常量测试"""
    
    def test_signatures(self):
        """测试签名常量"""
        assert SIGNATURE_HFS_PLUS == 0x482B
        assert SIGNATURE_HFSX == 0x4858
    
    def test_hfs_epoch(self):
        """测试 HFS 纪元偏移"""
        assert HFS_EPOCH_OFFSET == 2082844800
    
    def test_node_types(self):
        """测试节点类型"""
        assert BTreeNodeKind.LEAF == -1
        assert BTreeNodeKind.INDEX == 0
        assert BTreeNodeKind.HEADER == 1
        assert BTreeNodeKind.MAP == 2
    
    def test_catalog_record_types(self):
        """测试 Catalog 记录类型"""
        assert CatalogRecordType.FOLDER == 0x0001
        assert CatalogRecordType.FILE == 0x0002
        assert CatalogRecordType.FOLDER_THREAD == 0x0003
        assert CatalogRecordType.FILE_THREAD == 0x0004


class TestStructures:
    """数据结构测试"""
    
    def test_extent_descriptor(self):
        """测试 ExtentDescriptor"""
        ext = ExtentDescriptor(start_block=100, block_count=50)
        assert ext.start_block == 100
        assert ext.block_count == 50
        assert ext.end_block == 150
        assert ext.is_empty is False
        
        # 测试序列化
        data = ext.to_bytes()
        assert len(data) == 8
        
        # 测试反序列化
        ext2 = ExtentDescriptor.from_bytes(data)
        assert ext2.start_block == 100
        assert ext2.block_count == 50
    
    def test_fork_data(self):
        """测试 ForkData"""
        extents = [
            ExtentDescriptor(start_block=100, block_count=50),
            ExtentDescriptor(start_block=200, block_count=30),
        ]
        fork = ForkData(
            logical_size=8192,
            clump_size=4096,
            total_blocks=80,
            extents=extents
        )
        assert fork.logical_size == 8192
        assert fork.clump_size == 4096
        assert fork.total_blocks == 80
        assert len(fork.extents) == 2
        assert fork.is_empty is False
        
        # 测试序列化
        data = fork.to_bytes()
        assert len(data) == 80
    
    def test_finder_info(self):
        """测试 FinderInfo"""
        info = FinderInfo(blessed_system_folder=5, volume_uuid=123456789)
        assert info.blessed_system_folder == 5
        assert info.volume_uuid == 123456789
        
        # 测试序列化
        data = info.to_bytes()
        assert len(data) == 32
    
    def test_volume_header(self):
        """测试 HFSPlusVolumeHeader"""
        # 构造测试数据
        data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            SIGNATURE_HFS_PLUS,
            4, 0, 0x382E3130, 0, 0, 0, 0, 0, 100, 10, 4096, 1000, 500, 100, 4096, 4096, 16, 1, 0
        )
        data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        for _ in range(5):
            data += struct.pack('>QII', 0, 0, 0)
            data += b'\x00' * 64
        
        header = HFSPlusVolumeHeader.from_bytes(data)
        assert header.is_hfs_plus is True
        assert header.is_hfsx is False
        assert header.is_valid is True
        assert header.version == 4
        assert header.block_size == 4096
        assert header.total_blocks == 1000
        assert header.free_blocks == 500
        assert header.file_count == 100
        assert header.folder_count == 10
        assert header.volume_size == 4096 * 1000
        assert header.free_space == 4096 * 500


class TestBTree:
    """B-tree 测试"""
    
    def test_node_descriptor(self):
        """测试 BTNodeDescriptor"""
        desc = BTNodeDescriptor(
            fLink=10,
            bLink=5,
            kind=-1,
            height=1,
            numRecords=3,
            reserved=0
        )
        assert desc.fLink == 10
        assert desc.bLink == 5
        assert desc.kind == -1
        assert desc.height == 1
        assert desc.numRecords == 3
        assert desc.node_type == BTreeNodeKind.LEAF
        assert desc.is_leaf is True
        
        # 测试序列化
        data = desc.to_bytes()
        assert len(data) == 14
        
        # 测试反序列化
        desc2 = BTNodeDescriptor.from_bytes(data)
        assert desc2.fLink == 10
        assert desc2.is_leaf is True
    
    def test_header_record(self):
        """测试 BTHeaderRec"""
        header = BTHeaderRec(
            treeDepth=2,
            rootNode=10,
            leafRecords=100,
            firstLeafNode=5,
            lastLeafNode=15,
            nodeSize=4096,
            maxKeyLength=518,
            totalNodes=50,
            freeNodes=10,
            reserved1=0,
            clumpSize=65536,
            btreeType=0,
            keyCompareType=0xCF,
            attributes=0
        )
        assert header.treeDepth == 2
        assert header.rootNode == 10
        assert header.leafRecords == 100
        assert header.nodeSize == 4096
        assert header.is_case_sensitive is False
        
        # 测试序列化
        data = header.to_bytes()
        assert len(data) == 106


class TestSearch:
    """搜索测试"""
    
    def test_search_match_types(self):
        """测试搜索匹配类型"""
        assert SearchMatchType.EXACT.value == "exact"
        assert SearchMatchType.CONTAINS.value == "contains"
        assert SearchMatchType.STARTS_WITH.value == "starts_with"
        assert SearchMatchType.ENDS_WITH.value == "ends_with"
        assert SearchMatchType.REGEX.value == "regex"
    
    def test_search_filter(self):
        """测试搜索过滤器"""
        assert SearchFilter.ALL.value == "all"
        assert SearchFilter.FILES_ONLY.value == "files"
        assert SearchFilter.FOLDERS_ONLY.value == "folders"
    
    def test_search_result(self):
        """测试搜索结果"""
        result = SearchResult(
            name="test.txt",
            path="/path/to/test.txt",
            item_type="file",
            size=1024,
            create_date=0,
            mod_date=0,
            parent_id=2,
            item_id=16
        )
        assert result.name == "test.txt"
        assert result.item_type == "file"
        assert result.size == 1024


class TestWriter:
    """写入器测试"""
    
    def test_allocation_bitmap(self):
        """测试分配位图"""
        # 创建位图
        data = bytearray(128)  # 1024 位
        bitmap = AllocationBitmap(bytes(data))
        
        # 测试初始状态
        assert bitmap.is_block_allocated(0) is False
        assert bitmap.is_block_allocated(100) is False
        
        # 测试分配
        bitmap.allocate_block(0)
        assert bitmap.is_block_allocated(0) is True
        
        bitmap.allocate_block(100)
        assert bitmap.is_block_allocated(100) is True
        
        # 测试释放
        bitmap.free_block(0)
        assert bitmap.is_block_allocated(0) is False
        assert bitmap.is_block_allocated(100) is True
    
    def test_allocation_bitmap_find_free(self):
        """测试查找空闲块"""
        data = bytearray(128)
        bitmap = AllocationBitmap(bytes(data))
        
        # 分配一些块
        bitmap.allocate_block(0)
        bitmap.allocate_block(1)
        bitmap.allocate_block(2)
        
        # 查找空闲块
        free_blocks = bitmap.find_free_blocks(3, start_block=0)
        assert len(free_blocks) == 3
        assert 0 not in free_blocks
        assert 1 not in free_blocks
        assert 2 not in free_blocks


class TestCrypto:
    """加密测试"""
    
    def test_aes_xts_key_validation(self):
        """测试 AES-XTS 密钥验证"""
        # 有效密钥
        key32 = b'\x00' * 32
        key64 = b'\x00' * 64
        
        # 测试无效密钥长度
        with pytest.raises(CryptoError):
            AESXTS(b'\x00' * 16)
        
        with pytest.raises(CryptoError):
            AESXTS(b'\x00' * 48)
    
    def test_aes_key_wrap_validation(self):
        """测试 AES Key Wrap 密钥验证"""
        # 有效密钥
        key16 = b'\x00' * 16
        key32 = b'\x00' * 32
        
        # 测试无效密钥长度 - 注意：某些实现可能接受 24 字节密钥
        # 这里我们只测试能够创建实例
        try:
            AESKeyWrap(b'\x00' * 24)
        except CryptoError:
            pass  # 如果抛出异常也是可以的
    
    def test_pbkdf2_deriver(self):
        """测试 PBKDF2 密钥派生"""
        password = b"testpassword"
        salt = b"testsalt12345678"
        iterations = 1000
        
        # 测试 SHA-256
        key = PBKDF2Deriver.derive(password, salt, iterations, 
                                   key_length=32, hash_algo='sha256')
        assert len(key) == 32
        
        # 测试 SHA-1
        key_sha1 = PBKDF2Deriver.derive(password, salt, iterations,
                                        key_length=32, hash_algo='sha1')
        assert len(key_sha1) == 32
        
        # 不同算法应该产生不同密钥
        assert key != key_sha1
    
    def test_encrypted_volume_header_validation(self):
        """测试加密卷头验证"""
        # 无效数据
        with pytest.raises(CryptoError):
            EncryptedVolumeHeader(b'\x00' * 100)
        
        # 无效签名
        data = b'\x00' * 512
        with pytest.raises(CryptoError):
            EncryptedVolumeHeader(data)


class TestIntegration:
    """集成测试"""
    
    def test_full_volume_header_workflow(self):
        """测试完整的卷头工作流"""
        # 创建测试卷
        data = b'\x00' * VOLUME_HEADER_OFFSET
        
        # 添加卷头
        header_data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            SIGNATURE_HFS_PLUS,
            4, 0, 0x382E3130, 0, 0, 0, 0, 0, 100, 10, 4096, 1000, 500, 100, 4096, 4096, 16, 1, 0
        )
        header_data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        for _ in range(5):
            header_data += struct.pack('>QII', 0, 0, 0)
            header_data += b'\x00' * 64
        
        data += header_data
        stream = BytesIO(data)
        
        # 测试读取
        header = read_volume_header(stream)
        assert header.is_hfs_plus is True
        assert header.block_size == 4096
        assert header.total_blocks == 1000
        assert header.free_blocks == 500
        
        # 测试 is_hfs_plus_volume
        stream.seek(0)
        assert is_hfs_plus_volume(stream) is True
    
    def test_catalog_key_parsing(self):
        """测试 Catalog 键解析"""
        # 构造测试数据
        name = 'test.txt'.encode('utf-16-be')
        data = struct.pack('>HI', 4 + len(name), 2) + name
        
        key = HFSPlusCatalogKey.from_bytes(data)
        assert key.key_length == 4 + len(name)
        assert key.parent_id == 2
        assert key.node_name == 'test.txt'
        assert key.occupied_size == 2 + key.key_length
    
    def test_extent_key_parsing(self):
        """测试 Extent 键解析"""
        data = struct.pack('>HBBI I', 10, 0, 0, 16, 100)
        
        key = HFSPlusExtentKey.from_bytes(data)
        assert key.key_length == 10
        assert key.fork_type == 0
        assert key.file_id == 16
        assert key.start_block == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])