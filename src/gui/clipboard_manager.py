#!/usr/bin/env python3
"""
剪贴板管理器

提供文件和文件夹的复制、剪切、粘贴功能。
"""

import os
from typing import List, Optional, Dict, Any
from enum import Enum

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QMimeData, QUrl


class ClipboardOperation(Enum):
    """剪贴板操作类型"""
    COPY = "copy"
    CUT = "cut"


class ClipboardItem:
    """剪贴板项目"""
    
    def __init__(self, parent_id: int, name: str, item_type: str, 
                 item_id: int = 0, size: int = 0):
        """
        初始化剪贴板项目
        
        Args:
            parent_id: 父文件夹 CNID
            name: 项目名称
            item_type: 项目类型 ('file' 或 'folder')
            item_id: 项目 CNID
            size: 文件大小
        """
        self.parent_id = parent_id
        self.name = name
        self.item_type = item_type
        self.item_id = item_id
        self.size = size
    
    def __repr__(self):
        return f"ClipboardItem(parent={self.parent_id}, name='{self.name}', type={self.item_type})"


class ClipboardManager:
    """
    剪贴板管理器
    
    管理文件和文件夹的复制、剪切、粘贴操作。
    
    Usage:
        clipboard = ClipboardManager()
        
        # 复制文件
        clipboard.copy([ClipboardItem(2, "test.txt", "file")])
        
        # 剪切文件
        clipboard.cut([ClipboardItem(2, "test.txt", "file")])
        
        # 粘贴文件
        items = clipboard.get_items()
        operation = clipboard.get_operation()
    """
    
    def __init__(self):
        """初始化剪贴板管理器"""
        self._items: List[ClipboardItem] = []
        self._operation: Optional[ClipboardOperation] = None
        self._source_path: Optional[str] = None
    
    def copy(self, items: List[ClipboardItem], source_path: str = None):
        """
        复制项目到剪贴板
        
        Args:
            items: 要复制的项目列表
            source_path: 源文件路径
        """
        self._items = items.copy()
        self._operation = ClipboardOperation.COPY
        self._source_path = source_path
        
        # 同步到系统剪贴板
        self._sync_to_system_clipboard()
    
    def cut(self, items: List[ClipboardItem], source_path: str = None):
        """
        剪切项目到剪贴板
        
        Args:
            items: 要剪切的项目列表
            source_path: 源文件路径
        """
        self._items = items.copy()
        self._operation = ClipboardOperation.CUT
        self._source_path = source_path
        
        # 同步到系统剪贴板
        self._sync_to_system_clipboard()
    
    def paste(self) -> List[ClipboardItem]:
        """
        粘贴项目
        
        Returns:
            要粘贴的项目列表
        """
        if not self._items:
            return []
        
        # 返回项目副本
        return self._items.copy()
    
    def get_operation(self) -> Optional[ClipboardOperation]:
        """
        获取当前操作类型
        
        Returns:
            操作类型
        """
        return self._operation
    
    def get_items(self) -> List[ClipboardItem]:
        """
        获取剪贴板中的项目
        
        Returns:
            项目列表
        """
        return self._items.copy()
    
    def get_source_path(self) -> Optional[str]:
        """
        获取源文件路径
        
        Returns:
            源文件路径
        """
        return self._source_path
    
    def has_content(self) -> bool:
        """
        检查剪贴板是否有内容
        
        Returns:
            是否有内容
        """
        return len(self._items) > 0
    
    def clear(self):
        """清空剪贴板"""
        self._items.clear()
        self._operation = None
        self._source_path = None
    
    def _sync_to_system_clipboard(self):
        """同步到系统剪贴板"""
        try:
            clipboard = QApplication.clipboard()
            mime_data = QMimeData()
            
            # 设置文件 URL
            urls = []
            for item in self._items:
                # 这里需要实际的文件路径，暂时使用占位符
                # 实际实现需要从 HFS+ 卷中提取文件到临时目录
                pass
            
            if urls:
                mime_data.setUrls(urls)
                clipboard.setMimeData(mime_data)
        except Exception:
            # 系统剪贴板同步失败，忽略
            pass
    
    def get_summary(self) -> str:
        """
        获取剪贴板内容摘要
        
        Returns:
            摘要文本
        """
        if not self._items:
            return "剪贴板为空"
        
        file_count = sum(1 for item in self._items if item.item_type == 'file')
        folder_count = sum(1 for item in self._items if item.item_type == 'folder')
        
        operation = "复制" if self._operation == ClipboardOperation.COPY else "剪切"
        
        parts = []
        if file_count > 0:
            parts.append(f"{file_count} 个文件")
        if folder_count > 0:
            parts.append(f"{folder_count} 个文件夹")
        
        return f"{operation} {', '.join(parts)}"
    
    def duplicate_items(self) -> List[ClipboardItem]:
        """
        生成副本项目列表（用于在同一文件夹下创建副本）
        
        Returns:
            副本项目列表
        """
        if not self._items:
            return []
        
        # 为每个项目生成副本名称
        duplicated = []
        for item in self._items:
            base_name, ext = os.path.splitext(item.name)
            copy_name = f"{base_name} 副本{ext}"
            
            # 检查名称是否已存在（简化处理）
            counter = 1
            # 实际实现需要检查文件系统中是否存在同名文件
            
            duplicated.append(ClipboardItem(
                parent_id=item.parent_id,
                name=copy_name,
                item_type=item.item_type,
                item_id=item.item_id,
                size=item.size
            ))
        
        return duplicated


class ClipboardHistory:
    """
    剪贴板历史记录
    
    记录剪贴板操作历史，支持撤销。
    """
    
    def __init__(self, max_history: int = 10):
        """
        初始化剪贴板历史
        
        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
    
    def add_operation(self, operation: ClipboardOperation, 
                      items: List[ClipboardItem], source_path: str = None):
        """
        添加操作到历史
        
        Args:
            operation: 操作类型
            items: 操作的项目
            source_path: 源文件路径
        """
        entry = {
            'operation': operation,
            'items': items.copy(),
            'source_path': source_path,
            'timestamp': __import__('time').time()
        }
        
        self.history.append(entry)
        
        # 限制历史记录数
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        """
        获取最后的操作
        
        Returns:
            最后的操作记录
        """
        if not self.history:
            return None
        return self.history[-1]
    
    def clear(self):
        """清空历史"""
        self.history.clear()
