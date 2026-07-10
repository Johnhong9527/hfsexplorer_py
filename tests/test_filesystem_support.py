#!/usr/bin/env python3
"""
文件系统支持测试

测试 APFS、HFS Classic 和 CoreStorage 的支持。
"""

import pytest
import sys
import os
import tempfile
import struct

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestFileSystemDetection:
    """测试文件系统检测"""
    
    def test_detect_hfs_plus(self):
        """测试检测 HFS+"""
        from src.core.unified_fs import FileSystemDetector, FileSystemType
        
        # 创建一个 HFS+ 卷头
        data = bytearray(4096)
        struct.pack_into('>H', data, 1024, 0x482B)  # HFS+ 签名
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            f.flush()
            
            fs_type = FileSystemDetector.detect(f.name)
            assert fs_type == FileSystemType.HFS_PLUS
            
            os.unlink(f.name)
    
    def test_detect_hfsx(self):
        """测试检测 HFSX"""
        from src.core.unified_fs import FileSystemDetector, FileSystemType
        
        # 创建一个 HFSX 卷头
        data = bytearray(4096)
        struct.pack_into('>H', data, 1024, 0x4858)  # HFSX 签名
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            f.flush()
            
            fs_type = FileSystemDetector.detect(f.name)
            assert fs_type == FileSystemType.HFSX
            
            os.unlink(f.name)
    
    def test_detect_hfs(self):
        """测试检测 HFS Classic"""
        from src.core.unified_fs import FileSystemDetector, FileSystemType
        
        # 创建一个 HFS 卷头
        data = bytearray(4096)
        struct.pack_into('>H', data, 1024, 0x4244)  # HFS 签名
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            f.flush()
            
            fs_type = FileSystemDetector.detect(f.name)
            assert fs_type == FileSystemType.HFS
            
            os.unlink(f.name)
    
    def test_detect_apfs(self):
        """测试检测 APFS"""
        from src.core.unified_fs import FileSystemDetector, FileSystemType
        
        # 创建一个 APFS 容器
        data = bytearray(4096)
        data[32:36] = b'NXSB'  # APFS 魔数
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            f.flush()
            
            fs_type = FileSystemDetector.detect(f.name)
            assert fs_type == FileSystemType.APFS
            
            os.unlink(f.name)
    
    def test_detect_unknown(self):
        """测试检测未知文件系统"""
        from src.core.unified_fs import FileSystemDetector, FileSystemType
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 4096)
            f.flush()
            
            fs_type = FileSystemDetector.detect(f.name)
            assert fs_type == FileSystemType.UNKNOWN
            
            os.unlink(f.name)


class TestUnifiedVolume:
    """测试统一卷接口"""
    
    def test_open_hfs_plus(self):
        """测试打开 HFS+ 卷"""
        from src.core.unified_fs import UnifiedVolume, FileSystemType
        
        # 使用现有的测试文件
        test_path = tempfile.mktemp(suffix='.img')
        
        try:
            # 创建 HFS+ 卷
            from src.core.hfs.formatter import HFSPlusFormatter
            with open(test_path, 'wb') as f:
                f.seek(10 * 1024 * 1024 - 1)
                f.write(b'\x00')
            
            formatter = HFSPlusFormatter()
            formatter.format(test_path, 'TestVolume', 4096)
            
            # 测试统一卷接口
            with UnifiedVolume(test_path) as vol:
                assert vol.fs_type == FileSystemType.HFS_PLUS
                
                info = vol.get_info()
                assert 'fs_type' in info
                assert info['fs_type'] == 'hfs+'
                
                # 列出根目录
                contents = vol.list_folder(2)
                assert isinstance(contents, list)
                
        finally:
            if os.path.exists(test_path):
                os.unlink(test_path)


class TestAPFSSupport:
    """测试 APFS 支持"""
    
    def test_apfs_structures(self):
        """测试 APFS 数据结构"""
        from src.core.apfs.full_support import NXSuperblock, APFSSuperblock
        
        # 测试 NXSuperblock
        data = bytearray(4096)
        data[32:36] = b'NXSB'
        struct.pack_into('<I', data, 36, 4096)  # block_size
        
        nx = NXSuperblock.from_bytes(bytes(data))
        assert nx.magic == b'NXSB'
        assert nx.block_size == 4096
    
    def test_apfs_container_reader(self):
        """测试 APFS 容器读取器"""
        from src.core.apfs.full_support import APFSContainerReader
        
        # 这个测试需要一个真实的 APFS 镜像
        # 暂时跳过
        pass


class TestHFSClassicSupport:
    """测试 HFS Classic 支持"""
    
    def test_hfs_header_parsing(self):
        """测试 HFS 头部解析"""
        from src.core.hfs_classic_full import HFSVolumeHeader
        
        # 创建一个简单的 HFS 头部
        data = bytearray(512)
        struct.pack_into('>H', data, 0, 0x4244)  # HFS 签名
        struct.pack_into('>I', data, 28, 4096)  # block_size
        struct.pack_into('>I', data, 32, 2560)  # total_blocks
        
        header = HFSVolumeHeader.from_bytes(bytes(data))
        assert header.signature == 0x4244
        assert header.block_size == 4096
        assert header.total_blocks == 2560
    
    def test_hfs_volume_detection(self):
        """测试 HFS 卷检测"""
        from src.core.hfs_classic_full import is_hfs_volume
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 创建 HFS 卷头
            data = bytearray(4096)
            struct.pack_into('>H', data, 1024, 0x4244)  # HFS 签名
            f.write(data)
            f.flush()
            
            assert is_hfs_volume(f.name) == True
            
            os.unlink(f.name)


class TestCoreStorageSupport:
    """测试 CoreStorage 支持"""
    
    def test_corestorage_header(self):
        """测试 CoreStorage 头部解析"""
        from src.core.corestorage_full import CoreStorageHeader
        
        # 创建一个简单的 CoreStorage 头部
        data = bytearray(512)
        data[0:4] = b'CS\x00\x00'  # 签名
        struct.pack_into('>I', data, 4, 1)  # version
        struct.pack_into('>I', data, 8, 1)  # flags
        struct.pack_into('>I', data, 12, 1)  # volume_type
        
        header = CoreStorageHeader.from_bytes(bytes(data))
        assert header.signature == b'CS\x00\x00'
        assert header.version == 1
        assert header.is_valid == True
    
    def test_corestorage_detection(self):
        """测试 CoreStorage 检测"""
        from src.core.corestorage_full import is_corestorage
        import io
        
        # 创建 CoreStorage 数据
        data = bytearray(512)
        data[0:4] = b'CS\x00\x00'
        
        stream = io.BytesIO(data)
        assert is_corestorage(stream, 0) == True


class TestSupportedFilesystems:
    """测试支持的文件系统列表"""
    
    def test_get_supported_filesystems(self):
        """测试获取支持的文件系统列表"""
        from src.core.unified_fs import get_supported_filesystems
        
        fs_list = get_supported_filesystems()
        assert 'hfs' in fs_list
        assert 'hfs+' in fs_list
        assert 'hfsx' in fs_list
        assert 'apfs' in fs_list
        assert 'corestorage' in fs_list
    
    def test_is_supported(self):
        """测试检查文件是否支持"""
        from src.core.unified_fs import is_supported
        
        # 创建一个 HFS+ 卷
        with tempfile.NamedTemporaryFile(delete=False) as f:
            data = bytearray(4096)
            struct.pack_into('>H', data, 1024, 0x482B)
            f.write(data)
            f.flush()
            
            assert is_supported(f.name) == True
            
            os.unlink(f.name)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
