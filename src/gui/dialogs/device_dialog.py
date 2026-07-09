"""
设备选择对话框

用于选择物理硬盘设备。
"""

import os
import platform
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QLineEdit, QGroupBox,
    QButtonGroup, QMessageBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt


class DeviceInfo:
    """设备信息"""
    
    def __init__(self, path: str, name: str, size: int = 0, model: str = ""):
        self.path = path
        self.name = name
        self.size = size
        self.model = model
    
    @property
    def size_str(self) -> str:
        """格式化大小"""
        if self.size == 0:
            return "未知"
        elif self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.2f} GB"
    
    def __str__(self) -> str:
        if self.model:
            return f"{self.name} - {self.model} ({self.size_str})"
        return f"{self.name} ({self.size_str})"


def detect_devices() -> List[DeviceInfo]:
    """
    检测系统中的硬盘设备
    
    Returns:
        设备信息列表
    """
    devices = []
    system = platform.system()
    
    if system == "Linux":
        # Linux: 检查 /dev/sd*, /dev/nvme*, /dev/vd* 等
        dev_paths = []
        
        # SCSI/SATA 设备及其分区
        for i in range(26):
            dev_base = f"sd{chr(97 + i)}"
            dev_path = f"/dev/{dev_base}"
            if os.path.exists(dev_path):
                dev_paths.append(dev_path)
                # 检测分区
                for j in range(1, 20):
                    part_path = f"/dev/{dev_base}{j}"
                    if os.path.exists(part_path):
                        dev_paths.append(part_path)
        
        # NVMe 设备及其分区
        for i in range(10):
            for j in range(10):
                dev_base = f"nvme{i}n{j}"
                dev_path = f"/dev/{dev_base}"
                if os.path.exists(dev_path):
                    dev_paths.append(dev_path)
                    # 检测分区
                    for k in range(1, 20):
                        part_path = f"/dev/{dev_base}p{k}"
                        if os.path.exists(part_path):
                            dev_paths.append(part_path)
        
        # 虚拟设备及其分区
        for i in range(26):
            dev_base = f"vd{chr(97 + i)}"
            dev_path = f"/dev/{dev_base}"
            if os.path.exists(dev_path):
                dev_paths.append(dev_path)
                for j in range(1, 20):
                    part_path = f"/dev/{dev_base}{j}"
                    if os.path.exists(part_path):
                        dev_paths.append(part_path)
        
        # 获取设备信息
        for dev_path in dev_paths:
            name = os.path.basename(dev_path)
            size = _get_device_size_linux(dev_path)
            model = _get_device_model_linux(dev_path)
            # 检查权限
            readable = os.access(dev_path, os.R_OK)
            if not readable:
                name += " (需要root权限)"
            devices.append(DeviceInfo(dev_path, name, size, model))
    
    elif system == "Windows":
        # Windows: 检查 PhysicalDrive0, 1, 2...
        for i in range(10):
            dev_path = f"\\\\.\\PhysicalDrive{i}"
            name = f"PhysicalDrive{i}"
            devices.append(DeviceInfo(dev_path, name))
    
    elif system == "Darwin":
        # macOS: 检查 /dev/disk0, 1, 2...
        for i in range(20):
            dev_path = f"/dev/disk{i}"
            if os.path.exists(dev_path):
                name = f"disk{i}"
                size = _get_device_size_linux(dev_path)
                devices.append(DeviceInfo(dev_path, name, size))
    
    return devices


def _get_device_size_linux(dev_path: str) -> int:
    """获取 Linux 设备大小"""
    try:
        # 尝试从 /sys/block 获取大小
        basename = os.path.basename(dev_path)
        size_file = f"/sys/block/{basename}/size"
        if os.path.exists(size_file):
            with open(size_file, 'r') as f:
                sectors = int(f.read().strip())
                return sectors * 512  # 扇区大小 512 字节
    except:
        pass
    return 0


