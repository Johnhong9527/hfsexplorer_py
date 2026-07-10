"""
unhfs 命令行工具测试

测试 unhfs 命令行工具的功能。
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli.unhfs import (
    list_files,
    extract_files,
    _resolve_path,
    _format_size,
    UnhfsError,
)


class TestFormatSize(unittest.TestCase):
    """测试文件大小格式化"""
    
    def test_bytes(self):
        """测试字节格式化"""
        self.assertEqual(_format_size(100), "100 B")
        self.assertEqual(_format_size(0), "0 B")
        self.assertEqual(_format_size(1023), "1023 B")
    
    def test_kilobytes(self):
        """测试千字节格式化"""
        self.assertEqual(_format_size(1024), "1.0 KB")
        self.assertEqual(_format_size(1536), "1.5 KB")
        self.assertEqual(_format_size(1024 * 1024 - 1), "1024.0 KB")
    
    def test_megabytes(self):
        """测试兆字节格式化"""
        self.assertEqual(_format_size(1024 * 1024), "1.0 MB")
        self.assertEqual(_format_size(1024 * 1024 * 1.5), "1.5 MB")
    
    def test_gigabytes(self):
        """测试千兆字节格式化"""
        self.assertEqual(_format_size(1024 * 1024 * 1024), "1.00 GB")
        self.assertEqual(_format_size(1024 * 1024 * 1024 * 2.5), "2.50 GB")


class TestResolvePath(unittest.TestCase):
    """测试路径解析"""
    
    def _create_mock_volume(self):
        """创建模拟卷"""
        volume = MagicMock()
        
        # 模拟目录结构
        # 根目录 (CNID 2)
        volume.list_folder.return_value = [
            {'name': 'Documents', 'type': 'folder', 'id': 100},
            {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
        ]
        
        return volume
    
    def test_resolve_root(self):
        """测试解析根目录"""
        volume = self._create_mock_volume()
        
        # 根目录直接返回 2
        result = _resolve_path(volume, '/')
        self.assertEqual(result, 2)
    
    def test_resolve_single_path(self):
        """测试解析单层路径"""
        volume = self._create_mock_volume()
        
        # 模拟 Documents 目录
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                    {'name': 'file.txt', 'type': 'file', 'id': 200},
                ]
            elif cnid == 100:
                return [
                    {'name': 'report.pdf', 'type': 'file', 'id': 300},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        result = _resolve_path(volume, '/Documents')
        self.assertEqual(result, 100)
    
    def test_resolve_nested_path(self):
        """测试解析嵌套路径"""
        volume = MagicMock()
        
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                ]
            elif cnid == 100:
                return [
                    {'name': 'Work', 'type': 'folder', 'id': 200},
                ]
            elif cnid == 200:
                return [
                    {'name': 'report.pdf', 'type': 'file', 'id': 300},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        result = _resolve_path(volume, '/Documents/Work')
        self.assertEqual(result, 200)
    
    def test_resolve_nonexistent_path(self):
        """测试解析不存在的路径"""
        volume = MagicMock()
        
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        result = _resolve_path(volume, '/Nonexistent')
        self.assertIsNone(result)


class TestListFiles(unittest.TestCase):
    """测试文件列表"""
    
    def test_list_root(self):
        """测试列出根目录"""
        volume = MagicMock()
        
        volume.list_folder.return_value = [
            {'name': 'Documents', 'type': 'folder', 'id': 100},
            {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
        ]
        
        files = list_files(volume, '/', recursive=False)
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['name'], 'Documents')
        self.assertEqual(files[0]['type'], 'folder')
        self.assertEqual(files[1]['name'], 'file.txt')
        self.assertEqual(files[1]['type'], 'file')
        self.assertEqual(files[1]['size'], 1024)
    
    def test_list_recursive(self):
        """测试递归列出"""
        volume = MagicMock()
        
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                    {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
                ]
            elif cnid == 100:
                return [
                    {'name': 'report.pdf', 'type': 'file', 'id': 300, 'size': 2048},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        files = list_files(volume, '/', recursive=True)
        
        self.assertEqual(len(files), 3)
        # 递归时，子目录内容会插入到父目录项之后
        self.assertEqual(files[0]['name'], 'Documents')
        self.assertEqual(files[1]['name'], 'report.pdf')
        self.assertEqual(files[1]['indent'], 1)
        self.assertEqual(files[2]['name'], 'file.txt')
    
    def test_list_subdirectory(self):
        """测试列出子目录"""
        volume = MagicMock()
        
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                ]
            elif cnid == 100:
                return [
                    {'name': 'report.pdf', 'type': 'file', 'id': 300, 'size': 2048},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        files = list_files(volume, '/Documents', recursive=False)
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['name'], 'report.pdf')


class TestExtractFiles(unittest.TestCase):
    """测试文件提取"""
    
    def test_extract_files(self):
        """测试提取文件"""
        volume = MagicMock()
        
        def mock_list_folder(cnid):
            if cnid == 2:
                return [
                    {'name': 'Documents', 'type': 'folder', 'id': 100},
                    {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
                ]
            elif cnid == 100:
                return [
                    {'name': 'report.pdf', 'type': 'file', 'id': 300, 'size': 2048},
                ]
            return []
        
        volume.list_folder.side_effect = mock_list_folder
        
        def mock_read_file(file_id):
            if file_id == 200:
                return b'\x00' * 1024
            elif file_id == 300:
                return b'\x01' * 2048
            return b''
        
        volume.read_file.side_effect = mock_read_file
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            count = extract_files(volume, tmpdir, '/', recursive=True, force=True)
            
            # 验证提取的文件数
            self.assertEqual(count, 2)
            
            # 验证文件是否存在
            # 由于递归顺序，文件可能在不同位置
            # 检查根目录下的文件
            root_files = [f for f in os.listdir(tmpdir) if os.path.isfile(os.path.join(tmpdir, f))]
            self.assertTrue(len(root_files) >= 1)
            
            # 检查 Documents 目录
            docs_dir = os.path.join(tmpdir, 'Documents')
            if os.path.exists(docs_dir):
                docs_files = os.listdir(docs_dir)
                self.assertTrue(len(docs_files) >= 1)
    
    def test_extract_no_overwrite(self):
        """测试不覆盖已存在的文件"""
        volume = MagicMock()
        
        volume.list_folder.return_value = [
            {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
        ]
        
        volume.read_file.return_value = b'\x00' * 1024
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建已存在的文件
            existing_file = os.path.join(tmpdir, 'file.txt')
            with open(existing_file, 'wb') as f:
                f.write(b'\x01' * 512)
            
            # 不覆盖模式
            count = extract_files(volume, tmpdir, '/', recursive=False, force=False)
            
            # 验证文件数
            self.assertEqual(count, 0)
            
            # 验证文件内容未被覆盖
            with open(existing_file, 'rb') as f:
                self.assertEqual(f.read(), b'\x01' * 512)
    
    def test_extract_force_overwrite(self):
        """测试强制覆盖已存在的文件"""
        volume = MagicMock()
        
        volume.list_folder.return_value = [
            {'name': 'file.txt', 'type': 'file', 'id': 200, 'size': 1024},
        ]
        
        volume.read_file.return_value = b'\x00' * 1024
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建已存在的文件
            existing_file = os.path.join(tmpdir, 'file.txt')
            with open(existing_file, 'wb') as f:
                f.write(b'\x01' * 512)
            
            # 强制覆盖模式
            count = extract_files(volume, tmpdir, '/', recursive=False, force=True)
            
            # 验证文件数
            self.assertEqual(count, 1)
            
            # 验证文件内容被覆盖
            with open(existing_file, 'rb') as f:
                self.assertEqual(f.read(), b'\x00' * 1024)


if __name__ == '__main__':
    unittest.main()
