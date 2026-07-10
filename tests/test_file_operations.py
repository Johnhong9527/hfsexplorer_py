#!/usr/bin/env python3
"""
文件操作集成测试

测试完整的文件操作流程：创建、复制、移动、重命名、删除。
"""

import pytest
import sys
import os
import tempfile

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.hfs.formatter import HFSPlusFormatter
from src.core.hfs import HFSPlusVolume
from src.core.hfs.writer import CatalogWriter, CopyManager


class TestFileOperationsIntegration:
    """文件操作集成测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前的设置"""
        # 创建临时文件
        self.temp_path = tempfile.mktemp(suffix='.img')
        
        # 创建 10MB 的测试文件
        with open(self.temp_path, 'wb') as f:
            f.seek(10 * 1024 * 1024 - 1)
            f.write(b'\x00')
        
        # 格式化为 HFS+
        formatter = HFSPlusFormatter()
        self.header = formatter.format(self.temp_path, 'TestVolume', 4096)
        
        # 打开卷进行写入
        self.stream = open(self.temp_path, 'r+b')
        self.vol = HFSPlusVolume(self.temp_path)
        self.catalog = self.vol.catalog
        
        self.writer = CatalogWriter(self.catalog, self.header, self.stream)
        self.copy_manager = CopyManager(self.writer, self.vol)
        
        yield
        
        # 清理
        self.vol.close()
        self.stream.close()
        if os.path.exists(self.temp_path):
            os.unlink(self.temp_path)
    
    def test_create_file(self):
        """测试创建文件"""
        file_id = self.writer.create_file(2, 'test.txt', b'Hello World')
        
        # 验证文件存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert any(item['name'] == 'test.txt' for item in contents)
        
        # 验证文件内容
        data = vol.read_file(file_id)
        assert data == b'Hello World'
        vol.close()
    
    def test_create_folder(self):
        """测试创建文件夹"""
        folder_id = self.writer.create_folder(2, 'TestFolder')
        
        # 验证文件夹存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert any(item['name'] == 'TestFolder' for item in contents)
        vol.close()
    
    def test_move_file(self):
        """测试移动文件"""
        # 创建文件和文件夹
        file_id = self.writer.create_file(2, 'file.txt', b'data')
        folder_id = self.writer.create_folder(2, 'Folder')
        
        # 移动文件
        self.writer.move_entry(2, 'file.txt', folder_id, 'file.txt')
        
        # 验证文件已从根目录移除
        vol = HFSPlusVolume(self.temp_path)
        root_contents = vol.list_folder(2)
        assert not any(item['name'] == 'file.txt' for item in root_contents)
        
        # 验证文件已移动到目标文件夹
        folder_contents = vol.list_folder(folder_id)
        assert any(item['name'] == 'file.txt' for item in folder_contents)
        
        # 验证文件内容保持不变
        moved_file = next(item for item in folder_contents if item['name'] == 'file.txt')
        data = vol.read_file(moved_file['id'])
        assert data == b'data'
        vol.close()
    
    def test_rename_file(self):
        """测试重命名文件"""
        # 创建文件
        file_id = self.writer.create_file(2, 'old_name.txt', b'data')
        
        # 重命名文件
        self.writer.rename_entry(2, 'old_name.txt', 'new_name.txt')
        
        # 验证旧名称不存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert not any(item['name'] == 'old_name.txt' for item in contents)
        
        # 验证新名称存在
        assert any(item['name'] == 'new_name.txt' for item in contents)
        
        # 验证文件内容保持不变
        renamed_file = next(item for item in contents if item['name'] == 'new_name.txt')
        data = vol.read_file(renamed_file['id'])
        assert data == b'data'
        vol.close()
    
    def test_delete_file(self):
        """测试删除文件"""
        # 创建文件
        file_id = self.writer.create_file(2, 'to_delete.txt', b'data')
        
        # 删除文件
        self.writer.delete_entry(2, 'to_delete.txt')
        
        # 验证文件不存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert not any(item['name'] == 'to_delete.txt' for item in contents)
        vol.close()
    
    def test_copy_file(self):
        """测试复制文件"""
        # 创建文件
        file_id = self.writer.create_file(2, 'original.txt', b'original data')
        
        # 复制文件
        new_id = self.copy_manager.copy_entry(2, 'original.txt', 2, 'copy.txt')
        
        # 验证两个文件都存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert any(item['name'] == 'original.txt' for item in contents)
        assert any(item['name'] == 'copy.txt' for item in contents)
        
        # 验证复制文件的内容
        data = vol.read_file(new_id)
        assert data == b'original data'
        vol.close()
    
    def test_copy_file_to_folder(self):
        """测试复制文件到另一个文件夹"""
        # 创建文件和文件夹
        file_id = self.writer.create_file(2, 'file.txt', b'data')
        folder_id = self.writer.create_folder(2, 'TargetFolder')
        
        # 复制文件到文件夹
        new_id = self.copy_manager.copy_entry(2, 'file.txt', folder_id, 'file_copy.txt')
        
        # 验证原文件仍在根目录
        vol = HFSPlusVolume(self.temp_path)
        root_contents = vol.list_folder(2)
        assert any(item['name'] == 'file.txt' for item in root_contents)
        
        # 验证复制文件在目标文件夹中
        folder_contents = vol.list_folder(folder_id)
        assert any(item['name'] == 'file_copy.txt' for item in folder_contents)
        
        # 验证内容相同
        data = vol.read_file(new_id)
        assert data == b'data'
        vol.close()
    
    def test_copy_folder(self):
        """测试复制文件夹（递归）"""
        # 创建文件夹和文件
        folder_id = self.writer.create_folder(2, 'SourceFolder')
        file_id = self.writer.create_file(folder_id, 'nested.txt', b'nested data')
        
        # 复制文件夹
        new_folder_id = self.copy_manager.copy_entry(2, 'SourceFolder', 2, 'DestFolder')
        
        # 验证两个文件夹都存在
        vol = HFSPlusVolume(self.temp_path)
        root_contents = vol.list_folder(2)
        assert any(item['name'] == 'SourceFolder' for item in root_contents)
        assert any(item['name'] == 'DestFolder' for item in root_contents)
        
        # 验证复制的文件夹中有文件
        dest_contents = vol.list_folder(new_folder_id)
        assert len(dest_contents) == 1
        assert dest_contents[0]['name'] == 'nested.txt'
        
        # 验证文件内容
        data = vol.read_file(dest_contents[0]['id'])
        assert data == b'nested data'
        vol.close()
    
    def test_duplicate_file(self):
        """测试复制文件到同一位置（创建副本）"""
        # 创建文件
        file_id = self.writer.create_file(2, 'document.txt', b'content')
        
        # 复制文件
        new_id = self.copy_manager.duplicate_entry(2, 'document.txt')
        
        # 验证两个文件都存在
        vol = HFSPlusVolume(self.temp_path)
        contents = vol.list_folder(2)
        assert any(item['name'] == 'document.txt' for item in contents)
        assert any('副本' in item['name'] for item in contents)
        
        # 验证内容相同
        data = vol.read_file(new_id)
        assert data == b'content'
        vol.close()
    
    def test_multiple_operations(self):
        """测试多个操作的组合"""
        # 创建初始结构
        folder1_id = self.writer.create_folder(2, 'Folder1')
        folder2_id = self.writer.create_folder(2, 'Folder2')
        file1_id = self.writer.create_file(2, 'file1.txt', b'data1')
        file2_id = self.writer.create_file(2, 'file2.txt', b'data2')
        
        # 移动 file1 到 Folder1
        self.writer.move_entry(2, 'file1.txt', folder1_id, 'file1.txt')
        
        # 复制 file2 到 Folder2
        self.copy_manager.copy_entry(2, 'file2.txt', folder2_id, 'file2_copy.txt')
        
        # 重命名 Folder1 中的文件
        self.writer.rename_entry(folder1_id, 'file1.txt', 'file1_renamed.txt')
        
        # 删除原始 file2
        self.writer.delete_entry(2, 'file2.txt')
        
        # 验证最终状态
        vol = HFSPlusVolume(self.temp_path)
        
        root_contents = vol.list_folder(2)
        root_names = [item['name'] for item in root_contents]
        assert 'Folder1' in root_names
        assert 'Folder2' in root_names
        assert 'file1.txt' not in root_names
        assert 'file2.txt' not in root_names
        
        folder1_contents = vol.list_folder(folder1_id)
        assert len(folder1_contents) == 1
        assert folder1_contents[0]['name'] == 'file1_renamed.txt'
        
        folder2_contents = vol.list_folder(folder2_id)
        assert len(folder2_contents) == 1
        assert folder2_contents[0]['name'] == 'file2_copy.txt'
        
        # 验证文件内容
        data1 = vol.read_file(folder1_contents[0]['id'])
        assert data1 == b'data1'
        
        data2 = vol.read_file(folder2_contents[0]['id'])
        assert data2 == b'data2'
        
        vol.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