def _get_device_model_linux(dev_path: str) -> str:
    """获取 Linux 设备型号"""
    try:
        basename = os.path.basename(dev_path)
        # 去除分区号（如果有）
        if basename[-1].isdigit():
            basename = basename.rstrip('0123456789')
        
        model_file = f"/sys/block/{basename}/device/model"
        if os.path.exists(model_file):
            with open(model_file, 'r') as f:
                return f.read().strip()
    except:
        pass
    return ""


class DeviceSelectionDialog(QDialog):
    """
    设备选择对话框
    
    用于选择物理硬盘设备。
    
    Usage:
        dialog = DeviceSelectionDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            device_path = dialog.get_selected_device()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择设备")
        self.setMinimumWidth(500)
        
        self._selected_device: Optional[str] = None
        self._devices: List[DeviceInfo] = []
        
        self._setup_ui()
        self._detect_devices()
    
    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # 设备选择组
        device_group = QGroupBox("选择设备")
        device_layout = QVBoxLayout(device_group)
        
        # 自动检测的设备
        self.auto_radio = QRadioButton("从检测到的设备中选择:")
        self.auto_radio.setChecked(True)
        device_layout.addWidget(self.auto_radio)
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(150)
        device_layout.addWidget(self.device_list)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新设备列表")
        refresh_button.clicked.connect(self._detect_devices)
        refresh_layout.addWidget(refresh_button)
        refresh_layout.addStretch()
        device_layout.addLayout(refresh_layout)
        
        # 手动输入
        self.manual_radio = QRadioButton("手动指定设备路径:")
        device_layout.addWidget(self.manual_radio)
        
        manual_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("例如: /dev/sda 或 \\\\.\\PhysicalDrive0")
        self.path_edit.setEnabled(False)
        manual_layout.addWidget(self.path_edit)
        device_layout.addLayout(manual_layout)
        
        # 单选按钮组
        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.auto_radio)
        self.radio_group.addButton(self.manual_radio)
        
        # 连接信号
        self.auto_radio.toggled.connect(self._on_radio_changed)
        
        layout.addWidget(device_group)
        
        # 警告标签
        warning_label = QLabel(
            "⚠️ 警告：直接访问物理设备可能导致数据损坏！\n"
            "请确保您知道自己在做什么。"
        )
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(warning_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        load_button = QPushButton("加载")
        load_button.clicked.connect(self._on_load)
        button_layout.addWidget(load_button)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _detect_devices(self):
        """检测设备"""
        self.device_list.clear()
        self._devices = detect_devices()
        
        for device in self._devices:
            item = QListWidgetItem(str(device))
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.device_list.addItem(item)
        
        if self._devices:
            self.device_list.setCurrentRow(0)
    
    def _on_radio_changed(self, checked: bool):
        """单选按钮状态改变"""
        self.device_list.setEnabled(checked)
        self.path_edit.setEnabled(not checked)
    
    def _on_load(self):
        """加载按钮点击"""
        if self.auto_radio.isChecked():
            # 从列表中选择
            current_item = self.device_list.currentItem()
            if current_item is None:
                QMessageBox.warning(self, "警告", "请选择一个设备")
                return
            
            device = current_item.data(Qt.ItemDataRole.UserRole)
            self._selected_device = device.path
        else:
            # 手动输入
            path = self.path_edit.text().strip()
            if not path:
                QMessageBox.warning(self, "警告", "请输入设备路径")
                return
            
            if not os.path.exists(path):
                QMessageBox.warning(self, "警告", f"设备不存在: {path}")
                return
            
            self._selected_device = path
        
        self.accept()
    
    def get_selected_device(self) -> Optional[str]:
        """获取选中的设备路径"""
        return self._selected_device


def show_device_selection_dialog(parent=None) -> Optional[str]:
    """
    显示设备选择对话框的便捷函数
    
    Args:
        parent: 父窗口
    
    Returns:
        选中的设备路径，如果取消则返回 None
    """
    dialog = DeviceSelectionDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_selected_device()
    return None
