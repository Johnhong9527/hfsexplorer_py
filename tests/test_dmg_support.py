"""
DMG/UDIF 镜像支持测试

测试 DMG 镜像的解析和读取功能。
"""

import struct
import unittest
import io
import tempfile
import os
from src.core.dmg import (
    DMGImage,
    KolyBlock,
    KOLY_SIGNATURE,
    KOLY_SIZE,
    DMGBlockType,
    DMGBlockEntry,
    DMGBlockMap,
    DMGPartition,
    DMGError,
)


class TestKolyBlock(unittest.TestCase):
    """测试 koly 块解析"""
    
    def _create_koly_data(self):
        """创建测试用的 koly 块数据"""
        data = bytearray(KOLY_SIZE)
        
        # 签名
        data[0:4] = KOLY_SIGNATURE
        
        # 版本
        struct.pack_into('>I', data, 4, 4)
        
        # 头部大小
        struct.pack_into('>I', data, 8, KOLY_SIZE)
        
        # 标志
        struct.pack_into('>I', data, 12, 0)
        
        # 数据分支偏移和长度
        struct.pack_into('>q', data, 24, 0)  # data_fork_offset
        struct.pack_into('>q', data, 32, 1024 * 1024)  # data_fork_length
        
        # 资源分支偏移和长度
        struct.pack_into('>q', data, 40, 0)  # rsrc_fork_offset
        struct.pack_into('>q', data, 48, 0)  # rsrc_fork_length
        
        # 段信息
        struct.pack_into('>I', data, 56, 1)  # segment_number
        struct.pack_into('>I', data, 60, 1)  # segment_count
        
        # XML 数据偏移和长度
        struct.pack_into('>q', data, 120, 512)  # xmldata_offset
        struct.pack_into('>q', data, 128, 1024)  # xmldata_length
        
        return bytes(data)
    
    def test_parse_koly_block(self):
        """测试解析 koly 块"""
        data = self._create_koly_data()
        koly = KolyBlock.from_bytes(data)
        
        self.assertTrue(koly.is_valid)
        self.assertEqual(koly.signature, KOLY_SIGNATURE)
        self.assertEqual(koly.version, 4)
        self.assertEqual(koly.header_size, KOLY_SIZE)
        self.assertEqual(koly.data_fork_length, 1024 * 1024)
        self.assertEqual(koly.segment_count, 1)
        self.assertEqual(koly.xmldata_offset, 512)
        self.assertEqual(koly.xmldata_length, 1024)
    
    def test_invalid_signature(self):
        """测试无效签名"""
        data = bytearray(KOLY_SIZE)
        data[0:4] = b'xxxx'
        
        with self.assertRaises(DMGError):
            KolyBlock.from_bytes(bytes(data))
    
    def test_data_too_short(self):
        """测试数据太短"""
        data = b'\x00' * 100
        
        with self.assertRaises(DMGError):
            KolyBlock.from_bytes(data)


class TestDMGBlockEntry(unittest.TestCase):
    """测试 DMG 块条目"""
    
    def test_parse_raw_entry(self):
        """测试解析原始数据块"""
        data = bytearray(40)
        
        # 块类型：RAW
        struct.pack_into('>I', data, 0, DMGBlockType.RAW)
        
        # 扇区号
        struct.pack_into('>q', data, 8, 0)
        
        # 扇区数
        struct.pack_into('>q', data, 16, 100)
        
        # 数据偏移
        struct.pack_into('>q', data, 24, 1024)
        
        entry = DMGBlockEntry.from_bytes(bytes(data))
        
        self.assertTrue(entry.is_raw)
        self.assertFalse(entry.is_compressed)
        self.assertFalse(entry.is_zero)
        self.assertEqual(entry.sector_number, 0)
        self.assertEqual(entry.sector_count, 100)
        self.assertEqual(entry.data_offset, 1024)
    
    def test_parse_zero_entry(self):
        """测试解析零填充块"""
        data = bytearray(40)
        
        # 块类型：ZERO
        struct.pack_into('>I', data, 0, DMGBlockType.ZERO)
        
        # 扇区号
        struct.pack_into('>q', data, 8, 100)
        
        # 扇区数
        struct.pack_into('>q', data, 16, 50)
        
        entry = DMGBlockEntry.from_bytes(bytes(data))
        
        self.assertFalse(entry.is_raw)
        self.assertFalse(entry.is_compressed)
        self.assertTrue(entry.is_zero)
        self.assertEqual(entry.sector_number, 100)
        self.assertEqual(entry.sector_count, 50)
    
    def test_parse_compressed_entry(self):
        """测试解析压缩块"""
        data = bytearray(40)
        
        # 块类型：ZLIB_COMPRESSED
        struct.pack_into('>I', data, 0, DMGBlockType.ZLIB_COMPRESSED)
        
        # 扇区号
        struct.pack_into('>q', data, 8, 200)
        
        # 扇区数
        struct.pack_into('>q', data, 16, 75)
        
        # 数据偏移
        struct.pack_into('>q', data, 24, 2048)
        
        entry = DMGBlockEntry.from_bytes(bytes(data))
        
        self.assertFalse(entry.is_raw)
        self.assertTrue(entry.is_compressed)
        self.assertFalse(entry.is_zero)
        self.assertEqual(entry.sector_number, 200)
        self.assertEqual(entry.sector_count, 75)
        self.assertEqual(entry.data_offset, 2048)


