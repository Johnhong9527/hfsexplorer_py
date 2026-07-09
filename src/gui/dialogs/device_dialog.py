"""
设备选择对话框

从 Java 版本 HFSExplorer 提炼的功能，支持：
- Windows 设备检测 (Harddisk0\\Partition0 格式)
- 自动检测 HFS/HFS+/HFSX 文件系统
- 嵌套分区系统支持
"""

import os
import platform
import struct
from typing import Optional, List, Tuple, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QLineEdit, QGroupBox,
    QButtonGroup, QMessageBox, QListWidget, QListWidgetItem,
    QApplication
)
from PyQt6.QtCore import Qt

from src.core.partition import parse_partitions, PartitionType


class DeviceInfo:
    """设备信息"""
    
    def __init__(self, path: str, name: str, size: int = 0, model: str = "", 
                 is_usb: bool = False, partition_offset: int = 0,
                 fs_type: str = ""):
        self.path = path
        self.name = name
        self.size = size
        self.model = model
        self.is_usb = is_usb
        self.partition_offset = partition_offset
        self.fs_type = fs_type  # HFS, HFS+, HFSX
    
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
        fs_marker = f" [{self.fs_type}]" if self.fs_type else ""
        if self.model:
            return f"{self.name}{usb_marker}{fs_marker} - {self.model} ({self.size_str})"
        return f"{self.name}{usb_marker}{fs_marker} ({self.size_str})"


def detect_filesystem_type(data: bytes, offset: int = 0) -> str:
    """
    检测文件系统类型
    
    Args:
        data: 扇区数据
        offset: 偏移量
    
    Returns:
        文件系统类型: "HFS", "HFS+", "HFSX", 或 ""
    """
    if len(data) < offset + 2:
        return ""
    
    signature = struct.unpack_from('>H', data, offset)[0]
    
    if signature == 0x4244:  # 'BD'
        return "HFS"
    elif signature == 0x482B:  # 'H+'
        return "HFS+"
    elif signature == 0x4858:  # 'HX'
        return "HFSX"
    
    return ""


def detect_devices() -> List[DeviceInfo]:
    """
    检测系统中的硬盘设备
    
    Returns:
        设备信息列表
    """
    devices = []
    system = platform.system()
    
    if system == "Windows":
        # Windows: 检测 Harddisk0\\Partition0, Harddisk0\Partition1, ...
        # 这是 Java 版本的检测方式
        devices.extend(_detect_windows_devices())
    elif system == "Linux":
        # Linux: 检查 /dev/sd*, /dev/nvme*, /dev/vd* 等
        devices.extend(_detect_linux_devices())
    elif system == "Darwin":
        # macOS: 检查 /dev/disk0, 1, 2...
        devices.extend(_detect_macos_devices())
    
    return devices


