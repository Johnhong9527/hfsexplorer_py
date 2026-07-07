"""
HFS+ 卷头解析器测试
"""

import pytest
import struct
from io import BytesIO

from src.core.hfs.constants import (
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
    VOLUME_HEADER_OFFSET,
    VOLUME_HEADER_SIZE,
    VolumeAttributes,
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


class TestExtentDescriptor:
    """ExtentDescriptor 测试"""
    
    def test_create_empty(self):
        """测试创建空 extent"""
        ext = ExtentDescriptor(start_block=0, block_count=0)
        assert ext.start_block == 0
        assert ext.block_count == 0
        assert ext.is_empty is True
        assert ext.end_block == 0
    
    def test_create_non_empty(self):
        """测试创建非空 extent"""
        ext = ExtentDescriptor(start_block=100, block_count=50)
        assert ext.start_block == 100
        assert ext.block_count == 50
        assert ext.is_empty is False
        assert ext.end_block == 150
    
    def test_to_bytes(self):
        """测试转换为字节"""
        ext = ExtentDescriptor(start_block=100, block_count=50)
        data = ext.to_bytes()
        assert len(data) == 8
        assert struct.unpack('>II', data) == (100, 50)
    
    def test_from_bytes(self):
        """测试从字节解析"""
        data = struct.pack('>II', 100, 50)
        ext = ExtentDescriptor.from_bytes(data)
        assert ext.start_block == 100
        assert ext.block_count == 50
    
    def test_from_bytes_with_offset(self):
        """测试从带偏移量的字节解析"""
        prefix = b'\x00' * 10
        data = prefix + struct.pack('>II', 100, 50)
        ext = ExtentDescriptor.from_bytes(data, offset=10)
        assert ext.start_block == 100
        assert ext.block_count == 50
    
    def test_from_bytes_insufficient_data(self):
        """测试数据不足时的错误处理"""
        with pytest.raises(ValueError):
            ExtentDescriptor.from_bytes(b'\x00' * 7)


class TestForkData:
    """ForkData 测试"""
    
    def test_create_empty(self):
        """测试创建空 fork"""
        fork = ForkData(logical_size=0, clump_size=0, total_blocks=0)
        assert fork.logical_size == 0
        assert fork.clump_size == 0
        assert fork.total_blocks == 0
        assert fork.extents == []
        assert fork.is_empty is True
    
    def test_create_with_extents(self):
        """测试创建带 extent 的 fork"""
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
    
    def test_to_bytes(self):
        """测试转换为字节"""
        extents = [
            ExtentDescriptor(start_block=100, block_count=50),
        ]
        fork = ForkData(
            logical_size=8192,
            clump_size=4096,
            total_blocks=80,
            extents=extents
        )
        data = fork.to_bytes()
        assert len(data) == 80  # 8 + 4 + 4 + 64
    
    def test_from_bytes(self):
        """测试从字节解析"""
        # 构造测试数据
        data = struct.pack('>QII', 8192, 4096, 80)
        # 添加 8 个 extent 描述符
        data += struct.pack('>II', 100, 50)  # 第一个 extent
        data += b'\x00' * (7 * 8)  # 其他 7 个空 extent
        
        fork = ForkData.from_bytes(data)
        assert fork.logical_size == 8192
        assert fork.clump_size == 4096
        assert fork.total_blocks == 80
        assert len(fork.extents) == 1
        assert fork.extents[0].start_block == 100
        assert fork.extents[0].block_count == 50


class TestFinderInfo:
    """FinderInfo 测试"""
    
    def test_create_default(self):
        """测试创建默认 FinderInfo"""
        info = FinderInfo()
        assert info.blessed_system_folder == 0
        assert info.volume_uuid == 0
    
    def test_to_bytes(self):
        """测试转换为字节"""
        info = FinderInfo(blessed_system_folder=5, volume_uuid=123456789)
        data = info.to_bytes()
        assert len(data) == 32
    
    def test_from_bytes(self):
        """测试从字节解析"""
        data = struct.pack('>IIIIIIQ', 5, 0, 0, 0, 0, 0, 123456789)
        info = FinderInfo.from_bytes(data)
        assert info.blessed_system_folder == 5
        assert info.volume_uuid == 123456789


class TestHFSPlusVolumeHeader:
    """HFSPlusVolumeHeader 测试"""
    
    def _create_test_header_data(self, signature=SIGNATURE_HFS_PLUS):
        """创建测试用的卷头数据"""
        # 基本字段 (20 个值)
        data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            signature,      # signature
            4,              # version
            0x00000000,     # attributes
            0x382E3130,     # lastMountedVersion (b'8.10' as uint32)
            0,              # journalInfoBlock
            1000000,        # createDate
            2000000,        # modifyDate
            3000000,        # backupDate
            4000000,        # checkedDate
            100,            # fileCount
            10,             # folderCount
            4096,           # blockSize
            1000,           # totalBlocks
            500,            # freeBlocks
            100,            # nextAllocation
            4096,           # rsrcClumpSize
            4096,           # dataClumpSize
            16,             # nextCatalogID
            1,              # writeCount
            0x0000000000000000,  # encodingsBitmap
        )
        
        # Finder Info (32 bytes)
        data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        
        # 5 个 ForkData
        for _ in range(5):
            data += struct.pack('>QII', 0, 0, 0)
            data += b'\x00' * 64
        
        return data
        
        # Finder Info (32 bytes)
        data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        
        # 5 个 ForkData (每个 80 bytes)
        for _ in range(5):
            # ForkData: logicalSize(8) + clumpSize(4) + totalBlocks(4) + extents(64)
            data += struct.pack('>QII', 0, 0, 0)
            data += b'\x00' * 64  # 8 个空 extent
        
        return data
    
    def test_from_bytes_hfs_plus(self):
        """测试解析 HFS+ 卷头"""
        data = self._create_test_header_data(SIGNATURE_HFS_PLUS)
        header = HFSPlusVolumeHeader.from_bytes(data)
        
        assert header.signature == SIGNATURE_HFS_PLUS
        assert header.is_hfs_plus is True
        assert header.is_hfsx is False
        assert header.is_valid is True
        assert header.version == 4
        assert header.block_size == 4096
        assert header.total_blocks == 1000
        assert header.free_blocks == 500
        assert header.file_count == 100
        assert header.folder_count == 10
    
    def test_from_bytes_hfsx(self):
        """测试解析 HFSX 卷头"""
        data = self._create_test_header_data(SIGNATURE_HFSX)
        header = HFSPlusVolumeHeader.from_bytes(data)
        
        assert header.signature == SIGNATURE_HFSX
        assert header.is_hfs_plus is False
        assert header.is_hfsx is True
        assert header.is_valid is True
    
    def test_invalid_signature(self):
        """测试无效签名"""
        data = self._create_test_header_data(0x1234)
        header = HFSPlusVolumeHeader.from_bytes(data)
        assert header.is_valid is False
    
    def test_volume_size(self):
        """测试卷大小计算"""
        data = self._create_test_header_data()
        header = HFSPlusVolumeHeader.from_bytes(data)
        
        assert header.volume_size == 4096 * 1000
        assert header.free_space == 4096 * 500
        assert header.used_space == 4096 * 500
    
    def test_attributes(self):
        """测试属性标志"""
        # 创建带属性的卷头
        data = self._create_test_header_data()
        # 修改属性字段 (offset 4, 4 bytes)
        data = data[:4] + struct.pack('>I', VolumeAttributes.VOLUME_JOURNALED) + data[8:]
        
        header = HFSPlusVolumeHeader.from_bytes(data)
        assert header.is_journaled is True
        assert header.is_locked is False
    
    def test_to_bytes(self):
        """测试转换为字节"""
        data = self._create_test_header_data()
        header = HFSPlusVolumeHeader.from_bytes(data)
        
        # 转换回字节
        result = header.to_bytes()
        assert len(result) == VOLUME_HEADER_SIZE
        
        # 重新解析
        header2 = HFSPlusVolumeHeader.from_bytes(result)
        assert header2.signature == header.signature
        assert header2.block_size == header.block_size
        assert header2.total_blocks == header.total_blocks


