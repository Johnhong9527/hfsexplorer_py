#!/usr/bin/env python3
"""
HFSExplorer 主窗口

实现类似 macOS Finder 的文件浏览器界面。
"""

import sys
import os
import struct
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QSplitter, QTreeWidget, QTableWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QHeaderView,
    QTreeWidgetItem, QTableWidgetItem, QApplication,
    QStyle, QAbstractItemView, QProgressDialog,
    QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QAction, QIcon, QPixmap, QKeySequence, QCursor

from src.core.hfs import (
    read_volume_header,
    is_hfs_plus_volume,
    HFSPlusVolumeHeader,
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFS_EPOCH_OFFSET,
    BTreeFile,
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
            
            # 尝试打开 Catalog B-tree
            catalog = None
            try:
                with open(self.file_path, 'rb') as f:
                    # Catalog 文件在卷头的 catalog_file 字段中
                    # 简化实现：假设 Catalog 从卷的某个位置开始
                    # 实际需要解析 extent 来找到 Catalog 的位置
                    pass
            except Exception:
                pass
            
            result = {
                'path': self.file_path,
                'header': header,
                'catalog': catalog,
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


class FolderLoadThread(QThread):
    """文件夹内容加载线程"""
    
    finished = pyqtSignal(int, list)
    error = pyqtSignal(str)
    
    def __init__(self, file_path: str, parent_id: int, 
                 catalog_offset: int = 0, node_size: int = 4096):
        super().__init__()
        self.file_path = file_path
        self.parent_id = parent_id
        self.catalog_offset = catalog_offset
        self.node_size = node_size
    
    def run(self):
        try:
            # 打开文件并读取 Catalog B-tree
            with open(self.file_path, 'rb') as f:
                catalog = CatalogBTree(f, self.catalog_offset, self.node_size)
                contents = catalog.list_folder_contents(self.parent_id)
                self.finished.emit(self.parent_id, contents)
        except Exception as e:
            self.error.emit(str(e))


def hfs_date_to_string(timestamp: int) -> str:
    """将 HFS 日期转换为字符串"""
    if timestamp == 0:
        return "-"
    try:
        unix_timestamp = timestamp - HFS_EPOCH_OFFSET
        dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "-"


def format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


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
        self.catalog_offset: int = 0
        self.node_size: int = 4096
        
        # 目录缓存 {parent_id: [children]}
        self.folder_cache: Dict[int, List[dict]] = {}
        
        # 当前查看的文件夹 ID
        self.current_folder_id: int = 2  # 根目录
        
        # 初始化 UI
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central_widget()
        
        # 加载线程
        self.load_thread: Optional[FileLoadThread] = None
        self.folder_thread: Optional[FolderLoadThread] = None
    
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
        
        extract_action = QAction("提取(&E)...", self)
        extract_action.setShortcut("Ctrl+E")
        extract_action.triggered.connect(self._extract_selected)
        file_menu.addAction(extract_action)
        
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
        self.up_action = QAction("向上", self)
        self.up_action.triggered.connect(self._go_up)
        self.up_action.setEnabled(False)
        toolbar.addAction(self.up_action)
        
        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # 提取按钮
        extract_action = QAction("提取", self)
        extract_action.triggered.connect(self._extract_selected)
        toolbar.addAction(extract_action)
    
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
        self.tree_widget.itemExpanded.connect(self._on_tree_item_expanded)
        
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
        self.table_widget.doubleClicked.connect(self._on_table_double_clicked)
        
        # 右键菜单
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)
        
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
        
        # 清空缓存
        self.folder_cache.clear()
        
        # 启动加载线程
        self.load_thread = FileLoadThread(path)
        self.load_thread.finished.connect(self._on_load_finished)
        self.load_thread.error.connect(self._on_load_error)
        self.load_thread.start()
    
    def _on_load_finished(self, result: dict):
        """加载完成"""
        self.current_path = result['path']
        self.current_header = result['header']
        self.node_size = self.current_header.block_size
        
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
        placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
        
        self.tree_widget.expandItem(root_item)
        
        # 加载根目录内容
        self._load_folder_contents(2)
    
    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """树项目被展开"""
        # 检查是否需要加载子项
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) is None:
                # 移除占位符
                item.removeChild(child)
                
                # 加载实际内容
                parent_id = item.data(0, Qt.ItemDataRole.UserRole)
                if parent_id:
                    self._load_subfolders(item, parent_id)
                break
    
    def _load_subfolders(self, parent_item: QTreeWidgetItem, parent_id: int):
        """加载子文件夹到树"""
        if parent_id not in self.folder_cache:
            # 异步加载
            self._load_folder_async(parent_id)
            return
        
        # 从缓存加载
        contents = self.folder_cache[parent_id]
        for item_data in contents:
            if item_data['type'] == 'folder':
                child = QTreeWidgetItem(parent_item)
                child.setText(0, item_data['name'])
                child.setData(0, Qt.ItemDataRole.UserRole, item_data['id'])
                
                # 添加占位子节点
                placeholder = QTreeWidgetItem(child)
                placeholder.setText(0, "加载中...")
                placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
    
    def _load_folder_async(self, parent_id: int):
        """异步加载文件夹内容"""
        if self.current_path is None:
            return
        
        self.folder_thread = FolderLoadThread(
            self.current_path, parent_id, self.catalog_offset, self.node_size
        )
        self.folder_thread.finished.connect(self._on_folder_loaded)
        self.folder_thread.error.connect(self._on_folder_error)
        self.folder_thread.start()
    
    def _on_folder_loaded(self, parent_id: int, contents: list):
        """文件夹加载完成"""
        # 缓存结果
        self.folder_cache[parent_id] = contents
        
        # 如果是当前文件夹，更新表格
        if parent_id == self.current_folder_id:
            self._update_table(contents)
        
        # 更新树视图
        self._update_tree_for_folder(parent_id)
    
    def _on_folder_error(self, error: str):
        """文件夹加载错误"""
        self.statusBar().showMessage(f"加载文件夹失败: {error}")
    
    def _update_tree_for_folder(self, parent_id: int):
        """更新树视图中指定文件夹的子项"""
        # 查找对应的树项
        def find_item(parent_item, target_id):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) == target_id:
                    return child
                result = find_item(child, target_id)
                if result:
                    return result
            return None
        
        root = self.tree_widget.invisibleRootItem()
        item = find_item(root, parent_id)
        
        if item and parent_id in self.folder_cache:
            # 移除占位符
            while item.childCount() > 0:
                item.removeChild(item.child(0))
            
            # 添加实际子项
            contents = self.folder_cache[parent_id]
            for item_data in contents:
                if item_data['type'] == 'folder':
                    child = QTreeWidgetItem(item)
                    child.setText(0, item_data['name'])
                    child.setData(0, Qt.ItemDataRole.UserRole, item_data['id'])
                    
                    # 添加占位子节点
                    placeholder = QTreeWidgetItem(child)
                    placeholder.setText(0, "加载中...")
                    placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
    
    def _load_folder_contents(self, parent_id: int):
        """加载文件夹内容到表格"""
        self.current_folder_id = parent_id
        
        # 检查缓存
        if parent_id in self.folder_cache:
            self._update_table(self.folder_cache[parent_id])
        else:
            # 异步加载
            self._load_folder_async(parent_id)
    
    def _update_table(self, contents: list):
        """更新表格内容"""
        self.table_widget.setRowCount(0)
        
        # 分离文件夹和文件
        folders = [item for item in contents if item['type'] == 'folder']
        files = [item for item in contents if item['type'] == 'file']
        
        # 排序
        folders.sort(key=lambda x: x['name'].lower())
        files.sort(key=lambda x: x['name'].lower())
        
        # 合并
        sorted_items = folders + files
        
        self.table_widget.setRowCount(len(sorted_items))
        
        for i, item_data in enumerate(sorted_items):
            # 名称
            name_item = QTableWidgetItem(item_data['name'])
            if item_data['type'] == 'folder':
                name_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            else:
                name_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            name_item.setData(Qt.ItemDataRole.UserRole, item_data)
            self.table_widget.setItem(i, 0, name_item)
            
            # 大小
            if item_data['type'] == 'file':
                size_str = format_size(item_data.get('size', 0))
            else:
                size_str = "-"
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_widget.setItem(i, 1, size_item)
            
            # 类型
            type_str = "文件夹" if item_data['type'] == 'folder' else "文件"
            type_item = QTableWidgetItem(type_str)
            self.table_widget.setItem(i, 2, type_item)
            
            # 修改时间
            mod_date = item_data.get('mod_date', 0)
            modified_item = QTableWidgetItem(hfs_date_to_string(mod_date))
            self.table_widget.setItem(i, 3, modified_item)
    
    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """树项目被点击"""
        cnid = item.data(0, Qt.ItemDataRole.UserRole)
        if cnid:
            self._load_folder_contents(cnid)
            
            # 更新向上按钮状态
            self.up_action.setEnabled(cnid != 2)
    
    def _on_table_double_clicked(self, index):
        """表格项目被双击"""
        row = index.row()
        name_item = self.table_widget.item(row, 0)
        if name_item:
            item_data = name_item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data['type'] == 'folder':
                # 进入文件夹
                self._load_folder_contents(item_data['id'])
                self.up_action.setEnabled(True)
    
    def _on_selection_changed(self):
        """选择改变"""
        selected = self.table_widget.selectedItems()
        if selected:
            count = len(set(item.row() for item in selected))
            self.selection_label.setText(f"选择: {count} 个对象")
        else:
            self.selection_label.setText("选择: 0 个对象")
    
    def _show_context_menu(self, position):
        """显示右键菜单"""
        menu = QMenu(self)
        
        open_action = menu.addAction("打开")
        open_action.triggered.connect(self._open_selected)
        
        extract_action = menu.addAction("提取...")
        extract_action.triggered.connect(self._extract_selected)
        
        menu.addSeparator()
        
        info_action = menu.addAction("属性")
        info_action.triggered.connect(self._show_selected_info)
        
        menu.exec(QCursor.pos())
    
    def _open_selected(self):
        """打开选中的项目"""
        selected = self.table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            name_item = self.table_widget.item(row, 0)
            if name_item:
                item_data = name_item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data['type'] == 'folder':
                    self._load_folder_contents(item_data['id'])
                    self.up_action.setEnabled(True)
    
    def _extract_selected(self):
        """提取选中的文件"""
        selected = self.table_widget.selectedItems()
        if not selected:
            QMessageBox.information(self, "提取", "请先选择要提取的文件")
            return
        
        # 获取选中的文件
        rows = set()
        for item in selected:
            rows.add(item.row())
        
        files = []
        for row in rows:
            name_item = self.table_widget.item(row, 0)
            if name_item:
                item_data = name_item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data['type'] == 'file':
                    files.append(item_data)
        
        if not files:
            QMessageBox.information(self, "提取", "选中的项目中没有文件")
            return
        
        # 选择目标目录
        target_dir = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if not target_dir:
            return
        
        # TODO: 实现实际的文件提取
        QMessageBox.information(
            self, "提取", 
            f"将提取 {len(files)} 个文件到:\n{target_dir}\n\n功能待实现"
        )
    
    def _show_selected_info(self):
        """显示选中项目的信息"""
        selected = self.table_widget.selectedItems()
        if selected:
            row = selected[0].row()
            name_item = self.table_widget.item(row, 0)
            if name_item:
                item_data = name_item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    info = f"""
名称: {item_data['name']}
类型: {'文件夹' if item_data['type'] == 'folder' else '文件'}
"""
                    if item_data['type'] == 'file':
                        info += f"大小: {format_size(item_data.get('size', 0))}\n"
                    
                    info += f"修改时间: {hfs_date_to_string(item_data.get('mod_date', 0))}\n"
                    info += f"CNID: {item_data.get('id', '-')}\n"
                    
                    QMessageBox.information(self, "属性", info)
    
    def _go_up(self):
        """向上导航"""
        # TODO: 实现向上导航到父目录
        pass
    
    def _refresh(self):
        """刷新当前视图"""
        if self.current_path:
            self.folder_cache.clear()
            self._load_filesystem(self.current_path)
    
    def _navigate_to(self):
        """导航到地址栏中的路径"""
        path = self.address_edit.text()
        if path:
            self._load_filesystem(path)
    
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