#!/usr/bin/env python3
"""
HFSExplorer 主窗口
"""

from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QSplitter, QTreeWidget, QTableWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap

class MainWindow(QMainWindow):
    """HFSExplorer 主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HFSExplorer")
        self.setMinimumSize(1024, 768)
        
        # 初始化 UI
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central_widget()
        
        # 当前打开的文件系统
        self.current_fs = None
    
    def _setup_menus(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        open_action = QAction("打开(&O)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)
        
        # 打开按钮
        open_action = QAction("打开", self)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)
        
        # 提取按钮
        extract_action = QAction("提取", self)
        extract_action.triggered.connect(self._extract_files)
        toolbar.addAction(extract_action)
    
    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusBar().showMessage("就绪")
    
    def _setup_central_widget(self):
        """设置中央部件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 地址栏
        address_layout = QHBoxLayout()
        address_label = QLabel("路径:")
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("选择文件或设备...")
        go_button = QPushButton("转到")
        go_button.clicked.connect(self._navigate_to)
        
        address_layout.addWidget(address_label)
        address_layout.addWidget(self.address_edit)
        address_layout.addWidget(go_button)
        
        layout.addLayout(address_layout)
        
        # 分割窗口：树视图 + 表格视图
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 目录树
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("目录结构")
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        
        # 文件表格
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改时间"])
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        
        splitter.addWidget(self.tree_widget)
        splitter.addWidget(self.table_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # 状态信息
        self.selection_label = QLabel("选择: 0 个对象")
        layout.addWidget(self.selection_label)
    
    def _open_file(self):
        """打开文件或设备"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 HFS 磁盘镜像",
            "",
            "磁盘镜像 (*.dmg *.img *.iso *.raw *.bin);;所有文件 (*)"
        )
        
        if file_path:
            self._load_filesystem(file_path)
    
    def _load_filesystem(self, path):
        """加载文件系统"""
        self.statusBar().showMessage(f"正在加载: {path}")
        # TODO: 实现文件系统加载
        self.address_edit.setText(path)
        self.statusBar().showMessage(f"已加载: {path}")
    
    def _navigate_to(self):
        """导航到地址栏中的路径"""
        path = self.address_edit.text()
        if path:
            self._load_filesystem(path)
    
    def _on_tree_item_clicked(self, item, column):
        """树项目被点击"""
        # TODO: 更新表格视图
        pass
    
    def _extract_files(self):
        """提取选中的文件"""
        # TODO: 实现文件提取
        QMessageBox.information(self, "提取", "文件提取功能待实现")
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 HFSExplorer",
            "HFSExplorer 复刻版本\n\n"
            "一个用于浏览和提取 HFS/HFS+/HFSX 文件系统内容的工具。\n\n"
            "本软件是原 HFSExplorer 的复刻版本，去除了 Java 依赖。\n"
            "原作者: Erik Larsson (Catacombae Software)"
        )