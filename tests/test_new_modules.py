"""
新模块测试

测试 Apple Single、Resource Fork、plist、DS_Store、Finder Info 等模块。
"""

import struct
import tempfile
import os
import pytest

from src.core.apple_single import (
    AppleSingleFile, AppleSingleEntry, AppleSingleEntryType,
    APPLE_SINGLE_MAGIC, APPLE_SINGLE_VERSION,
    open_apple_single, create_apple_single
)

from src.core.plist import (
    parse_plist, create_binary_plist, create_xml_plist,
    get_plist_value, get_plist_string, get_plist_int
)

from src.core.finder_info import (
    FinderInfo, ExtendedFinderInfo,
    get_file_type_description, get_file_creator_description
)


class TestAppleSingle:
    """Apple Single 测试"""
    
    def test_create_apple_single(self):
        """测试创建 Apple Single 文件"""
        data = create_apple_single(
            data_fork=b'Hello World',
            resource_fork=b'\x00' * 10,
            finder_info=b'\x00' * 16,
            real_name='test.txt'
        )
        
        assert len(data) > 0
        
        # 解析
        apple_file = AppleSingleFile.from_bytes(data)
        assert apple_file.is_apple_single
        assert apple_file.data_fork == b'Hello World'
        assert apple_file.real_name == 'test.txt'
    
    def test_parse_apple_single(self):
        """测试解析 Apple Single 文件"""
        # 构造简单的 Apple Single 数据
        data = bytearray()
        
        # 头部
        data += struct.pack('>I', APPLE_SINGLE_MAGIC)
        data += struct.pack('>I', APPLE_SINGLE_VERSION)
        data += b'\x00' * 16  # 填充
        data += struct.pack('>H', 2)  # 条目数量
        
        # 条目 1: 数据分支
        data += struct.pack('>I', AppleSingleEntryType.DATA_FORK)
        data += struct.pack('>I', 50)  # 偏移
        data += struct.pack('>I', 11)  # 长度
        
        # 条目 2: Finder Info
        data += struct.pack('>I', AppleSingleEntryType.FINDER_INFO)
        data += struct.pack('>I', 61)  # 偏移
        data += struct.pack('>I', 16)  # 长度
        
        # 填充到偏移 50
        data += b'\x00' * (50 - len(data))
        
        # 数据分支数据
        data += b'Hello World'
        
        # Finder Info 数据
        data += b'\x00' * 16
        
        apple_file = AppleSingleFile.from_bytes(bytes(data))
        
        assert apple_file.is_apple_single
        assert apple_file.data_fork == b'Hello World'
        assert len(apple_file.finder_info) == 16
    
    def test_get_entry(self):
        """测试获取条目"""
        data = create_apple_single(data_fork=b'test')
        apple_file = AppleSingleFile.from_bytes(data)
        
        entry = apple_file.get_entry(AppleSingleEntryType.DATA_FORK)
        assert entry is not None
        assert entry.data == b'test'
        
        # 不存在的类型
        entry = apple_file.get_entry(AppleSingleEntryType.RESOURCE_FORK)
        assert entry is None


class TestPlist:
    """Plist 测试"""
    
    def test_create_xml_plist(self):
        """测试创建 XML plist"""
        data = {'key': 'value', 'number': 42}
        xml_data = create_xml_plist(data)
        
        assert b'<?xml' in xml_data
        assert b'<plist' in xml_data
    
    def test_create_binary_plist(self):
        """测试创建二进制 plist"""
        data = {'key': 'value', 'number': 42}
        binary_data = create_binary_plist(data)
        
        assert binary_data[:6] == b'bplist'
    
    def test_parse_plist(self):
        """测试解析 plist"""
        data = {'key': 'value', 'number': 42}
        xml_data = create_xml_plist(data)
        
        parsed = parse_plist(xml_data)
        assert parsed['key'] == 'value'
        assert parsed['number'] == 42
    
    def test_get_plist_value(self):
        """测试获取 plist 值"""
        data = {
            'level1': {
                'level2': {
                    'value': 'test'
                }
            },
            'list': [1, 2, 3]
        }
        
        assert get_plist_value(data, 'level1', 'level2', 'value') == 'test'
        assert get_plist_value(data, 'list', '0') == 1
        assert get_plist_value(data, 'nonexistent') is None
    
    def test_get_plist_helpers(self):
        """测试 plist 辅助函数"""
        data = {
            'string': 'hello',
            'number': 42,
            'float': 3.14
        }
        
        assert get_plist_string(data, 'string') == 'hello'
        assert get_plist_int(data, 'number') == 42
        assert get_plist_int(data, 'string', default=0) == 0


class TestFinderInfo:
    """Finder Info 测试"""
    
    def test_create_finder_info(self):
        """测试创建 Finder Info"""
        info = FinderInfo(
            file_type='TEXT',
            file_creator='ttxt',
            finder_flags=0,
            location_x=100,
            location_y=200
        )
        
        data = info.to_bytes()
        assert len(data) == 16
        
        # 解析
        parsed = FinderInfo.from_bytes(data)
        assert parsed.file_type == 'TEXT'
        assert parsed.file_creator == 'ttxt'
        assert parsed.location_x == 100
        assert parsed.location_y == 200
    
    def test_finder_flags(self):
        """测试 Finder 标志"""
        info = FinderInfo(finder_flags=0x0400)
        assert info.has_custom_icon
        
        info = FinderInfo(finder_flags=0x4000)
        assert info.is_invisible
        
        info = FinderInfo(finder_flags=0x8000)
        assert info.is_alias
    
    def test_file_type_description(self):
        """测试文件类型描述"""
        assert get_file_type_description('TEXT') == '纯文本'
        assert get_file_type_description('JPEG') == 'JPEG 图片'
        assert get_file_type_description('????') == '????'
    
    def test_file_creator_description(self):
        """测试文件创建者描述"""
        assert get_file_creator_description('MACS') == 'Finder'
        assert get_file_creator_description('ttxt') == 'SimpleText'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