def _detect_windows_devices() -> List[DeviceInfo]:
    """
    检测 Windows 设备
    
    使用 Java 版本的检测方式：Harddisk0\\Partition0, Harddisk1\Partition0, ...
    """
    devices = []
    
    # 检测硬盘和分区 (最多20个硬盘，每个最多20个分区)
    for i in range(20):
        any_found = False
        for j in range(20):
            device_name = f"Harddisk{i}\\Partition{j}"
            device_path = f"\\\\.\\PhysicalDrive{i}" if j == 0 else f"\\\\.\\{device_name}"
            
            # 尝试打开设备
            try:
                with open(device_path, 'rb') as f:
                    # 读取第一个扇区
                    data = f.read(512)
                    if len(data) >= 512:
                        any_found = True
                        
                        # 检测是否是 HFS+ 分区
                        fs_type = detect_filesystem_type(data)
                        
                        if j == 0:
                            # 整盘
                            devices.append(DeviceInfo(
                                device_path,
                                device_name,
                                0,
                                "",
                                False,
                                0,
                                fs_type
                            ))
                        else:
                            # 分区
                            devices.append(DeviceInfo(
                                device_path,
                                device_name,
                                0,
                                "",
                                False,
                                0,
                                fs_type
                            ))
            except (PermissionError, OSError, Exception):
                # 无法访问，跳过
                if j == 0 and not any_found:
                    break
                if j >= 1:
                    break
        
        if not any_found and i >= 5:
            break
    
    # 也尝试使用 wmic 获取更多信息
    try:
        import subprocess
        result = subprocess.run(
            ['wmic', 'diskdrive', 'get', 'DeviceID,Size,Model,InterfaceType'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]
            for line in lines:
                if not line.strip():
                    continue
                
                # 解析设备信息
                device_id = None
                model = ''
                size = 0
                is_usb = False
                
                parts = line.split()
                for j, part in enumerate(parts):
                    if 'PhysicalDrive' in part:
                        device_id = part
                    elif part.isdigit() and int(part) > 1000000:
                        size = int(part)
                
                if device_id:
                    # 检查是否是 USB
                    is_usb = 'USB' in line.upper() or 'EXTERNAL' in line.upper()
                    
                    # 获取型号
                    model_parts = [p for p in parts if not p.isdigit() and 'PhysicalDrive' not in p]
                    model = ' '.join(model_parts) if model_parts else ''
                    
                    # 更新设备信息
                    for dev in devices:
                        if dev.path == device_id or dev.path.endswith(device_id.split('\\')[-1]):
                            dev.size = size
                            dev.model = model
                            dev.is_usb = is_usb
    except Exception:
        pass
    
    return devices


def _detect_linux_devices() -> List[DeviceInfo]:
    """检测 Linux 设备"""
    devices = []
    
    # SCSI/SATA/USB 设备及其分区
    for i in range(26):
        dev_base = f"sd{chr(97 + i)}"
        dev_path = f"/dev/{dev_base}"
        if os.path.exists(dev_path):
            # 检测整盘
            size = _get_device_size_linux(dev_path)
            model = _get_device_model_linux(dev_path)
            is_usb = _is_removable_device(dev_path)
            
            # 检测文件系统类型
            fs_type = ""
            try:
                with open(dev_path, 'rb') as f:
                    data = f.read(512)
                    fs_type = detect_filesystem_type(data)
            except:
                pass
            
            devices.append(DeviceInfo(dev_path, dev_base, size, model, is_usb, 0, fs_type))
            
            # 检测分区
            for j in range(1, 20):
                part_path = f"/dev/{dev_base}{j}"
                if os.path.exists(part_path):
                    part_size = _get_device_size_linux(part_path)
                    part_fs = ""
                    try:
                        with open(part_path, 'rb') as f:
                            data = f.read(512)
                            part_fs = detect_filesystem_type(data)
                    except:
                        pass
                    
                    devices.append(DeviceInfo(
                        part_path, f"{dev_base}{j}", part_size, model, is_usb, 0, part_fs
                    ))
    
    # NVMe 设备及其分区
    for i in range(10):
        for j in range(10):
            dev_base = f"nvme{i}n{j}"
            dev_path = f"/dev/{dev_base}"
            if os.path.exists(dev_path):
                size = _get_device_size_linux(dev_path)
                model = _get_device_model_linux(dev_path)
                is_usb = False  # NVMe 通常不是 USB
                
                fs_type = ""
                try:
                    with open(dev_path, 'rb') as f:
                        data = f.read(512)
                        fs_type = detect_filesystem_type(data)
                except:
                    pass
                
                devices.append(DeviceInfo(dev_path, dev_base, size, model, is_usb, 0, fs_type))
                
                # 检测分区
                for k in range(1, 20):
                    part_path = f"/dev/{dev_base}p{k}"
                    if os.path.exists(part_path):
                        part_size = _get_device_size_linux(part_path)
                        part_fs = ""
                        try:
                            with open(part_path, 'rb') as f:
                                data = f.read(512)
                                part_fs = detect_filesystem_type(data)
                        except:
                            pass
                        
                        devices.append(DeviceInfo(
                            part_path, f"{dev_base}p{k}", part_size, model, False, 0, part_fs
                        ))
    
    return devices


def _detect_macos_devices() -> List[DeviceInfo]:
    """检测 macOS 设备"""
    devices = []
    
    for i in range(20):
        dev_path = f"/dev/disk{i}"
        if os.path.exists(dev_path):
            name = f"disk{i}"
            size = _get_device_size_linux(dev_path)
            
            fs_type = ""
            try:
                with open(dev_path, 'rb') as f:
                    data = f.read(512)
                    fs_type = detect_filesystem_type(data)
            except:
                pass
            
            devices.append(DeviceInfo(dev_path, name, size, "", False, 0, fs_type))
    
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
    
    从 Java 版本 HFSExplorer 提炼的功能。
    
    Usage:
        dialog = DeviceSelectionDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            device_path = dialog.get_selected_device()
            partition_offset = dialog.get_partition_offset()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载文件系统从设备")
        self.setMinimumWidth(550)
        
        self._selected_device: Optional[str] = None
        self._partition_offset: int = 0
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
        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(30)
        device_layout.addWidget(self.device_combo)
        
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
        
        # 示例标签
        system = platform.system()
        if system == "Windows":
            example = "示例: \\\\.\\GLOBALROOT\\Device\\Harddisk0\\Partition1"
        else:
            example = "示例: /dev/sda1"
        example_label = QLabel(example)
        example_label.setStyleSheet("color: gray;")
        device_layout.addWidget(example_label)
        
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
        self.device_combo.clear()
        self._devices = detect_devices()
        
        for device in self._devices:
            self.device_combo.addItem(str(device), device)
        
        if self._devices:
            self.device_combo.setCurrentIndex(0)
    
    def _on_radio_changed(self, checked: bool):
        """单选按钮状态改变"""
        self.device_combo.setEnabled(checked)
        self.path_edit.setEnabled(not checked)
    
    def _autodetect_hfs(self):
        """自动检测 HFS/HFS+/HFSX 分区"""
        self.device_combo.clear()
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
            if device.path[-1].isdigit() and 'Partition' not in device.name:
                continue
            
            try:
                progress.setText(f"正在扫描: {device.name}")
                QApplication.processEvents()
                
                with open(device.path, 'rb') as f:
                    partition_type, partitions = parse_partitions(f)
                    
                    if partitions:
                        for p in partitions:
                            if p.is_hfs:
                                # 检测文件系统类型
                                f.seek(p.start_offset)
                                data = f.read(512)
                                fs_type = detect_filesystem_type(data)
                                
                                if fs_type:
                                    size_gb = p.size_bytes / (1024 * 1024 * 1024)
                                    name = f"{device.name} - {p.name} ({fs_type}, {size_gb:.2f} GB)"
                                    
                                    hfs_info = DeviceInfo(
                                        device.path,
                                        name,
                                        p.size_bytes,
                                        device.model,
                                        device.is_usb,
                                        p.start_offset,
                                        fs_type
                                    )
                                    hfs_devices.append(hfs_info)
                    
                    # 也检查整个设备是否是 HFS+
                    if not partitions:
                        f.seek(0)
                        data = f.read(512)
                        fs_type = detect_filesystem_type(data)
                        if fs_type:
                            hfs_info = DeviceInfo(
                                device.path,
                                f"{device.name} ({fs_type})",
                                device.size,
                                device.model,
                                device.is_usb,
                                0,
                                fs_type
                            )
                            hfs_devices.append(hfs_info)
            except Exception as e:
                # 忽略无法访问的设备
                pass
        
        progress.close()
        
        if not hfs_devices:
            QMessageBox.information(
                self, "自动检测",
                "未检测到 HFS/HFS+/HFSX 文件系统。\n\n"
                "可能的原因：\n"
                "1. 没有连接 HFS+ 格式的硬盘\n"
                "2. 需要管理员权限才能访问设备\n"
                "3. 分区表格式不支持"
            )
            return
        
        # 添加到列表
        self._devices = hfs_devices
        for device in hfs_devices:
            self.device_combo.addItem(str(device), device)
        
        self.device_combo.setCurrentIndex(0)
        QMessageBox.information(
            self, "自动检测",
            f"自动检测完成！找到 {len(hfs_devices)} 个 HFS+ 文件系统。\n"
            "请选择要加载的文件系统："
        )
    
    def _on_load(self):
        """加载按钮点击"""
        if self.auto_radio.isChecked():
            # 从列表中选择
            current_index = self.device_combo.currentIndex()
            if current_index < 0:
                QMessageBox.warning(self, "警告", "请选择一个设备")
                return
            
            device = self._devices[current_index]
            self._selected_device = device.path
            self._partition_offset = device.partition_offset
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
        return self._partition_offset


def show_device_selection_dialog(parent=None) -> Optional[Tuple[str, int]]:
    """
    显示设备选择对话框的便捷函数
    
    Args:
        parent: 父窗口
    
    Returns:
        (设备路径, 分区偏移) 元组，如果取消则返回 None
    """
    dialog = DeviceSelectionDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_selected_device(), dialog.get_partition_offset()
    return None