class TestHFSPlusVolumeHeaderReader:
    """HFSPlusVolumeHeaderReader 测试"""
    
    def _create_test_volume(self, signature=SIGNATURE_HFS_PLUS):
        """创建测试用的卷数据"""
        # 创建足够大的数据
        data = b'\x00' * VOLUME_HEADER_OFFSET
        
        # 添加卷头 (20 个值)
        header_data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            signature,      # signature
            4,              # version
            0x00000000,     # attributes
            0x382E3130,     # lastMountedVersion (b'8.10' as uint32)
            0,              # journalInfoBlock
            1000000,        # createDate
            2000000,        # modifyDate
            3000000,        # backupDate
            4000000,        # checkedDate
            100,            # fileCount
            10,             # folderCount
            4096,           # blockSize
            1000,           # totalBlocks
            500,            # freeBlocks
            100,            # nextAllocation
            4096,           # rsrcClumpSize
            4096,           # dataClumpSize
            16,             # nextCatalogID
            1,              # writeCount
            0x0000000000000000,  # encodingsBitmap
        )
        
        # Finder Info (32 bytes)
        header_data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        
        # 5 个 ForkData
        for _ in range(5):
            header_data += struct.pack('>QII', 0, 0, 0)
            header_data += b'\x00' * 64
        
        data += header_data
        return data
    
    def test_read_from_bytes_io(self):
        """测试从 BytesIO 读取"""
        data = self._create_test_volume()
        stream = BytesIO(data)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            header = reader.read_header()
            assert header.is_hfs_plus is True
            assert header.block_size == 4096
    
    def test_is_hfs_plus(self):
        """测试 is_hfs_plus 方法"""
        data = self._create_test_volume(SIGNATURE_HFS_PLUS)
        stream = BytesIO(data)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            assert reader.is_hfs_plus() is True
    
    def test_is_hfsx(self):
        """测试 is_hfsx 方法"""
        data = self._create_test_volume(SIGNATURE_HFSX)
        stream = BytesIO(data)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            assert reader.is_hfsx() is True
    
    def test_validate(self):
        """测试 validate 方法"""
        data = self._create_test_volume()
        stream = BytesIO(data)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            assert reader.validate() is True
    
    def test_invalid_signature(self):
        """测试无效签名"""
        data = self._create_test_volume(0x1234)
        stream = BytesIO(data)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            with pytest.raises(ValueError):
                reader.read_header()
    
    def test_insufficient_data(self):
        """测试数据不足"""
        stream = BytesIO(b'\x00' * 100)
        
        with HFSPlusVolumeHeaderReader(stream) as reader:
            with pytest.raises(IOError):
                reader.read_header()


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_read_volume_header(self):
        """测试 read_volume_header 函数"""
        # 创建测试数据
        data = b'\x00' * VOLUME_HEADER_OFFSET
        
        # 添加卷头 (20 个值)
        header_data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            SIGNATURE_HFS_PLUS,
            4, 0, 0x382E3130, 0, 0, 0, 0, 0, 100, 10, 4096, 1000, 500, 100, 4096, 4096, 16, 1, 0
        )
        # Finder Info (32 bytes)
        header_data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        for _ in range(5):
            header_data += struct.pack('>QII', 0, 0, 0)
            header_data += b'\x00' * 64
        
        data += header_data
        stream = BytesIO(data)
        
        header = read_volume_header(stream)
        assert header.is_hfs_plus is True
    
    def test_is_hfs_plus_volume(self):
        """测试 is_hfs_plus_volume 函数"""
        # 创建测试数据
        data = b'\x00' * VOLUME_HEADER_OFFSET
        
        # 添加卷头 (20 个值)
        header_data = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            SIGNATURE_HFS_PLUS,
            4, 0, 0x382E3130, 0, 0, 0, 0, 0, 100, 10, 4096, 1000, 500, 100, 4096, 4096, 16, 1, 0
        )
        # Finder Info (32 bytes)
        header_data += struct.pack('>IIIIIIQ', 0, 0, 0, 0, 0, 0, 0)
        for _ in range(5):
            header_data += struct.pack('>QII', 0, 0, 0)
            header_data += b'\x00' * 64
        
        data += header_data
        stream = BytesIO(data)
        
        assert is_hfs_plus_volume(stream) is True


if __name__ == '__main__':
    pytest.main([__file__])