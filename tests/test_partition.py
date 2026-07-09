"""
分区表解析模块测试
"""

import pytest
import struct
from io import BytesIO

from src.core.partition import (
    PartitionType,
    PartitionError,
    PartitionEntry,
    parse_apm,
    parse_gpt,
    parse_mbr,
    parse_partitions,
    detect_partition_type,
    find_hfs_partitions,
)


class TestPartitionEntry:
    """PartitionEntry 测试"""
    
    def test_create_entry(self):
        """测试创建分区条目"""
        entry = PartitionEntry(
            name="Test",
            type_name="Apple_HFS",
            start_lba=40,
            size_sectors=1000
        )
        assert entry.name == "Test"
        assert entry.type_name == "Apple_HFS"
        assert entry.start_lba == 40
        assert entry.size_sectors == 1000
        assert entry.start_offset == 40 * 512
        assert entry.size_bytes == 1000 * 512
        assert entry.is_hfs is False
    
    def test_hfs_entry(self):
        """测试 HFS+ 分区条目"""
        entry = PartitionEntry(
            name="Macintosh HD",
            type_name="Apple_HFS",
            start_lba=40,
            size_sectors=1000,
            is_hfs=True
        )
        assert entry.is_hfs is True


class TestAPMParser:
    """APM 解析器测试"""
    
    def test_parse_empty_apm(self):
        """测试解析空 APM"""
        # 创建一个包含驱动器描述符的空 APM
        data = bytearray(512 * 3)
        
        # 驱动器描述符 (LBA 0)
        data[0:2] = struct.pack('>H', 0x4552)  # 签名 "ER"
        data[4:8] = struct.pack('>I', 1)  # 分区表大小
        data[8:12] = struct.pack('>I', 512)  # 块大小
        
        stream = BytesIO(data)
        partitions = parse_apm(stream)
        
        # 应该没有分区（只有驱动器描述符）
        assert len(partitions) == 0
    
    def test_parse_single_partition(self):
        """测试解析单个分区"""
        data = bytearray(512 * 3)
        
        # 驱动器描述符 (LBA 0)
        data[0:2] = struct.pack('>H', 0x4552)  # 签名 "ER"
        data[4:8] = struct.pack('>I', 2)  # 分区表大小（包含驱动器描述符）
        data[8:12] = struct.pack('>I', 512)  # 块大小
        
        # 分区条目 (LBA 1)
        offset = 512
        data[offset:offset+2] = struct.pack('>H', 0x504D)  # 签名 "PM"
        data[offset+8:offset+12] = struct.pack('>I', 40)  # 起始块
        data[offset+12:offset+16] = struct.pack('>I', 1000)  # 块数
        
        # 分区名称 (16-48)
        name = b'Test\x00' + b'\x00' * 27
        data[offset+16:offset+48] = name
        
        # 分区类型 (48-80)
        type_name = b'Apple_HFS\x00' + b'\x00' * 22
        data[offset+48:offset+80] = type_name
        
        stream = BytesIO(data)
        partitions = parse_apm(stream)
        
        assert len(partitions) == 1
        assert partitions[0].name == "Test"
        assert partitions[0].type_name == "Apple_HFS"
        assert partitions[0].start_lba == 40
        assert partitions[0].size_sectors == 1000
        assert partitions[0].is_hfs is True


class TestGPTParser:
    """GPT 解析器测试"""
    
    def test_parse_empty_gpt(self):
        """测试解析空 GPT"""
        data = bytearray(512 * 3)
        
        # GPT 头 (LBA 1)
        offset = 512
        data[offset:offset+8] = b'EFI PART'  # 签名
        data[offset+8:offset+12] = struct.pack('<I', 0x00010000)  # 版本
        data[offset+12:offset+16] = struct.pack('<I', 92)  # 头大小
        data[offset+72:offset+80] = struct.pack('<Q', 2)  # 分区条目 LBA
        data[offset+80:offset+84] = struct.pack('<I', 0)  # 分区数量
        data[offset+84:offset+88] = struct.pack('<I', 128)  # 条目大小
        
        stream = BytesIO(data)
        partitions = parse_gpt(stream)
        
        assert len(partitions) == 0
    
    def test_parse_single_partition(self):
        """测试解析单个分区"""
        data = bytearray(512 * 4)
        
        # GPT 头 (LBA 1)
        offset = 512
        data[offset:offset+8] = b'EFI PART'  # 签名
        data[offset+8:offset+12] = struct.pack('<I', 0x00010000)  # 版本
        data[offset+12:offset+16] = struct.pack('<I', 92)  # 头大小
        data[offset+72:offset+80] = struct.pack('<Q', 2)  # 分区条目 LBA
        data[offset+80:offset+84] = struct.pack('<I', 1)  # 分区数量
        data[offset+84:offset+88] = struct.pack('<I', 128)  # 条目大小
        
        # 分区条目 (LBA 2)
        entry_offset = 1024
        # HFS+ 类型 GUID
        hfs_guid = bytes([
            0x00, 0x53, 0x46, 0x48, 0x00, 0x00, 0xAA, 0x11,
            0xAA, 0x11, 0x00, 0x30, 0x65, 0x43, 0xEC, 0xAC
        ])
        data[entry_offset:entry_offset+16] = hfs_guid
        
        # 分区 GUID (任意)
        data[entry_offset+16:entry_offset+32] = b'\x01' * 16
        
        # 起始 LBA
        data[entry_offset+32:entry_offset+40] = struct.pack('<Q', 40)
        
        # 结束 LBA
        data[entry_offset+40:entry_offset+48] = struct.pack('<Q', 1039)
        
        # 分区名称 "Test" (UTF-16LE)
        name_bytes = "Test".encode('utf-16-le') + b'\x00\x00'
        data[entry_offset+56:entry_offset+56+len(name_bytes)] = name_bytes
        
        stream = BytesIO(data)
        partitions = parse_gpt(stream)
        
        assert len(partitions) == 1
        assert partitions[0].name == "Test"
        assert partitions[0].type_name == "Apple HFS+"
        assert partitions[0].start_lba == 40
        assert partitions[0].size_sectors == 1000
        assert partitions[0].is_hfs is True


