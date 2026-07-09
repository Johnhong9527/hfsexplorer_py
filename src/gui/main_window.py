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
    QMenu, QInputDialog, QDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QMimeData, QUrl
from PyQt6.QtGui import QAction, QIcon, QPixmap, QKeySequence, QCursor, QDragEnterEvent, QDropEvent

from src.core.hfs import (
    read_volume_header,
    is_hfs_plus_volume,
    HFSPlusVolumeHeader,
    HFSPlusVolume,
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFS_EPOCH_OFFSET,
    BTreeFile,
    SearchEngine,
    SearchMatchType,
    SearchFilter,
    SearchResult,
)

from src.core.crypto import (
    EncryptedVolumeHeader,
    EncryptedVolume,
    Keybag,
    CryptoError,
)

from src.gui.panels.info_panels import FilePropertiesPanel
from src.gui.dialogs.password_dialog import PasswordDialog
from src.gui.views.view_manager import ViewManager, ViewMode


class FileLoadThread(QThread):
    """文件加载线程"""
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
    
    def run(self):
        try:
            # 使用 HFSPlusVolume 统一加载
            with HFSPlusVolume(self.file_path) as vol:
                header = vol.header
                info = vol.get_info()
                
                result = {
                    'path': self.file_path,
                    'header': header,
                    'volume': vol,
                    'signature': info['signature'],
                    'block_size': info['block_size'],
                    'total_blocks': info['total_blocks'],
                    'free_blocks': info['free_blocks'],
                    'file_count': info['file_count'],
                    'folder_count': info['folder_count'],
                }
                
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FolderLoadThread(QThread):
    """文件夹内容加载线程"""
    
    finished = pyqtSignal(int, list)
    error = pyqtSignal(str)
    
    def __init__(self, file_path: str, parent_id: int):
        super().__init__()
        self.file_path = file_path
        self.parent_id = parent_id
    
    def run(self):
        try:
            # 使用 HFSPlusVolume 加载文件夹内容
            with HFSPlusVolume(self.file_path) as vol:
                contents = vol.list_folder(self.parent_id)
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
        self.setWindowTitle("HFSExplorer (Alpha) - 只读 HFS+/HFSX")
        self.setMinimumSize(1024, 768)
        
        # 启用拖放
        self.setAcceptDrops(True)
        
        # 当前打开的文件系统
        self.current_path: Optional[str] = None
        self.current_header: Optional[HFSPlusVolumeHeader] = None
        self.current_catalog: Optional[CatalogBTree] = None
        self.catalog_offset: int = 0
        self.node_size: int = 4096
        
        # 目录导航历史 (用于向上导航)
        self.folder_history: List[int] = []  # 父目录 ID 栈
        
        # 加密卷支持
        self.encrypted_volume: Optional[EncryptedVolume] = None
        self.is_encrypted: bool = False
        
        # 搜索引擎
        self.search_engine: Optional[SearchEngine] = None
        
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
        
        search_action = QAction("搜索(&S)...", self)
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self._show_search_dialog)
        tools_menu.addAction(search_action)
        
        tools_menu.addSeparator()
        
        # 视图模式子菜单
        view_menu = tools_menu.addMenu("视图模式(&V)")
        
        icon_view_action = QAction("图标视图", self)
        icon_view_action.triggered.connect(lambda: self._set_view_mode(ViewMode.ICON))
        view_menu.addAction(icon_view_action)
        
        list_view_action = QAction("列表视图", self)
        list_view_action.triggered.connect(lambda: self._set_view_mode(ViewMode.LIST))
        view_menu.addAction(list_view_action)
        
        column_view_action = QAction("分栏视图", self)
        column_view_action.triggered.connect(lambda: self._set_view_mode(ViewMode.COLUMN))
        view_menu.addAction(column_view_action)
        
        gallery_view_action = QAction("画廊视图", self)
        gallery_view_action.triggered.connect(lambda: self._set_view_mode(ViewMode.GALLERY))
        view_menu.addAction(gallery_view_action)
        
        tools_menu.addSeparator()
        
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
        
        # 搜索按钮
        search_action = QAction("搜索", self)
        search_action.triggered.connect(self._show_search_dialog)
        toolbar.addAction(search_action)
        
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
        
        # 分割窗口：树视图 + 内容区域
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 目录树
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("目录结构")
        self.tree_widget.setMinimumWidth(200)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        self.tree_widget.itemExpanded.connect(self._on_tree_item_expanded)
        
        # 视图管理器
        self.view_manager = ViewManager()
        self.view_manager.item_clicked.connect(self._on_view_item_clicked)
        self.view_manager.item_double_clicked.connect(self._on_view_item_double_clicked)
        
        # 文件表格（保留用于兼容）
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
        
        # 信息面板
        self.info_panel = FilePropertiesPanel()
        self.info_panel.setMinimumWidth(250)
        self.info_panel.setMaximumWidth(350)
        
        # 创建右侧分割窗口（视图管理器 + 信息面板）
        right_splitter = QSplitter(Qt.Orientation.Horizontal)
        right_splitter.addWidget(self.view_manager)
        right_splitter.addWidget(self.info_panel)
        right_splitter.setSizes([500, 250])
        
        # 主分割窗口（树 + 右侧）
        splitter.addWidget(self.tree_widget)
        splitter.addWidget(right_splitter)
        splitter.setSizes([200, 750])
        
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
        self.encrypted_volume = None
        self.is_encrypted = False
        
        # 检查是否是加密卷
        try:
            with open(path, 'rb') as f:
                # 读取前 512 字节检查是否是 CoreStorage
                header_data = f.read(512)
                if len(header_data) >= 512 and header_data[88:90] == b'CS':
                    # 是 CoreStorage 卷
                    self.is_encrypted = True
                    
                    # 尝试解析加密卷头
                    try:
                        cs_header = EncryptedVolumeHeader(header_data)
                        if cs_header.is_encrypted:
                            # 显示密码对话框
                            password = PasswordDialog.get_password(
                                self, os.path.basename(path)
                            )
                            
                            if password is None:
                                # 用户取消
                                self.setEnabled(True)
                                return
                            
                            # TODO: 实际解密逻辑
                            QMessageBox.information(
                                self, "加密卷",
                                "检测到加密卷，但解密功能尚未完全实现。"
                            )
                    except CryptoError as e:
                        QMessageBox.warning(self, "警告", f"解析加密卷头失败: {e}")
        except Exception:
            pass
        
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
        
        # 更新信息面板
        self.info_panel.set_volume_header(self.current_header)
        
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
        
        self.folder_thread = FolderLoadThread(self.current_path, parent_id)
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
        # 记录父目录历史（用于向上导航）
        if self.current_folder_id != parent_id:
            self.folder_history.append(self.current_folder_id)
        
        self.current_folder_id = parent_id
        
        # 更新地址栏
        self._update_address_bar(parent_id)
        
        # 检查缓存
        if parent_id in self.folder_cache:
            self._update_table(self.folder_cache[parent_id])
            self._update_view(self.folder_cache[parent_id])
        else:
            # 异步加载
            self._load_folder_async(parent_id)
        
        # 更新向上按钮状态
        self.up_action.setEnabled(len(self.folder_history) > 0 and parent_id != 2)
    
    def _update_view(self, contents: list):
        """更新视图内容"""
        # 分离文件夹和文件
        folders = [item for item in contents if item['type'] == 'folder']
        files = [item for item in contents if item['type'] == 'file']
        
        # 排序
        folders.sort(key=lambda x: x['name'].lower())
        files.sort(key=lambda x: x['name'].lower())
        
        # 合并
        sorted_items = folders + files
        
        # 更新视图管理器
        self.view_manager.set_items(sorted_items)
    
    def _on_view_item_clicked(self, item_data: dict):
        """视图项目被点击"""
        # 更新信息面板
        if item_data:
            if item_data['type'] == 'file':
                self.info_panel.set_info_from_dict({
                    'name': item_data.get('name', ''),
                    'type': 'file',
                    'size': item_data.get('size', 0),
                    'create_date': item_data.get('create_date', 0),
                    'mod_date': item_data.get('mod_date', 0),
                    'id': item_data.get('id', 0),
                })
            elif item_data['type'] == 'folder':
                self.info_panel.set_info_from_dict({
                    'name': item_data.get('name', ''),
                    'type': 'folder',
                    'size': 0,
                    'create_date': item_data.get('create_date', 0),
                    'mod_date': item_data.get('mod_date', 0),
                    'id': item_data.get('id', 0),
                })
    
    def _on_view_item_double_clicked(self, item_data: dict):
        """视图项目被双击"""
        if item_data['type'] == 'folder':
            self._load_folder_contents(item_data['id'])
            self.up_action.setEnabled(True)
    
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
            
            # 显示第一个选中项的信息
            row = selected[0].row()
            name_item = self.table_widget.item(row, 0)
            if name_item:
                item_data = name_item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    # 更新信息面板
                    if item_data['type'] == 'file':
                        # 显示文件信息
                        self.info_panel.set_info_from_dict({
                            'name': item_data.get('name', ''),
                            'type': 'file',
                            'size': item_data.get('size', 0),
                            'create_date': item_data.get('create_date', 0),
                            'mod_date': item_data.get('mod_date', 0),
                            'id': item_data.get('id', 0),
                        })
                    elif item_data['type'] == 'folder':
                        # 显示文件夹信息
                        self.info_panel.set_info_from_dict({
                            'name': item_data.get('name', ''),
                            'type': 'folder',
                            'size': 0,
                            'create_date': item_data.get('create_date', 0),
                            'mod_date': item_data.get('mod_date', 0),
                            'id': item_data.get('id', 0),
                        })
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
        
        # 创建进度对话框
        progress = QProgressDialog("正在提取文件...", "取消", 0, len(files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        extracted_count = 0
        errors = []
        
        try:
            # 使用 HFSPlusVolume 提取文件
            with HFSPlusVolume(self.current_path) as vol:
                for i, file_data in enumerate(files):
                    if progress.wasCanceled():
                        break
                    
                    progress.setLabelText(f"正在提取: {file_data['name']}")
                    progress.setValue(i)
                    QApplication.processEvents()
                    
                    try:
                        # 构建输出路径
                        output_path = os.path.join(target_dir, file_data['name'])
                        
                        # 读取文件数据
                        file_id = file_data['id']
                        data = vol.read_file(file_id)
                        
                        # 写入文件
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(data)
                        
                        extracted_count += 1
                    except Exception as e:
                        errors.append(f"{file_data['name']}: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"提取失败: {str(e)}")
            return
        finally:
            progress.setValue(len(files))
        
        # 显示结果
        if errors:
            error_text = "\n".join(errors[:10])
            if len(errors) > 10:
                error_text += f"\n... 还有 {len(errors) - 10} 个错误"
            QMessageBox.warning(
                self, "提取完成",
                f"成功提取 {extracted_count}/{len(files)} 个文件\n\n错误:\n{error_text}"
            )
        else:
            QMessageBox.information(
                self, "提取完成",
                f"成功提取 {extracted_count} 个文件到:\n{target_dir}"
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
        """向上导航到父目录"""
        if not self.folder_history:
            return
        
        # 从历史记录中取出父目录 ID
        parent_id = self.folder_history.pop()
        
        # 更新向上按钮状态
        self.up_action.setEnabled(len(self.folder_history) > 0 and parent_id != 2)
        
        # 加载父目录内容（不记录历史）
        self.current_folder_id = parent_id
        self._update_address_bar(parent_id)
        
        # 检查缓存
        if parent_id in self.folder_cache:
            self._update_table(self.folder_cache[parent_id])
            self._update_view(self.folder_cache[parent_id])
        else:
            self._load_folder_async(parent_id)
    
    def _update_address_bar(self, folder_id: int):
        """更新地址栏显示"""
        # 构建路径
        path_parts = []
        current_id = folder_id
        
        # 从 folder_cache 中查找父目录名称
        # 简化处理：只显示 CNID
        if folder_id == 2:
            self.address_edit.setText("/")
        else:
            self.address_edit.setText(f"CNID: {folder_id}")
    
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
            "HFSExplorer (Alpha)\n\n"
            "只读 HFS+/HFSX 文件系统浏览器。\n\n"
            "当前状态：Alpha 原型，仅支持基本目录浏览。\n"
            "原作者: Erik Larsson (Catacombae Software)"
        )
    
    def _show_search_dialog(self):
        """显示搜索对话框"""
        if self.current_catalog is None:
            QMessageBox.information(self, "搜索", "请先打开一个 HFS+ 卷")
            return
        
        # 创建简单的搜索对话框
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
        
        dialog = QDialog(self)
        dialog.setWindowTitle("搜索")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 搜索输入
        search_layout = QHBoxLayout()
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入搜索关键词...")
        
        match_combo = QComboBox()
        match_combo.addItems(["包含", "精确匹配", "开头匹配", "结尾匹配"])
        
        filter_combo = QComboBox()
        filter_combo.addItems(["所有", "仅文件", "仅文件夹"])
        
        search_button = QPushButton("搜索")
        
        search_layout.addWidget(search_edit)
        search_layout.addWidget(match_combo)
        search_layout.addWidget(filter_combo)
        search_layout.addWidget(search_button)
        
        layout.addLayout(search_layout)
        
        # 结果表格
        result_table = QTableWidget()
        result_table.setColumnCount(4)
        result_table.setHorizontalHeaderLabels(["名称", "类型", "大小", "修改时间"])
        result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        result_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        
        layout.addWidget(result_table)
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        # 搜索功能
        def do_search():
            query = search_edit.text().strip()
            if not query:
                return
            
            # 获取匹配类型
            match_type_map = {
                "包含": SearchMatchType.CONTAINS,
                "精确匹配": SearchMatchType.EXACT,
                "开头匹配": SearchMatchType.STARTS_WITH,
                "结尾匹配": SearchMatchType.ENDS_WITH,
            }
            match_type = match_type_map.get(match_combo.currentText(), SearchMatchType.CONTAINS)
            
            # 获取过滤器
            filter_map = {
                "所有": SearchFilter.ALL,
                "仅文件": SearchFilter.FILES_ONLY,
                "仅文件夹": SearchFilter.FOLDERS_ONLY,
            }
            search_filter = filter_map.get(filter_combo.currentText(), SearchFilter.ALL)
            
            # 执行搜索
            if self.search_engine is None:
                self.search_engine = SearchEngine(self.current_catalog)
            
            results = self.search_engine.search(
                query, 
                match_type=match_type,
                search_filter=search_filter
            )
            
            # 显示结果
            result_table.setRowCount(len(results))
            for i, result in enumerate(results):
                # 名称
                name_item = QTableWidgetItem(result.name)
                result_table.setItem(i, 0, name_item)
                
                # 类型
                type_item = QTableWidgetItem("文件" if result.item_type == "file" else "文件夹")
                result_table.setItem(i, 1, type_item)
                
                # 大小
                if result.item_type == "file":
                    size_item = QTableWidgetItem(format_size(result.size))
                else:
                    size_item = QTableWidgetItem("-")
                result_table.setItem(i, 2, size_item)
                
                # 修改时间
                mod_item = QTableWidgetItem(hfs_date_to_string(result.mod_date))
                result_table.setItem(i, 3, mod_item)
        
        search_button.clicked.connect(do_search)
        search_edit.returnPressed.connect(do_search)
        
        dialog.exec()
    
    def _set_view_mode(self, mode: ViewMode):
        """设置视图模式"""
        self.view_manager.set_view_mode(mode)
        
        # 更新状态栏
        mode_names = {
            ViewMode.ICON: "图标视图",
            ViewMode.LIST: "列表视图",
            ViewMode.COLUMN: "分栏视图",
            ViewMode.GALLERY: "画廊视图",
        }
        self.statusBar().showMessage(f"视图模式: {mode_names.get(mode, '未知')}")
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖放进入事件"""
        # 检查是否接受文件拖放
        if event.mimeData().hasUrls():
            # 检查是否有文件
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        
        event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """拖放放下事件"""
        # 获取拖放的文件
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                files.append(url.toLocalFile())
        
        # 打开第一个文件
        if files:
            self._load_filesystem(files[0])
        
        event.acceptProposedAction()


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