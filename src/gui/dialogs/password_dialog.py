"""
HFS+ 密码输入对话框

用于输入密码以解锁加密卷。
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QCheckBox, QGroupBox,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class PasswordDialog(QDialog):
    """
    密码输入对话框
    
    用于输入密码以解锁 FileVault 2 加密卷。
    
    Usage:
        dialog = PasswordDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            use_recovery_key = dialog.use_recovery_key
    """
    
    def __init__(self, parent=None, volume_name: str = ""):
        """
        初始化密码对话框
        
        Args:
            parent: 父窗口
            volume_name: 卷名称
        """
        super().__init__(parent)
        self.volume_name = volume_name
        self._use_recovery_key = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("解锁加密卷")
        self.setMinimumWidth(400)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("此卷已加密，需要密码才能访问。")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # 卷信息
        if self.volume_name:
            info_label = QLabel(f"卷: {self.volume_name}")
            info_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(info_label)
        
        layout.addSpacing(10)
        
        # 解锁方式选择
        unlock_group = QGroupBox("解锁方式")
        unlock_layout = QVBoxLayout(unlock_group)
        
        self.password_radio = QRadioButton("使用密码")
        self.password_radio.setChecked(True)
        self.password_radio.toggled.connect(self._on_unlock_method_changed)
        
        self.recovery_radio = QRadioButton("使用恢复密钥")
        self.recovery_radio.toggled.connect(self._on_unlock_method_changed)
        
        unlock_layout.addWidget(self.password_radio)
        unlock_layout.addWidget(self.recovery_radio)
        
        layout.addWidget(unlock_group)
        
        # 密码输入
        self.password_group = QGroupBox("密码")
        password_layout = QVBoxLayout(self.password_group)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("输入密码...")
        self.password_edit.returnPressed.connect(self._on_ok)
        
        password_layout.addWidget(self.password_edit)
        
        # 显示密码复选框
        self.show_password_check = QCheckBox("显示密码")
        self.show_password_check.toggled.connect(self._on_show_password_toggled)
        password_layout.addWidget(self.show_password_check)
        
        layout.addWidget(self.password_group)
        
        # 恢复密钥输入
        self.recovery_group = QGroupBox("恢复密钥")
        recovery_layout = QVBoxLayout(self.recovery_group)
        
        recovery_label = QLabel("输入 24 位恢复密钥:")
        recovery_layout.addWidget(recovery_label)
        
        self.recovery_edit = QLineEdit()
        self.recovery_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.recovery_edit.returnPressed.connect(self._on_ok)
        
        recovery_layout.addWidget(self.recovery_edit)
        
        layout.addWidget(self.recovery_group)
        
        # 初始状态
        self.recovery_group.setVisible(False)
        
        layout.addSpacing(10)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("解锁")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self._on_ok)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _on_unlock_method_changed(self):
        """解锁方式改变"""
        self._use_recovery_key = self.recovery_radio.isChecked()
        self.password_group.setVisible(not self._use_recovery_key)
        self.recovery_group.setVisible(self._use_recovery_key)
    
    def _on_show_password_toggled(self, checked: bool):
        """显示密码切换"""
        if checked:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    def _on_ok(self):
        """确定按钮"""
        if self._use_recovery_key:
            recovery_key = self.recovery_edit.text().strip()
            if not recovery_key:
                QMessageBox.warning(self, "错误", "请输入恢复密钥。")
                return
            
            # 验证恢复密钥格式
            if len(recovery_key) != 28:  # 24 位 + 4 个连字符
                QMessageBox.warning(self, "错误", "恢复密钥格式不正确。")
                return
        else:
            password = self.password_edit.text()
            if not password:
                QMessageBox.warning(self, "错误", "请输入密码。")
                return
        
        self.accept()
    
    def get_password(self) -> str:
        """
        获取密码
        
        Returns:
            密码或恢复密钥
        """
        if self._use_recovery_key:
            return self.recovery_edit.text().strip()
        else:
            return self.password_edit.text()
    
    @property
    def use_recovery_key(self) -> bool:
        """是否使用恢复密钥"""
        return self._use_recovery_key
    
    @staticmethod
    def get_password(parent=None, volume_name: str = "") -> Optional[str]:
        """
        获取密码的便捷方法
        
        Args:
            parent: 父窗口
            volume_name: 卷名称
        
        Returns:
            密码，如果取消则返回 None
        """
        dialog = PasswordDialog(parent, volume_name)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_password()
        return None