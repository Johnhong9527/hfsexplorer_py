"""
DMG 镜像测试

测试 DMG/UDIF 镜像解析功能。
"""

import struct
import plistlib
import tempfile
import os
import pytest

from src.core.dmg import (
    KolyBlock, KOLY_SIGNATURE, KOLY_SIZE,
    DMGBlockMap, DMGBlockEntry, DMGBlockType,
    DMGPartition, DMGImage, DMGError,
    open_dmg,
)


def create_test_dmg(path: str, num_sectors: int = 1000):
    """
    创建测试 DMG 文件
    
    Args:
        path: 输出路径
        num_sectors: 扇区数
    """
    # 创建简单的测试数据
    test_data = b'\xAB' * (num_sectors * 512)
    
    # 创建块映射表
    block_entries = []
    
    # 添加一个原始数据块
    entry_data = struct.pack('>I', DMGBlockType.RAW)  # entry_type
    entry_data += struct.pack('>I', 0)  # comment
    entry_data += struct.pack('>q', 0)  # sector_number
    entry_data += struct.pack('>q', num_sectors)  # sector_count
    entry_data += struct.pack('>q', 0)  # data_offset
    entry_data += struct.pack('>I', 0)  # buffers_needed
    entry_data += struct.pack('>I', 0)  # block_descriptor
    block_entries.append(entry_data)
    
    # 块映射表数据
    blkx_data = struct.pack('>I', 0x6D697368)  # signature 'mish'
    blkx_data += struct.pack('>I', 1)  # version
    blkx_data += struct.pack('>q', 0)  # sector_number
    blkx_data += struct.pack('>q', num_sectors)  # sector_count
    blkx_data += struct.pack('>q', 0)  # data_offset
    blkx_data += struct.pack('>I', 0)  # buffers_needed
    blkx_data += struct.pack('>I', len(block_entries))  # block_descriptors_count
    
    for entry in block_entries:
        blkx_data += entry
    
    # 创建 plist
    plist_data = {
        'resource-fork': {
            'blkx': [
                {
                    'Name': 'Test Partition',
                    'Data': blkx_data,
                }
            ]
        }
    }
    
    plist_bytes = plistlib.dumps(plist_data)
    
    # 写入数据
    with open(path, 'wb') as f:
        # 写入测试数据
        f.write(test_data)
        
        # 记录 plist 偏移
        plist_offset = f.tell()
        
        # 写入 plist
        f.write(plist_bytes)
        
        # 创建 koly 块
        koly = bytearray(KOLY_SIZE)
        
        # 签名
        koly[0:4] = KOLY_SIGNATURE
        
        # 版本
        struct.pack_into('>I', koly, 4, 4)
        
        # 头部大小
        struct.pack_into('>I', koly, 8, KOLY_SIZE)
        
        # 数据分支信息
        struct.pack_into('>q', koly, 16, 0)  # running_data_fork_offset
        struct.pack_into('>q', koly, 24, 0)  # data_fork_offset
        struct.pack_into('>q', koly, 32, len(test_data))  # data_fork_length
        
        # XML 数据偏移和长度
        struct.pack_into('>q', koly, 120, plist_offset)  # xmldata_offset
        struct.pack_into('>q', koly, 128, len(plist_bytes))  # xmldata_length
        
        # 写入 koly 块
        f.write(koly)


@pytest.fixture
def test_dmg_path():
    """创建测试 DMG 文件"""
    with tempfile.NamedTemporaryFile(suffix='.dmg', delete=False) as f:
        path = f.name
    
    create_test_dmg(path, num_sectors=100)
    
    yield path
    
    os.unlink(path)


class TestKolyBlock:
    """koly 块测试"""
    
    def test_create_koly(self):
        """测试创建 koly 块"""
        koly = KolyBlock(
            signature=KOLY_SIGNATURE,
            version=4,
            header_size=KOLY_SIZE,
            flags=0,
            running_data_fork_offset=0,
            data_fork_offset=0,
            data_fork_length=1024,
            rsrc_fork_offset=0,
            rsrc_fork_length=0,
            segment_number=1,
            segment_count=1,
            segment_id=b'\x00' * 16,
            data_checksum_type=0,
            data_checksum_size=0,
            data_checksum=b'\x00' * 32,
            xmldata_offset=1024,
            xmldata_length=256,
            checksum_type=0,
            checksum_size=0,
            checksum=b'\x00' * 32,
            plist_length=256
        )
        
        assert koly.is_valid
        assert koly.version == 4
        assert koly.data_fork_length == 1024
    
    def test_parse_koly(self):
        """测试解析 koly 块"""
        data = bytearray(KOLY_SIZE)
        data[0:4] = KOLY_SIGNATURE
        struct.pack_into('>I', data, 4, 4)  # version
        struct.pack_into('>I', data, 8, KOLY_SIZE)  # header_size
        struct.pack_into('>q', data, 32, 2048)  # data_fork_length
        
        koly = KolyBlock.from_bytes(bytes(data))
        
        assert koly.is_valid
        assert koly.version == 4
        assert koly.data_fork_length == 2048
    
    def test_invalid_signature(self):
        """测试无效签名"""
        data = b'\x00' * KOLY_SIZE
        
        with pytest.raises(DMGError):
            KolyBlock.from_bytes(data)