class TestDMGBlockMap(unittest.TestCase):
    """测试 DMG 块映射表"""
    
    def test_parse_block_map(self):
        """测试解析块映射表"""
        # 创建块映射表数据
        data = bytearray(40 + 40 * 3)  # 头部 + 3个条目
        
        # 头部
        struct.pack_into('>I', data, 0, 0x626C6B78)  # signature 'blkx'
        struct.pack_into('>I', data, 4, 1)  # version
        struct.pack_into('>q', data, 8, 0)  # sector_number
        struct.pack_into('>q', data, 16, 300)  # sector_count
        struct.pack_into('>q', data, 24, 0)  # data_offset
        struct.pack_into('>I', data, 32, 0)  # buffers_needed
        struct.pack_into('>I', data, 36, 3)  # block_descriptors_count
        
        # 条目 1：RAW
        offset = 40
        struct.pack_into('>I', data, offset, DMGBlockType.RAW)
        struct.pack_into('>q', data, offset + 8, 0)
        struct.pack_into('>q', data, offset + 16, 100)
        struct.pack_into('>q', data, offset + 24, 1024)
        
        # 条目 2：ZERO
        offset = 80
        struct.pack_into('>I', data, offset, DMGBlockType.ZERO)
        struct.pack_into('>q', data, offset + 8, 100)
        struct.pack_into('>q', data, offset + 16, 100)
        
        # 条目 3：ZLIB_COMPRESSED
        offset = 120
        struct.pack_into('>I', data, offset, DMGBlockType.ZLIB_COMPRESSED)
        struct.pack_into('>q', data, offset + 8, 200)
        struct.pack_into('>q', data, offset + 16, 100)
        struct.pack_into('>q', data, offset + 24, 2048)
        
        block_map = DMGBlockMap.from_bytes(bytes(data))
        
        self.assertEqual(block_map.signature, 0x626C6B78)
        self.assertEqual(block_map.version, 1)
        self.assertEqual(block_map.sector_count, 300)
        self.assertEqual(block_map.block_descriptors_count, 3)
        self.assertEqual(len(block_map.block_entries), 3)
        
        # 验证条目
        self.assertTrue(block_map.block_entries[0].is_raw)
        self.assertTrue(block_map.block_entries[1].is_zero)
        self.assertTrue(block_map.block_entries[2].is_compressed)


