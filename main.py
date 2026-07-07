#!/usr/bin/env python3
"""
HFSExplorer - HFS/HFS+/HFSX 文件系统浏览器
复刻版本，去除 Java 依赖
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.main_window import MainWindow

def main():
    # 设置高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("HFSExplorer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("HFSExplorer Rewrite")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