class TestDMGBlockEntry:
    """块条目测试"""
    
    def test_create_entry(self):
        """测试创建块条目"""
        data = struct.pack('>I', DMGBlockType.RAW)
        data += struct.pack('>I', 0)  # comment
        data += struct.pack('>q', 0)  # sector_number
        data += struct.pack('>q', 100)  # sector_count
        data += struct.pack('>q', 0)  # data_offset
        data += struct.pack('>I', 0)  # buffers_needed
        data += struct.pack('>I', 0)  # block_descriptor
        
        entry = DMGBlockEntry.from_bytes(data)
        
        assert entry.is_raw
        assert entry.sector_count == 100
        assert not entry.is_compressed
        assert not entry.is_zero
    
    def test_zero_entry(self):
        """测试零填充块"""
        data = struct.pack('>I', DMGBlockType.ZERO)
        data += struct.pack('>I', 0)
        data += struct.pack('>q', 0)
        data += struct.pack('>q', 50)
        data += struct.pack('>q', 0)
        data += struct.pack('>I', 0)
        data += struct.pack('>I', 0)
        
        entry = DMGBlockEntry.from_bytes(data)
        
        assert entry.is_zero
        assert not entry.is_raw
        assert entry.sector_count == 50
    
    def test_compressed_entry(self):
        """测试压缩块"""
        data = struct.pack('>I', DMGBlockType.ZLIB_COMPRESSED)
        data += struct.pack('>I', 0)
        data += struct.pack('>q', 0)
        data += struct.pack('>q', 200)
        data += struct.pack('>q', 1024)
        data += struct.pack('>I', 0)
        data += struct.pack('>I', 0)
        
        entry = DMGBlockEntry.from_bytes(data)
        
        assert entry.is_compressed
        assert not entry.is_raw
        assert entry.sector_count == 200


class TestDMGBlockMap:
    """块映射表测试"""
    
    def test_parse_block_map(self):
        """测试解析块映射表"""
        # 创建块映射表数据
        data = struct.pack('>I', 0x6D697368)  # signature
        data += struct.pack('>I', 1)  # version
        data += struct.pack('>q', 0)  # sector_number
        data += struct.pack('>q', 1000)  # sector_count
        data += struct.pack('>q', 0)  # data_offset
        data += struct.pack('>I', 0)  # buffers_needed
        data += struct.pack('>I', 1)  # block_descriptors_count
        
        # 添加一个块条目
        data += struct.pack('>I', DMGBlockType.RAW)
        data += struct.pack('>I', 0)
        data += struct.pack('>q', 0)
        data += struct.pack('>q', 1000)
        data += struct.pack('>q', 0)
        data += struct.pack('>I', 0)
        data += struct.pack('>I', 0)
        
        block_map = DMGBlockMap.from_bytes(data)
        
        assert block_map.sector_count == 1000
        assert len(block_map.block_entries) == 1
        assert block_map.block_entries[0].is_raw


class TestDMGImage:
    """DMG 镜像测试"""
    
    def test_open_dmg(self, test_dmg_path):
        """测试打开 DMG 文件"""
        with DMGImage(test_dmg_path) as dmg:
            assert dmg.koly is not None
            assert dmg.koly.is_valid
    
    def test_partitions(self, test_dmg_path):
        """测试获取分区"""
        with DMGImage(test_dmg_path) as dmg:
            assert dmg.partition_count == 1
            
            partition = dmg.partitions[0]
            assert partition.name == 'Test Partition'
            assert partition.sector_count == 100
    
    def test_get_partition_by_name(self, test_dmg_path):
        """测试根据名称获取分区"""
        with DMGImage(test_dmg_path) as dmg:
            partition = dmg.get_partition_by_name('Test Partition')
            assert partition is not None
            assert partition.name == 'Test Partition'
            
            # 不存在的分区
            partition = dmg.get_partition_by_name('Nonexistent')
            assert partition is None
    
    def test_file_size(self, test_dmg_path):
        """测试获取文件大小"""
        with DMGImage(test_dmg_path) as dmg:
            assert dmg.file_size > 0
    
    def test_str(self, test_dmg_path):
        """测试字符串表示"""
        with DMGImage(test_dmg_path) as dmg:
            s = str(dmg)
            assert 'Test Partition' in s
    
    def test_context_manager(self, test_dmg_path):
        """测试上下文管理器"""
        dmg = DMGImage(test_dmg_path)
        assert dmg._file is not None
        
        dmg.close()
        assert dmg._file is None
    
    def test_open_dmg_function(self, test_dmg_path):
        """测试 open_dmg 函数"""
        dmg = open_dmg(test_dmg_path)
        assert dmg is not None
        assert dmg.partition_count == 1
        dmg.close()


class TestDMGError:
    """错误处理测试"""
    
    def test_invalid_file(self):
        """测试无效文件"""
        with tempfile.NamedTemporaryFile(suffix='.dmg', delete=False) as f:
            f.write(b'\x00' * 1024)
            path = f.name
        
        try:
            with pytest.raises(DMGError):
                DMGImage(path)
        finally:
            os.unlink(path)
    
    def test_read_out_of_range(self, test_dmg_path):
        """测试读取超出范围"""
        with DMGImage(test_dmg_path) as dmg:
            partition = dmg.partitions[0]
            
            with pytest.raises(DMGError):
                # 超出分区范围
                dmg.read_sectors(0, partition.sector_count + 1)
    
    def test_invalid_partition_index(self, test_dmg_path):
        """测试无效分区索引"""
        with DMGImage(test_dmg_path) as dmg:
            with pytest.raises(DMGError):
                dmg.read_sectors(0, 10, partition_index=99)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