class TestDMGImage(unittest.TestCase):
    """测试 DMG 镜像读取器"""
    
    def _create_test_dmg(self, with_partitions=True):
        """创建测试用的 DMG 文件"""
        # 创建临时文件
        fd, path = tempfile.mkstemp(suffix='.dmg')
        
        try:
            with open(path, 'wb') as f:
                # 写入一些数据块
                data_block = b'\x01' * 1024
                f.write(data_block)
                
                # 计算 plist 数据位置
                plist_offset = f.tell()
                
                # 创建 plist 数据
                if with_partitions:
                    # 创建块映射表数据
                    block_map_data = bytearray(40 + 40)  # 头部 + 1个条目
                    
                    # 头部
                    struct.pack_into('>I', block_map_data, 0, 0x626C6B78)
                    struct.pack_into('>I', block_map_data, 4, 1)
                    struct.pack_into('>q', block_map_data, 8, 0)
                    struct.pack_into('>q', block_map_data, 16, 2)  # 2个扇区
                    struct.pack_into('>q', block_map_data, 24, 0)
                    struct.pack_into('>I', block_map_data, 32, 0)
                    struct.pack_into('>I', block_map_data, 36, 1)
                    
                    # RAW 条目
                    offset = 40
                    struct.pack_into('>I', block_map_data, offset, DMGBlockType.RAW)
                    struct.pack_into('>q', block_map_data, offset + 8, 0)
                    struct.pack_into('>q', block_map_data, offset + 16, 2)
                    struct.pack_into('>q', block_map_data, offset + 24, 0)
                    
                    plist_data = {
                        'resource-fork': {
                            'blkx': [
                                {
                                    'Name': 'Test Partition',
                                    'Data': bytes(block_map_data),
                                }
                            ]
                        }
                    }
                else:
                    plist_data = {}
                
                # 写入 plist
                import plistlib
                plist_bytes = plistlib.dumps(plist_data)
                f.write(plist_bytes)
                
                # 记录 plist 位置和大小
                plist_length = len(plist_bytes)
                
                # 写入 koly 块（文件末尾）
                koly_data = bytearray(KOLY_SIZE)
                koly_data[0:4] = KOLY_SIGNATURE
                struct.pack_into('>I', koly_data, 4, 4)
                struct.pack_into('>I', koly_data, 8, KOLY_SIZE)
                struct.pack_into('>I', koly_data, 12, 0)
                struct.pack_into('>q', koly_data, 24, 0)
                struct.pack_into('>q', koly_data, 32, 1024)
                struct.pack_into('>q', koly_data, 40, 0)
                struct.pack_into('>q', koly_data, 48, 0)
                struct.pack_into('>I', koly_data, 56, 1)
                struct.pack_into('>I', koly_data, 60, 1)
                struct.pack_into('>q', koly_data, 120, plist_offset)
                struct.pack_into('>q', koly_data, 128, plist_length)
                
                f.write(bytes(koly_data))
            
            return path
        except Exception:
            os.unlink(path)
            raise
    
    def test_open_dmg(self):
        """测试打开 DMG 文件"""
        path = self._create_test_dmg()
        
        try:
            with DMGImage(path) as dmg:
                self.assertIsNotNone(dmg.koly)
                self.assertTrue(dmg.koly.is_valid)
                self.assertEqual(dmg.partition_count, 1)
                
                partition = dmg.partitions[0]
                self.assertEqual(partition.name, 'Test Partition')
                self.assertEqual(partition.sector_count, 2)
        finally:
            os.unlink(path)
    
    def test_open_dmg_no_partitions(self):
        """测试打开没有分区的 DMG 文件"""
        path = self._create_test_dmg(with_partitions=False)
        
        try:
            with DMGImage(path) as dmg:
                self.assertIsNotNone(dmg.koly)
                self.assertTrue(dmg.koly.is_valid)
                self.assertEqual(dmg.partition_count, 0)
        finally:
            os.unlink(path)
    
    def test_get_partition_by_name(self):
        """测试根据名称获取分区"""
        path = self._create_test_dmg()
        
        try:
            with DMGImage(path) as dmg:
                partition = dmg.get_partition_by_name('Test Partition')
                self.assertIsNotNone(partition)
                self.assertEqual(partition.name, 'Test Partition')
                
                # 测试不存在的分区
                partition = dmg.get_partition_by_name('Nonexistent')
                self.assertIsNone(partition)
        finally:
            os.unlink(path)
    
    def test_read_sectors(self):
        """测试读取扇区"""
        path = self._create_test_dmg()
        
        try:
            with DMGImage(path) as dmg:
                # 读取前 2 个扇区
                data = dmg.read_sectors(0, 2)
                self.assertEqual(len(data), 1024)  # 2 扇区 * 512 字节
        finally:
            os.unlink(path)
    
    def test_invalid_dmg(self):
        """测试无效的 DMG 文件"""
        # 创建一个非 DMG 文件
        fd, path = tempfile.mkstemp(suffix='.dmg')
        
        try:
            with open(path, 'wb') as f:
                f.write(b'\x00' * 1024)
            
            with self.assertRaises(DMGError):
                DMGImage(path)
        finally:
            os.unlink(path)


class TestDMGBlockType(unittest.TestCase):
    """测试 DMG 块类型"""
    
    def test_block_type_values(self):
        """测试块类型值"""
        self.assertEqual(DMGBlockType.ZERO, 0x00000000)
        self.assertEqual(DMGBlockType.RAW, 0x00000001)
        self.assertEqual(DMGBlockType.IGNORE, 0x00000002)
        self.assertEqual(DMGBlockType.ADC_COMPRESSED, 0x80000004)
        self.assertEqual(DMGBlockType.ZLIB_COMPRESSED, 0x80000005)
        self.assertEqual(DMGBlockType.BZIP2_COMPRESSED, 0x80000006)
        self.assertEqual(DMGBlockType.LZFSE_COMPRESSED, 0x80000007)
        self.assertEqual(DMGBlockType.COMMENT, 0x7FFFFFFE)
        self.assertEqual(DMGBlockType.TERMINATOR, 0xFFFFFFFF)


if __name__ == '__main__':
    unittest.main()
