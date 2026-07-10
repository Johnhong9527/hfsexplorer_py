#!/usr/bin/env python3
"""
剪贴板管理器测试

测试复制、剪切、粘贴功能。
"""

import pytest
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.clipboard_manager import (
    ClipboardManager,
    ClipboardItem,
    ClipboardOperation,
    ClipboardHistory
)


class TestClipboardItem:
    """测试 ClipboardItem"""
    
    def test_create_item(self):
        """测试创建剪贴板项目"""
        item = ClipboardItem(
            parent_id=2,
            name="test.txt",
            item_type="file",
            item_id=100,
            size=1024
        )
        
        assert item.parent_id == 2
        assert item.name == "test.txt"
        assert item.item_type == "file"
        assert item.item_id == 100
        assert item.size == 1024
    
    def test_create_folder_item(self):
        """测试创建文件夹项目"""
        item = ClipboardItem(
            parent_id=2,
            name="Documents",
            item_type="folder",
            item_id=200
        )
        
        assert item.parent_id == 2
        assert item.name == "Documents"
        assert item.item_type == "folder"
        assert item.item_id == 200
        assert item.size == 0  # 文件夹默认大小为 0
    
    def test_repr(self):
        """测试字符串表示"""
        item = ClipboardItem(2, "test.txt", "file", 100, 1024)
        repr_str = repr(item)
        
        assert "test.txt" in repr_str
        assert "file" in repr_str
        assert "2" in repr_str


class TestClipboardManager:
    """测试 ClipboardManager"""
    
    def setup_method(self):
        """每个测试前的设置"""
        self.manager = ClipboardManager()
    
    def test_initial_state(self):
        """测试初始状态"""
        assert not self.manager.has_content()
        assert self.manager.get_operation() is None
        assert self.manager.get_items() == []
        assert self.manager.get_source_path() is None
    
    def test_copy(self):
        """测试复制操作"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024),
            ClipboardItem(2, "file2.txt", "file", 101, 2048)
        ]
        
        self.manager.copy(items, "/path/to/volume")
        
        assert self.manager.has_content()
        assert self.manager.get_operation() == ClipboardOperation.COPY
        assert len(self.manager.get_items()) == 2
        assert self.manager.get_source_path() == "/path/to/volume"
    
    def test_cut(self):
        """测试剪切操作"""
        items = [
            ClipboardItem(2, "folder1", "folder", 200)
        ]
        
        self.manager.cut(items, "/path/to/volume")
        
        assert self.manager.has_content()
        assert self.manager.get_operation() == ClipboardOperation.CUT
        assert len(self.manager.get_items()) == 1
    
    def test_paste(self):
        """测试粘贴操作"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024)
        ]
        
        self.manager.copy(items)
        pasted = self.manager.paste()
        
        assert len(pasted) == 1
        assert pasted[0].name == "file1.txt"
    
    def test_paste_empty(self):
        """测试空剪贴板粘贴"""
        pasted = self.manager.paste()
        assert pasted == []
    
    def test_clear(self):
        """测试清空剪贴板"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024)
        ]
        
        self.manager.copy(items)
        assert self.manager.has_content()
        
        self.manager.clear()
        assert not self.manager.has_content()
        assert self.manager.get_operation() is None
        assert self.manager.get_items() == []
    
    def test_summary_copy(self):
        """测试复制操作摘要"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024),
            ClipboardItem(2, "file2.txt", "file", 101, 2048),
            ClipboardItem(2, "folder1", "folder", 200)
        ]
        
        self.manager.copy(items)
        summary = self.manager.get_summary()
        
        assert "复制" in summary
        assert "2 个文件" in summary
        assert "1 个文件夹" in summary
    
    def test_summary_cut(self):
        """测试剪切操作摘要"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024)
        ]
        
        self.manager.cut(items)
        summary = self.manager.get_summary()
        
        assert "剪切" in summary
        assert "1 个文件" in summary
    
    def test_summary_empty(self):
        """测试空剪贴板摘要"""
        summary = self.manager.get_summary()
        assert "剪贴板为空" in summary
    
    def test_duplicate_items(self):
        """测试生成副本项目"""
        items = [
            ClipboardItem(2, "file1.txt", "file", 100, 1024),
            ClipboardItem(2, "document.pdf", "file", 101, 2048)
        ]
        
        self.manager.copy(items)
        duplicated = self.manager.duplicate_items()
        
        assert len(duplicated) == 2
        assert "副本" in duplicated[0].name
        assert "file1" in duplicated[0].name
        assert ".txt" in duplicated[0].name
        assert "副本" in duplicated[1].name
        assert "document" in duplicated[1].name
        assert ".pdf" in duplicated[1].name
    
    def test_duplicate_empty(self):
        """测试空剪贴板生成副本"""
        duplicated = self.manager.duplicate_items()
        assert duplicated == []


class TestClipboardHistory:
    """测试 ClipboardHistory"""
    
    def setup_method(self):
        """每个测试前的设置"""
        self.history = ClipboardHistory(max_history=5)
    
    def test_initial_state(self):
        """测试初始状态"""
        assert self.history.get_last_operation() is None
    
    def test_add_operation(self):
        """测试添加操作"""
        items = [ClipboardItem(2, "file1.txt", "file", 100, 1024)]
        
        self.history.add_operation(ClipboardOperation.COPY, items, "/path")
        
        last = self.history.get_last_operation()
        assert last is not None
        assert last['operation'] == ClipboardOperation.COPY
        assert len(last['items']) == 1
        assert last['source_path'] == "/path"
    
    def test_multiple_operations(self):
        """测试多个操作"""
        items1 = [ClipboardItem(2, "file1.txt", "file", 100, 1024)]
        items2 = [ClipboardItem(2, "file2.txt", "file", 101, 2048)]
        
        self.history.add_operation(ClipboardOperation.COPY, items1)
        self.history.add_operation(ClipboardOperation.CUT, items2)
        
        last = self.history.get_last_operation()
        assert last['operation'] == ClipboardOperation.CUT
    
    def test_max_history(self):
        """测试最大历史记录数"""
        for i in range(10):
            items = [ClipboardItem(2, f"file{i}.txt", "file", i, 1024)]
            self.history.add_operation(ClipboardOperation.COPY, items)
        
        assert len(self.history.history) == 5
    
    def test_clear(self):
        """测试清空历史"""
        items = [ClipboardItem(2, "file1.txt", "file", 100, 1024)]
        self.history.add_operation(ClipboardOperation.COPY, items)
        
        self.history.clear()
        assert self.history.get_last_operation() is None
        assert len(self.history.history) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
