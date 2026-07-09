"""
HFS+ 信息面板

提供文件、文件夹和卷的详细信息显示。
"""

import struct
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.hfs import (
    HFSPlusVolumeHeader,
    HFSPlusCatalogFile,
    HFSPlusCatalogFolder,
    HFS_EPOCH_OFFSET,
)


def hfs_date_to_string(timestamp: int) -> str:
    """将 HFS 日期转换为字符串"""
    if timestamp == 0:
        return "未设置"
    try:
        unix_timestamp = timestamp - HFS_EPOCH_OFFSET
        dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "无效日期"


def format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} 字节"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB ({size:,} 字节)"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB ({size:,} 字节)"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB ({size:,} 字节)"


def format_mode(mode: int) -> str:
    """格式化文件模式"""
    # 文件类型
    file_type = mode & 0xF000
    if file_type == 0x4000:
        type_char = 'd'  # 目录
    elif file_type == 0x8000:
        type_char = '-'  # 普通文件
    elif file_type == 0xA000:
        type_char = 'l'  # 符号链接
    elif file_type == 0xC000:
        type_char = 's'  # 套接字
    elif file_type == 0x6000:
        type_char = 'b'  # 块设备
    elif file_type == 0x2000:
        type_char = 'c'  # 字符设备
    elif file_type == 0x1000:
        type_char = 'p'  # 命名管道
    else:
        type_char = '?'
    
    # 权限
    perms = mode & 0xFFF
    owner = (perms >> 6) & 7
    group = (perms >> 3) & 7
    other = perms & 7
    
    def perm_str(p):
        r = 'r' if p & 4 else '-'
        w = 'w' if p & 2 else '-'
        x = 'x' if p & 1 else '-'
        return r + w + x
    
    return f"{type_char}{perm_str(owner)}{perm_str(group)}{perm_str(other)}"


