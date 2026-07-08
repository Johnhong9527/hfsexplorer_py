#!/usr/bin/env python3
"""
HFSExplorer 主窗口

实现类似 macOS Finder 的文件浏览器界面。
"""

import sys
import os
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QSplitter, QTreeWidget, QTableWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QHeaderView,
    QTreeWidgetItem, QTableWidgetItem, QApplication,
    QStyle, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QIcon, QPixmap, QKeySequence

from src.core.hfs import (
    read_volume_header,
    is_hfs_plus_volume,
    HFSPlusVolumeHeader,
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
)


class FileLoadThread(QThread):
    """文件加载线程"""
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        try:
            # 读取卷头
            header = read_volume_header(self.file_path)
            
            result = {
                'path': self.file_path,
                'header': header,
                'signature': 'HFS+' if header.is_hfs_plus else 'HFSX',
                'block_size': header.block_size,
                'total_blocks': header.total_blocks,
                'free_blocks': header.free_blocks,
                'file_count': header.file_count,
                'folder_count': header.folder_count,
            }
            
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """HFSExplorer 主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HFSExplorer")
        self.setMinimumSize(1024, 768)
        
        # 当前打开的文件系统
        self.current_path: Optional[str] = None
        self.current_header: Optional[HFSPlusVolumeHeader] = None
        self.current_catalog: Optional[CatalogBTree] = None
        
        # 初始化 UI
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central_widget()
        
        # 加载线程
        self.load_thread: Optional[FileLoadThread] = None
    
    def _setup_menus(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        open_action = QAction("打开(&O)...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        
        info_action = QAction("卷信息(&I)...", self)
        info_action.setShortcut("Ctrl+I")
        info_action.triggered.connect(self._show_volume_info)
        tools_menu.addAction(info_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # 打开按钮
        open_action = QAction("打开", self)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # 向上按钮
        up_action = QAction("向上", self)
        up_action.triggered.connect(self._go_up)
        toolbar.addAction(up_action)
        
        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh)
        toolbar.addAction(refresh_action)
    
    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusBar().showMessage("就绪")
        
        # 选择信息标签
        self.selection_label = QLabel("选择: 0 个对象")
        self.statusBar().addPermanentWidget(self.selection_label)
    
    def _setup_central_widget(self):
        """设置中央部件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 地址栏
        address_layout = QHBoxLayout()
        address_layout.setContentsMargins(5, 5, 5, 5)
        
        address_label = QLabel("路径:")
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("选择文件或设备...")
        self.address_edit.returnPressed.connect(self._navigate_to)
        
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
        self.tree_widget.setMinimumWidth(200)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        
        # 文件表格
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改时间"])
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.itemSelectionChanged.connect(self._on_selection_changed)
        
        splitter.addWidget(self.tree_widget)
        splitter.addWidget(self.table_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
    
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
    
    def _load_filesystem(self, path: str):
        """加载文件系统"""
        self.statusBar().showMessage(f"正在加载: {path}")
        self.address_edit.setText(path)
        
        # 禁用 UI
        self.setEnabled(False)
        
        # 启动加载线程
        self.load_thread = FileLoadThread(path)
        self.load_thread.finished.connect(self._on_load_finished)
        self.load_thread.error.connect(self._on_load_error)
        self.load_thread.start()
    
    def _on_load_finished(self, result: dict):
        """加载完成"""
        self.current_path = result['path']
        self.current_header = result['header']
        
        # 更新窗口标题
        self.setWindowTitle(f"HFSExplorer - {os.path.basename(self.current_path)}")
        
        # 更新状态栏
        self.statusBar().showMessage(
            f"已加载: {result['signature']} 卷, "
            f"块大小: {result['block_size']:,}, "
            f"文件: {result['file_count']:,}, "
            f"文件夹: {result['folder_count']:,}"
        )
        
        # 加载目录树
        self._load_directory_tree()
        
        # 启用 UI
        self.setEnabled(True)
    
    def _on_load_error(self, error: str):
        """加载错误"""
        self.statusBar().showMessage(f"加载失败: {error}")
        QMessageBox.critical(self, "错误", f"无法加载文件:\n{error}")
        self.setEnabled(True)
    
    def _load_directory_tree(self):
        """加载目录树"""
        self.tree_widget.clear()
        
        if self.current_header is None:
            return
        
        # 创建根节点
        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, "根目录")
        root_item.setData(0, Qt.ItemDataRole.UserRole, 2)  # CNID 2 = 根目录
        
        # 添加占位子节点（用于懒加载）
        placeholder = QTreeWidgetItem(root_item)
        placeholder.setText(0, "加载中...")
        
        self.tree_widget.expandItem(root_item)
    
    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """树项目被点击"""
        cnid = item.data(0, Qt.ItemDataRole.UserRole)
        if cnid:
            self._load_folder_contents(cnid)
    
    def _load_folder_contents(self, parent_id: int):
        """加载文件夹内容"""
        # 清空表格
        self.table_widget.setRowCount(0)
        
        # 注意：这里需要实际的 Catalog B-tree 来获取内容
        # 目前只是显示占位数据
        
        # 示例数据
        sample_data = [
            {'type': 'folder', 'name': 'Applications', 'size': '-', 'modified': '2024-01-01'},
            {'type': 'folder', 'name': 'System', 'size': '-', 'modified': '2024-01-01'},
            {'type': 'folder', 'name': 'Users', 'size': '-', 'modified': '2024-01-01'},
            {'type': 'file', 'name': 'README.txt', 'size': '1,024', 'modified': '2024-01-01'},
        ]
        
        self.table_widget.setRowCount(len(sample_data))
        
        for i, item_data in enumerate(sample_data):
            # 名称
            name_item = QTableWidgetItem(item_data['name'])
            if item_data['type'] == 'folder':
                name_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            else:
                name_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            self.table_widget.setItem(i, 0, name_item)
            
            # 大小
            size_item = QTableWidgetItem(item_data['size'])
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_widget.setItem(i, 1, size_item)
            
            # 类型
            type_item = QTableWidgetItem(item_data['type'].capitalize())
            self.table_widget.setItem(i, 2, type_item)
            
            # 修改时间
            modified_item = QTableWidgetItem(item_data['modified'])
            self.table_widget.setItem(i, 3, modified_item)
    
    def _on_selection_changed(self):
        """选择改变"""
        selected = self.table_widget.selectedItems()
        if selected:
            count = len(set(item.row() for item in selected))
            self.selection_label.setText(f"选择: {count} 个对象")
        else:
            self.selection_label.setText("选择: 0 个对象")
    
    def _navigate_to(self):
        """导航到地址栏中的路径"""
        path = self.address_edit.text()
        if path:
            self._load_filesystem(path)
    
    def _go_up(self):
        """向上导航"""
        # TODO: 实现向上导航
        pass
    
    def _refresh(self):
        """刷新当前视图"""
        if self.current_path:
            self._load_filesystem(self.current_path)
    
    def _show_volume_info(self):
        """显示卷信息"""
        if self.current_header is None:
            QMessageBox.information(self, "卷信息", "未打开任何卷")
            return
        
        header = self.current_header
        info = f"""
卷信息:
--------
签名: {'HFS+' if header.is_hfs_plus else 'HFSX'}
版本: {header.version}
块大小: {header.block_size:,} 字节
总块数: {header.total_blocks:,}
空闲块: {header.free_blocks:,}
卷大小: {header.volume_size:,} 字节 ({header.volume_size / (1024**3):.2f} GB)
空闲空间: {header.free_space:,} 字节 ({header.free_space / (1024**3):.2f} GB)
文件数: {header.file_count:,}
文件夹数: {header.folder_count:,}
日志: {'是' if header.is_journaled else '否'}
锁定: {'是' if header.is_locked else '否'}
"""
        QMessageBox.information(self, "卷信息", info)
    
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


def main():
    """主入口点"""
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