class TestMBRParser:
    """MBR 解析器测试"""
    
    def test_parse_empty_mbr(self):
        """测试解析空 MBR"""
        data = bytearray(512)
        
        # MBR 签名
        data[510:512] = b'\x55\xAA'
        
        stream = BytesIO(data)
        partitions = parse_mbr(stream)
        
        assert len(partitions) == 0
    
    def test_parse_single_partition(self):
        """测试解析单个分区"""
        data = bytearray(512)
        
        # MBR 签名
        data[510:512] = b'\x55\xAA'
        
        # 第一个分区条目
        entry_offset = 446
        data[entry_offset] = 0x80  # 活动标志
        data[entry_offset+4] = 0xAF  # HFS+ 类型
        data[entry_offset+8:entry_offset+12] = struct.pack('<I', 40)  # 起始 LBA
        data[entry_offset+12:entry_offset+16] = struct.pack('<I', 1000)  # 大小
        
        stream = BytesIO(data)
        partitions = parse_mbr(stream)
        
        assert len(partitions) == 1
        assert partitions[0].name == "Partition 1"
        assert partitions[0].type_name == "HFS/HFS+"
        assert partitions[0].start_lba == 40
        assert partitions[0].size_sectors == 1000
        assert partitions[0].is_hfs is True


class TestPartitionDetection:
    """分区表检测测试"""
    
    def test_detect_gpt(self):
        """测试检测 GPT"""
        data = bytearray(512 * 2)
        data[512:520] = b'EFI PART'  # GPT 签名在 LBA 1
        
        stream = BytesIO(data)
        assert detect_partition_type(stream) == PartitionType.GPT
    
    def test_detect_apm(self):
        """测试检测 APM"""
        data = bytearray(512 * 2)
        data[0:2] = struct.pack('>H', 0x4552)  # APM 驱动器描述符签名在 LBA 0
        
        stream = BytesIO(data)
        assert detect_partition_type(stream) == PartitionType.APM
    
    def test_detect_mbr(self):
        """测试检测 MBR"""
        data = bytearray(512)
        data[510:512] = b'\x55\xAA'  # MBR 签名
        
        stream = BytesIO(data)
        assert detect_partition_type(stream) == PartitionType.MBR
    
    def test_detect_unknown(self):
        """测试检测未知类型"""
        data = bytearray(512)
        
        stream = BytesIO(data)
        assert detect_partition_type(stream) == PartitionType.UNKNOWN


class TestCatalogThread:
    """Catalog 线程记录测试"""
    
    def test_thread_record_parsing(self):
        """测试线程记录解析"""
        from src.core.hfs.btree import HFSPlusCatalogThread, CatalogRecordType
        
        # 构造线程记录数据
        # recordType (2) + reserved (2) + parentID (4) + nodeName
        data = struct.pack('>HHI', 0x0003, 0, 100)  # 文件夹线程, parentID=100
        
        # nodeName: HFSUniStr255 (length + chars)
        name = "TestFolder"
        name_bytes = name.encode('utf-16-be')
        data += struct.pack('>H', len(name)) + name_bytes
        
        thread = HFSPlusCatalogThread.from_bytes(data)
        
        assert thread.record_type == CatalogRecordType.FOLDER_THREAD
        assert thread.parent_id == 100
        assert thread.node_name == "TestFolder"
        assert thread.is_folder_thread is True
        assert thread.is_file_thread is False
    
    def test_file_thread_record(self):
        """测试文件线程记录"""
        from src.core.hfs.btree import HFSPlusCatalogThread, CatalogRecordType
        
        # 构造文件线程记录
        data = struct.pack('>HHI', 0x0004, 0, 200)  # 文件线程, parentID=200
        
        name = "TestFile.txt"
        name_bytes = name.encode('utf-16-be')
        data += struct.pack('>H', len(name)) + name_bytes
        
        thread = HFSPlusCatalogThread.from_bytes(data)
        
        assert thread.record_type == CatalogRecordType.FILE_THREAD
        assert thread.parent_id == 200
        assert thread.node_name == "TestFile.txt"
        assert thread.is_folder_thread is False
        assert thread.is_file_thread is True