class FileInfoPanel(QWidget):
    """
    文件信息面板
    
    显示文件的详细信息，包括：
    - 基本信息（名称、大小、类型）
    - 日期信息（创建、修改、访问、备份）
    - POSIX 权限信息
    - Finder 信息
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # 内容容器
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        
        # 基本信息组
        self.basic_group = QGroupBox("基本信息")
        self.basic_layout = QFormLayout(self.basic_group)
        self.content_layout.addWidget(self.basic_group)
        
        # 日期信息组
        self.dates_group = QGroupBox("日期信息")
        self.dates_layout = QFormLayout(self.dates_group)
        self.content_layout.addWidget(self.dates_group)
        
        # 权限信息组
        self.permissions_group = QGroupBox("权限信息")
        self.permissions_layout = QFormLayout(self.permissions_group)
        self.content_layout.addWidget(self.permissions_group)
        
        # 添加弹性空间
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # 初始化标签
        self._init_labels()
    
    def _init_labels(self):
        """初始化标签"""
        # 基本信息标签
        self.name_label = QLabel()
        self.type_label = QLabel()
        self.size_label = QLabel()
        self.cnid_label = QLabel()
        
        self.basic_layout.addRow("名称:", self.name_label)
        self.basic_layout.addRow("类型:", self.type_label)
        self.basic_layout.addRow("大小:", self.size_label)
        self.basic_layout.addRow("CNID:", self.cnid_label)
        
        # 日期标签
        self.create_date_label = QLabel()
        self.mod_date_label = QLabel()
        self.access_date_label = QLabel()
        self.backup_date_label = QLabel()
        self.attr_mod_date_label = QLabel()
        
        self.dates_layout.addRow("创建日期:", self.create_date_label)
        self.dates_layout.addRow("修改日期:", self.mod_date_label)
        self.dates_layout.addRow("访问日期:", self.access_date_label)
        self.dates_layout.addRow("备份日期:", self.backup_date_label)
        self.dates_layout.addRow("属性修改:", self.attr_mod_date_label)
        
        # 权限标签
        self.owner_label = QLabel()
        self.group_label = QLabel()
        self.mode_label = QLabel()
        
        self.permissions_layout.addRow("所有者:", self.owner_label)
        self.permissions_layout.addRow("组:", self.group_label)
        self.permissions_layout.addRow("模式:", self.mode_label)
    
    def clear(self):
        """清空所有字段"""
        self.name_label.clear()
        self.type_label.clear()
        self.size_label.clear()
        self.cnid_label.clear()
        self.create_date_label.clear()
        self.mod_date_label.clear()
        self.access_date_label.clear()
        self.backup_date_label.clear()
        self.attr_mod_date_label.clear()
        self.owner_label.clear()
        self.group_label.clear()
        self.mode_label.clear()
    
    def set_file_info(self, name: str, file: HFSPlusCatalogFile):
        """设置文件信息"""
        self.name_label.setText(name)
        self.type_label.setText("文件")
        self.size_label.setText(format_size(file.get_data_fork_size()))
        self.cnid_label.setText(str(file.file_id))
        
        self.create_date_label.setText(hfs_date_to_string(file.create_date))
        self.mod_date_label.setText(hfs_date_to_string(file.content_mod_date))
        self.access_date_label.setText(hfs_date_to_string(file.access_date))
        self.backup_date_label.setText(hfs_date_to_string(file.backup_date))
        self.attr_mod_date_label.setText(hfs_date_to_string(file.attribute_mod_date))
        
        self.owner_label.setText(str(file.get_owner_id()))
        self.group_label.setText(str(file.get_group_id()))
        self.mode_label.setText(format_mode(file.get_file_mode()))
    
    def set_folder_info(self, name: str, folder: HFSPlusCatalogFolder):
        """设置文件夹信息"""
        self.name_label.setText(name)
        self.type_label.setText("文件夹")
        self.size_label.setText(f"{folder.valence} 个项目")
        self.cnid_label.setText(str(folder.folder_id))
        
        self.create_date_label.setText(hfs_date_to_string(folder.create_date))
        self.mod_date_label.setText(hfs_date_to_string(folder.content_mod_date))
        self.access_date_label.setText(hfs_date_to_string(folder.access_date))
        self.backup_date_label.setText(hfs_date_to_string(folder.backup_date))
        self.attr_mod_date_label.setText(hfs_date_to_string(folder.attribute_mod_date))
        
        self.owner_label.setText(str(folder.get_owner_id()))
        self.group_label.setText(str(folder.get_group_id()))
        self.mode_label.setText(format_mode(folder.get_file_mode()))


class VolumeInfoPanel(QWidget):
    """
    卷信息面板
    
    显示 HFS+ 卷的详细信息，包括：
    - 卷头信息
    - 统计信息
    - 空间使用情况
    - Fork 信息
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # 内容容器
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        
        # 基本信息组
        self.basic_group = QGroupBox("卷信息")
        self.basic_layout = QFormLayout(self.basic_group)
        self.content_layout.addWidget(self.basic_group)
        
        # 空间信息组
        self.space_group = QGroupBox("空间使用")
        self.space_layout = QFormLayout(self.space_group)
        self.content_layout.addWidget(self.space_group)
        
        # 统计信息组
        self.stats_group = QGroupBox("统计信息")
        self.stats_layout = QFormLayout(self.stats_group)
        self.content_layout.addWidget(self.stats_group)
        
        # 属性组
        self.attributes_group = QGroupBox("属性")
        self.attributes_layout = QFormLayout(self.attributes_group)
        self.content_layout.addWidget(self.attributes_group)
        
        # 添加弹性空间
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # 初始化标签
        self._init_labels()
    
    def _init_labels(self):
        """初始化标签"""
        # 基本信息标签
        self.signature_label = QLabel()
        self.version_label = QLabel()
        self.block_size_label = QLabel()
        self.total_blocks_label = QLabel()
        self.free_blocks_label = QLabel()
        
        self.basic_layout.addRow("签名:", self.signature_label)
        self.basic_layout.addRow("版本:", self.version_label)
        self.basic_layout.addRow("块大小:", self.block_size_label)
        self.basic_layout.addRow("总块数:", self.total_blocks_label)
        self.basic_layout.addRow("空闲块:", self.free_blocks_label)
        
        # 空间信息标签
        self.volume_size_label = QLabel()
        self.free_space_label = QLabel()
        self.used_space_label = QLabel()
        self.usage_percent_label = QLabel()
        
        self.space_layout.addRow("卷大小:", self.volume_size_label)
        self.space_layout.addRow("空闲空间:", self.free_space_label)
        self.space_layout.addRow("已用空间:", self.used_space_label)
        self.space_layout.addRow("使用率:", self.usage_percent_label)
        
        # 统计信息标签
        self.file_count_label = QLabel()
        self.folder_count_label = QLabel()
        self.next_catalog_id_label = QLabel()
        self.write_count_label = QLabel()
        
        self.stats_layout.addRow("文件数:", self.file_count_label)
        self.stats_layout.addRow("文件夹数:", self.folder_count_label)
        self.stats_layout.addRow("下一个 CNID:", self.next_catalog_id_label)
        self.stats_layout.writerow("写入计数:", self.write_count_label)
        
        # 属性标签
        self.journaled_label = QLabel()
        self.locked_label = QLabel()
        self.unmounted_label = QLabel()
        self.last_mounted_label = QLabel()
        
        self.attributes_layout.addRow("日志:", self.journaled_label)
        self.attributes_layout.addRow("锁定:", self.locked_label)
        self.attributes_layout.addRow("已卸载:", self.unmounted_label)
        self.attributes_layout.addRow("最后挂载:", self.last_mounted_label)
    
    def clear(self):
        """清空所有字段"""
        self.signature_label.clear()
        self.version_label.clear()
        self.block_size_label.clear()
        self.total_blocks_label.clear()
        self.free_blocks_label.clear()
        self.volume_size_label.clear()
        self.free_space_label.clear()
        self.used_space_label.clear()
        self.usage_percent_label.clear()
        self.file_count_label.clear()
        self.folder_count_label.clear()
        self.next_catalog_id_label.clear()
        self.write_count_label.clear()
        self.journaled_label.clear()
        self.locked_label.clear()
        self.unmounted_label.clear()
        self.last_mounted_label.clear()
    
    def set_volume_header(self, header: HFSPlusVolumeHeader):
        """设置卷头信息"""
        # 基本信息
        self.signature_label.setText("HFS+" if header.is_hfs_plus else "HFSX")
        self.version_label.setText(str(header.version))
        self.block_size_label.setText(f"{header.block_size:,} 字节")
        self.total_blocks_label.setText(f"{header.total_blocks:,}")
        self.free_blocks_label.setText(f"{header.free_blocks:,}")
        
        # 空间信息
        volume_size = header.volume_size
        free_space = header.free_space
        used_space = header.used_space
        usage_percent = (used_space / volume_size * 100) if volume_size > 0 else 0
        
        self.volume_size_label.setText(format_size(volume_size))
        self.free_space_label.setText(format_size(free_space))
        self.used_space_label.setText(format_size(used_space))
        self.usage_percent_label.setText(f"{usage_percent:.1f}%")
        
        # 统计信息
        self.file_count_label.setText(f"{header.file_count:,}")
        self.folder_count_label.setText(f"{header.folder_count:,}")
        self.next_catalog_id_label.setText(str(header.next_catalog_id))
        self.write_count_label.setText(str(header.write_count))
        
        # 属性
        self.journaled_label.setText("是" if header.is_journaled else "否")
        self.locked_label.setText("是" if header.is_locked else "否")
        self.unmounted_label.setText("是" if header.is_cleanly_unmounted else "否")
        self.last_mounted_label.setText(header.last_mounted_version)


class FilePropertiesPanel(QWidget):
    """
    文件属性面板
    
    显示文件或文件夹的完整属性信息。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 文件信息标签页
        self.file_info_panel = FileInfoPanel()
        self.tab_widget.addTab(self.file_info_panel, "文件信息")
        
        # 卷信息标签页
        self.volume_info_panel = VolumeInfoPanel()
        self.tab_widget.addTab(self.volume_info_panel, "卷信息")
        
        layout.addWidget(self.tab_widget)
    
    def clear(self):
        """清空所有字段"""
        self.file_info_panel.clear()
        self.volume_info_panel.clear()
    
    def set_file_info(self, name: str, file: HFSPlusCatalogFile):
        """设置文件信息"""
        self.file_info_panel.set_file_info(name, file)
        self.tab_widget.setCurrentIndex(0)
    
    def set_folder_info(self, name: str, folder: HFSPlusCatalogFolder):
        """设置文件夹信息"""
        self.file_info_panel.set_folder_info(name, folder)
        self.tab_widget.setCurrentIndex(0)
    
    def set_volume_header(self, header: HFSPlusVolumeHeader):
        """设置卷头信息"""
        self.volume_info_panel.set_volume_header(header)
        self.tab_widget.setCurrentIndex(1)