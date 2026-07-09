"""
HFS+ 格式化器测试

测试创建新 HFS+ 文件系统的功能。
"""

import os
import struct
import tempfile
import pytest
import time

from src.core.hfs.formatter import (
    HFSPlusFormatter,
    FormatError,
    FormatOptions,
    format_volume,
)
from src.core.hfs.structures import HFSPlusVolumeHeader
from src.core.hfs.constants import (
    SIGNATURE_HFS_PLUS,
    HFS_EPOCH_OFFSET,
    DEFAULT_BLOCK_SIZE,
    CatalogNodeID,
    VolumeAttributes,
)


class TestFormatOptions:
    """格式化选项测试"""
    
    def test_default_options(self):
        """测试默认选项"""
        options = FormatOptions()
        assert options.volume_name == "Untitled"
        assert options.block_size == DEFAULT_BLOCK_SIZE
        assert options.max_catalog_nodes == 0
        assert options.journal_size == 0
        assert options.file_system_type == "HFS+"
        assert options.case_sensitive is False
    
    def test_custom_options(self):
        """测试自定义选项"""
        options = FormatOptions(
            volume_name="TestVolume",
            block_size=8192,
            max_catalog_nodes=100,
            journal_size=1024*1024,
            file_system_type="HFSX",
            case_sensitive=True
        )
        assert options.volume_name == "TestVolume"
        assert options.block_size == 8192
        assert options.max_catalog_nodes == 100
        assert options.journal_size == 1024*1024
        assert options.file_system_type == "HFSX"
        assert options.case_sensitive is True


