"""
设备选择对话框

用于选择物理硬盘设备，支持 USB设备。
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
    
    def __init__(self, path: str, name: str, size: int = 0, model: str = "", is_usb: bool = False):
        self.path = path
        self.name = name
        self.size = size
        self.model = model
        self.is_usb = is_usb
    
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
        usb_marker = " [USB]" if self.is_usb else ""
        if self.model:
            return f"{self.name}{usb_marker} - {self.model} ({self.size_str})"
        return f"{self.name}{usb_marker} ({self.size_str})"


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
        
        # SCSI/SATA/USB 设备及其分区
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
            is_usb = _is_removable_device(dev_path)
            # 检查权限
            readable = os.access(dev_path, os.R_OK)
            if not readable:
                name += " (需要root权限)"
            devices.append(DeviceInfo(dev_path, name, size, model, is_usb))
    
    elif system == "Windows":
        # Windows: 使用 wmic 获取磁盘信息
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'DeviceID,Size,Model,MediaType,InterfaceType'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                for line in lines:
                    if not line.strip():
                        continue
                    # 解析字段
                    device_id = None
                    model = ''
                    size = 0
                    is_usb = False
                    
                    # 查找设备ID (\\.\PhysicalDriveN)
                    if '\\\\' in line or 'PhysicalDrive' in line:
                        parts = line.split()
                        for j, part in enumerate(parts):
                            if 'PhysicalDrive' in part or part.startswith('\\\\'):
                                device_id = part
                                break
                    
                    if not device_id:
                        # 尝试另一种解析方式
                        if 'PhysicalDrive' in line:
                            idx = line.find('PhysicalDrive')
                            device_id = '\\\\.\\' + line[idx:idx+16].split()[0]
                    
                    if device_id:
                        # 查找大小
                        for part in line.split():
                            if part.isdigit() and int(part) > 1000000:
                                size = int(part)
                                break
                        
                        # 检查是否是 USB
                        is_usb = 'USB' in line.upper() or 'EXTERNAL' in line.upper() or 'REMOVABLE' in line.upper()
                        
                        # 获取型号
                        model_start = line.find('PhysicalDrive')
                        if model_start > 0:
                            model_part = line[model_start:]
                            parts = model_part.split()
                            if len(parts) > 1:
                                model = ' '.join(parts[1:-1]) if len(parts) > 2 else parts[1]
                        
                        name = device_id.split('\\')[-1] if '\\' in device_id else device_id
                        devices.append(DeviceInfo(device_id, name, size, model, is_usb))
        except Exception as e:
            # 备用方案：直接添加 PhysicalDrive
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


def _is_removable_device(dev_path: str) -> bool:
    """检查是否是可移动设备（USB）"""
    try:
        basename = os.path.basename(dev_path)
        # 去除分区号
        if basename[-1].isdigit():
            basename = basename.rstrip('0123456789')
        
        removable_file = f"/sys/block/{basename}/removable"
        if os.path.exists(removable_file):
            with open(removable_file, 'r') as f:
                return f.read().strip() == '1'
    except:
        pass
    return False


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
        
        # 自动检测按钮
        autodetect_layout = QHBoxLayout()
        autodetect_button = QPushButton("自动检测...")
        autodetect_button.clicked.connect(self._autodetect_hfs)
        autodetect_layout.addWidget(autodetect_button)
        autodetect_label = QLabel("自动检测系统中的 HFS/HFS+/HFSX 分区")
        autodetect_layout.addWidget(autodetect_label)
        autodetect_layout.addStretch()
        device_layout.addLayout(autodetect_layout)
        
        # 分隔线
        line1 = QLabel()
        line1.setFrameShape(QLabel.Shape.HLine)
        line1.setFrameShadow(QLabel.Shadow.Sunken)
        device_layout.addWidget(line1)
        
        # 自动检测的设备
        self.auto_radio = QRadioButton("从检测到的设备中选择:")
        self.auto_radio.setChecked(True)
        device_layout.addWidget(self.auto_radio)
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(150)
        device_layout.addWidget(self.device_list)
        
        # 警告标签
        warning_label = QLabel("(混合 CD-ROM 同时包含 HFS/+/X 和 ISO 文件系统将无法工作)")
        warning_label.setStyleSheet("color: gray; font-style: italic;")
        device_layout.addWidget(warning_label)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新设备列表")
        refresh_button.clicked.connect(self._detect_devices)
        refresh_layout.addWidget(refresh_button)
        refresh_layout.addStretch()
        device_layout.addLayout(refresh_layout)
        
        # 分隔线
        line2 = QLabel()
        line2.setFrameShape(QLabel.Shape.HLine)
        line2.setFrameShadow(QLabel.Shadow.Sunken)
        device_layout.addWidget(line2)
        
        # 手动输入
        self.manual_radio = QRadioButton("指定设备名称:")
        device_layout.addWidget(self.manual_radio)
        
        manual_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("例如: \\\\.\\PhysicalDrive0 或 /dev/sda")
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
    
    def _autodetect_hfs(self):
        """自动检测 HFS/HFS+/HFSX 分区"""
        from src.core.partition import parse_partitions
        
        self.device_list.clear()
        self._devices = []
        
        # 检测所有设备
        all_devices = detect_devices()
        hfs_devices = []
        
        progress = QMessageBox(self)
        progress.setWindowTitle("自动检测")
        progress.setText("正在扫描设备...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        
        for device in all_devices:
            # 跳过分区，只扫描整盘
            if device.path[-1].isdigit():
                continue
            
            try:
                progress.setText(f"正在扫描: {device.name}")
                QApplication.processEvents()
                
                with open(device.path, 'rb') as f:
                    partition_type, partitions = parse_partitions(f)
                    
                    if partitions:
                        for p in partitions:
                            if p.is_hfs:
                                # 创建一个新的设备信息
                                hfs_path = device.path
                                # 计算分区偏移
                                offset_mb = p.start_offset / (1024 * 1024)
                                size_gb = p.size_bytes / (1024 * 1024 * 1024)
                                
                                name = f"{device.name} - {p.name} ({size_gb:.2f} GB, 偏移: {offset_mb:.1f} MB)"
                                hfs_info = DeviceInfo(
                                    device.path,
                                    name,
                                    p.size_bytes,
                                    device.model,
                                    device.is_usb
                                )
                                hfs_info.partition_offset = p.start_offset  # 保存分区偏移
                                hfs_devices.append(hfs_info)
            except Exception as e:
                # 忽略无法访问的设备
                pass
        
        progress.close()
        
        if not hfs_devices:
            QMessageBox.information(
                self, "自动检测",
                "未检测到 HFS/HFS+/HFSX 分区。\n\n"
                "可能的原因：\n"
                "1. 没有连接 HFS+ 格式的硬盘\n"
                "2. 需要管理员权限才能访问设备\n"
                "3. 分区表格式不支持"
            )
            return
        
        # 添加到列表
        self._devices = hfs_devices
        for device in hfs_devices:
            item = QListWidgetItem(str(device))
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.device_list.addItem(item)
        
        self.device_list.setCurrentRow(0)
        QMessageBox.information(
            self, "自动检测",
            f"检测到 {len(hfs_devices)} 个 HFS+ 分区"
        )
    
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
            # 保存分区偏移（如果有）
            if hasattr(device, 'partition_offset'):
                self._partition_offset = device.partition_offset
            else:
                self._partition_offset = 0
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
            self._partition_offset = 0
        
        self.accept()
    
    def get_selected_device(self) -> Optional[str]:
        """获取选中的设备路径"""
        return self._selected_device
    
    def get_partition_offset(self) -> int:
        """获取分区偏移"""
        return getattr(self, '_partition_offset', 0)


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