class TestHFSPlusFormatter:
    """HFS+ 格式化器测试"""
    
    @pytest.fixture
    def formatter(self):
        """创建格式化器实例"""
        return HFSPlusFormatter()
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_format_file(self, formatter, temp_dir):
        """测试格式化文件"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024  # 10 MB
        
        # 创建文件
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        # 格式化
        header = formatter.format(path, "TestVolume", 4096)
        
        # 验证卷头
        assert header.signature == SIGNATURE_HFS_PLUS
        assert header.version == 4
        assert header.block_size == 4096
        assert header.total_blocks == size // 4096
        assert header.folder_count == 1  # 根目录
        assert header.file_count == 0
    
    def test_format_stream(self, formatter, temp_dir):
        """测试格式化流"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024  # 10 MB
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
            f.flush()
            
            # 格式化流
            header = formatter.format_stream(f, size, FormatOptions(
                volume_name="StreamVolume",
                block_size=4096
            ))
        
        # 验证卷头
        assert header.signature == SIGNATURE_HFS_PLUS
        assert header.total_blocks == size // 4096
    
    def test_format_with_different_block_sizes(self, formatter, temp_dir):
        """测试不同块大小的格式化"""
        block_sizes = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
        
        for block_size in block_sizes:
            path = os.path.join(temp_dir, f"test_{block_size}.hfs")
            size = block_size * 1000  # 1000 个块
            
            # 确保最小卷大小
            if size < 1024 * 1024:
                size = 1024 * 1024
                # 调整为块大小的整数倍
                size = (size // block_size) * block_size
            
            # 创建文件
            with open(path, "w+b") as f:
                f.seek(size - 1)
                f.write(b'\x00')
            
            # 格式化
            header = formatter.format(path, f"Vol{block_size}", block_size)
            
            # 验证
            assert header.block_size == block_size
            assert header.total_blocks == size // block_size
    
    def test_format_validation_too_small(self, formatter, temp_dir):
        """测试卷太小的验证"""
        path = os.path.join(temp_dir, "tiny.hfs")
        size = 100 * 1024  # 100 KB - 太小
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        with pytest.raises(FormatError, match="卷大小太小"):
            formatter.format(path, "Tiny", 4096)
    
    def test_format_validation_invalid_block_size(self, formatter, temp_dir):
        """测试无效块大小的验证"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        # 非 2 的幂
        with pytest.raises(FormatError, match="块大小必须是 2 的幂"):
            formatter.format(path, "Test", 3000)
        
        # 太小
        with pytest.raises(FormatError, match="块大小无效"):
            formatter.format(path, "Test", 100)
        
        # 太大
        with pytest.raises(FormatError, match="块大小无效"):
            formatter.format(path, "Test", 100000)
    
    def test_format_validation_long_name(self, formatter, temp_dir):
        """测试名称太长的验证"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        long_name = "A" * 256
        with pytest.raises(FormatError, match="卷名称太长"):
            formatter.format(path, long_name, 4096)
    
    def test_format_creates_valid_header(self, formatter, temp_dir):
        """测试格式化创建有效的卷头"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Test", 4096)
        
        # 验证签名
        assert header.is_valid
        assert header.is_hfs_plus
        
        # 验证日期
        current_time = int(time.time())
        assert abs(header.create_date - (current_time + HFS_EPOCH_OFFSET)) < 10
        
        # 验证属性
        assert header.is_cleanly_unmounted
        
        # 验证块信息
        assert header.block_size == 4096
        assert header.total_blocks > 0
        assert header.free_blocks > 0
        assert header.free_blocks < header.total_blocks
        
        # 验证 Catalog 信息
        assert header.next_catalog_id >= CatalogNodeID.FIRST_USER
        assert header.folder_count == 1
    
    def test_format_creates_backup_header(self, formatter, temp_dir):
        """测试格式化创建备份卷头"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Test", 4096)
        
        # 读取备份卷头
        with open(path, "rb") as f:
            f.seek(size - 512)
            backup_data = f.read(512)
        
        backup_header = HFSPlusVolumeHeader.from_bytes(backup_data)
        
        # 验证备份卷头
        assert backup_header.signature == header.signature
        assert backup_header.total_blocks == header.total_blocks
        assert backup_header.block_size == header.block_size
    
    def test_format_initializes_allocation_bitmap(self, formatter, temp_dir):
        """测试格式化初始化分配位图"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Test", 4096)
        
        # 验证空闲块数合理
        assert header.free_blocks > 0
        assert header.free_blocks < header.total_blocks
        
        # 系统区域应该被标记为已使用
        system_used = header.total_blocks - header.free_blocks
        assert system_used > 0
    
    def test_format_creates_catalog_btree(self, formatter, temp_dir):
        """测试格式化创建 Catalog B-tree"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Test", 4096)
        
        # 验证 Catalog 文件 fork 数据
        assert header.catalog_file.logical_size > 0
        assert header.catalog_file.total_blocks > 0
        assert len(header.catalog_file.extents) > 0
    
    def test_format_creates_extents_btree(self, formatter, temp_dir):
        """测试格式化创建 Extents Overflow B-tree"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Test", 4096)
        
        # 验证 Extents 文件 fork 数据
        assert header.extents_file.logical_size > 0
        assert header.extents_file.total_blocks > 0
        assert len(header.extents_file.extents) > 0


class TestFormatVolumeFunction:
    """format_volume 便捷函数测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_format_volume(self, temp_dir):
        """测试 format_volume 函数"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        # 创建文件
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        # 格式化
        header = format_volume(path, "TestVolume", 4096)
        
        # 验证
        assert header.is_valid
        assert header.block_size == 4096
    
    def test_format_volume_creates_readable_filesystem(self, temp_dir):
        """测试格式化创建可读的文件系统"""
        from src.core.hfs import HFSPlusVolume
        
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        # 创建文件
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        # 格式化
        format_volume(path, "TestVolume", 4096)
        
        # 尝试读取
        with HFSPlusVolume(path) as vol:
            info = vol.get_info()
            assert info is not None
            assert 'total_blocks' in info
            
            # 列出根目录
            contents = vol.list_folder(CatalogNodeID.ROOT_FOLDER)
            assert isinstance(contents, list)


class TestFormatEdgeCases:
    """边界情况测试"""
    
    @pytest.fixture
    def formatter(self):
        """创建格式化器实例"""
        return HFSPlusFormatter()
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_format_minimum_size(self, formatter, temp_dir):
        """测试最小卷大小"""
        path = os.path.join(temp_dir, "min.hfs")
        size = 1024 * 1024  # 1 MB - 最小
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        header = formatter.format(path, "Min", 512)
        assert header.total_blocks == size // 512
    
    def test_format_large_name(self, formatter, temp_dir):
        """测试较长的卷名"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        long_name = "A" * 255
        header = formatter.format(path, long_name, 4096)
        assert header.is_valid
    
    def test_format_unicode_name(self, formatter, temp_dir):
        """测试 Unicode 卷名"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        unicode_name = "测试卷名-TestVolume-日本語"
        header = formatter.format(path, unicode_name, 4096)
        assert header.is_valid
    
    def test_format_special_characters_name(self, formatter, temp_dir):
        """测试特殊字符卷名"""
        path = os.path.join(temp_dir, "test.hfs")
        size = 10 * 1024 * 1024
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        special_name = "Volume with spaces & special chars!@#$%"
        header = formatter.format(path, special_name, 4096)
        assert header.is_valid


class TestFormatPerformance:
    """性能测试"""
    
    @pytest.fixture
    def formatter(self):
        """创建格式化器实例"""
        return HFSPlusFormatter()
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.mark.slow
    def test_format_performance(self, formatter, temp_dir):
        """测试格式化性能"""
        path = os.path.join(temp_dir, "perf.hfs")
        size = 100 * 1024 * 1024  # 100 MB
        
        with open(path, "w+b") as f:
            f.seek(size - 1)
            f.write(b'\x00')
        
        start_time = time.time()
        header = formatter.format(path, "PerfTest", 4096)
        end_time = time.time()
        
        duration = end_time - start_time
        assert header.is_valid
        # 格式化应该在几秒内完成
        assert duration < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
