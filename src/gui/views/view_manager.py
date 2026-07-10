"""
HFS+ 视图模式

提供类似 macOS Finder 的多种视图模式。
"""

from enum import Enum
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QSplitter, QStackedWidget, QScrollArea,
    QFrame, QSizePolicy, QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont


class ViewMode(Enum):
    """视图模式"""
    ICON = "icon"      # 图标视图
    LIST = "list"      # 列表视图
    COLUMN = "column"  # 分栏视图
    GALLERY = "gallery"  # 画廊视图


class IconViewWidget(QWidget):
    """
    图标视图
    
    以图标形式显示文件和文件夹。
    """
    
    item_clicked = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._items = []
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # 内容容器
        self.content = QWidget()
        self.content_layout = QHBoxLayout(self.content)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_layout.setSpacing(20)
        
        scroll.setWidget(self.content)
        layout.addWidget(scroll)
    
    def set_items(self, items: List[Dict[str, Any]]):
        """
        设置项目列表
        
        Args:
            items: 项目列表，每个项目包含 name, type, size 等信息
        """
        # 清空现有项目
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self._items = items
        
        # 添加新项目
        for item in items:
            self._add_item(item)
    
    def _add_item(self, item: Dict[str, Any]):
        """添加项目"""
        # 创建项目容器
        item_widget = QWidget()
        item_widget.setFixedSize(100, 120)
        item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(item_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图标
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(64, 64)
        
        if item['type'] == 'folder':
            icon_label.setText("📁")
        else:
            icon_label.setText("📄")
        
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)
        
        # 名称
        name_label = QLabel(item['name'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(90)
        
        # 设置字体
        font = name_label.font()
        font.setPointSize(9)
        name_label.setFont(font)
        
        layout.addWidget(name_label)
        
        # 添加点击事件
        item_widget.mousePressEvent = lambda e, i=item: self.item_clicked.emit(i)
        item_widget.mouseDoubleClickEvent = lambda e, i=item: self.item_double_clicked.emit(i)
        
        self.content_layout.addWidget(item_widget)


class ListViewWidget(QWidget):
    """
    列表视图
    
    以列表形式显示文件和文件夹。
    """
    
    item_clicked = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改时间"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        
        # 设置列宽
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # 连接信号
        self.table.itemClicked.connect(self._on_item_clicked)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        layout.addWidget(self.table)
    
    def set_items(self, items: List[Dict[str, Any]]):
        """
        设置项目列表
        
        Args:
            items: 项目列表
        """
        self.table.setRowCount(len(items))
        
        for i, item in enumerate(items):
            # 名称
            name_item = QTableWidgetItem(item['name'])
            if item['type'] == 'folder':
                name_item.setIcon(QIcon.fromTheme("folder"))
            else:
                name_item.setIcon(QIcon.fromTheme("text-x-generic"))
            self.table.setItem(i, 0, name_item)
            
            # 大小
            if item['type'] == 'file':
                size_item = QTableWidgetItem(self._format_size(item.get('size', 0)))
            else:
                size_item = QTableWidgetItem("-")
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 1, size_item)
            
            # 类型
            type_item = QTableWidgetItem("文件夹" if item['type'] == 'folder' else "文件")
            self.table.setItem(i, 2, type_item)
            
            # 修改时间
            mod_item = QTableWidgetItem(item.get('mod_date', '-'))
            self.table.setItem(i, 3, mod_item)
            
            # 存储项目数据
            for col in range(4):
                self.table.item(i, col).setData(Qt.ItemDataRole.UserRole, item)
    
    def _on_item_clicked(self, item: QTableWidgetItem):
        """项目被点击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_clicked.emit(data)
    
    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """项目被双击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_double_clicked.emit(data)
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"


class ColumnViewWidget(QWidget):
    """
    分栏视图
    
    以分栏形式显示文件和文件夹层级。
    """
    
    item_clicked = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    load_subitems_requested = pyqtSignal(int)  # 请求加载子文件夹内容
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._columns = []
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建分割窗口
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        
        layout.addWidget(self.splitter)
    
    def set_root_items(self, items: List[Dict[str, Any]]):
        """
        设置根项目
        
        Args:
            items: 根项目列表
        """
        # 清空现有列
        while self.splitter.count():
            widget = self.splitter.takeAt(0)
            widget.deleteLater()
        
        self._columns = []
        
        # 创建第一列
        self._add_column(items)
    
    def _add_column(self, items: List[Dict[str, Any]]):
        """添加列"""
        # 创建列表
        list_widget = QListWidget()
        list_widget.setMinimumWidth(200)
        
        # 添加项目
        for item in items:
            list_item = QListWidgetItem(item['name'])
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            
            if item['type'] == 'folder':
                list_item.setIcon(QIcon.fromTheme("folder"))
            else:
                list_item.setIcon(QIcon.fromTheme("text-x-generic"))
            
            list_widget.addItem(list_item)
        
        # 连接信号
        list_widget.currentItemChanged.connect(self._on_item_changed)
        list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # 添加到分割窗口
        self.splitter.addWidget(list_widget)
        self._columns.append(list_widget)
    
    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """项目改变"""
        if current:
            item = current.data(Qt.ItemDataRole.UserRole)
            if item:
                self.item_clicked.emit(item)
                
                # 如果是文件夹，加载子项目
                if item['type'] == 'folder':
                    self._load_subitems(item)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """项目被双击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_double_clicked.emit(data)
    
    def _load_subitems(self, folder: Dict[str, Any]):
        """加载子项目"""
        folder_id = folder.get('id')
        if folder_id:
            self.load_subitems_requested.emit(folder_id)
    
    def add_subitems_column(self, items: List[Dict[str, Any]]):
        """
        添加子项目列（由外部调用，加载完成后）
        
        Args:
            items: 子项目列表
        """
        # 移除后续列（保留当前列）
        # 当前列是最后选中的列，后续列需要替换
        while len(self._columns) > 1:
            last_widget = self.splitter.widget(len(self._columns) - 1)
            if last_widget:
                last_widget.deleteLater()
            self._columns.pop()
        
        # 添加新列
        if items:
            self._add_column(items)


class GalleryViewWidget(QWidget):
    """
    画廊视图
    
    以大图形式显示文件预览。
    """
    
    item_clicked = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 预览区域
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setStyleSheet("background-color: #f0f0f0;")
        
        layout.addWidget(self.preview_label)
        
        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setWrapping(True)
        self.list_widget.setSpacing(10)
        
        # 连接信号
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        layout.addWidget(self.list_widget)
    
    def set_items(self, items: List[Dict[str, Any]]):
        """
        设置项目列表
        
        Args:
            items: 项目列表
        """
        self.list_widget.clear()
        
        for item in items:
            list_item = QListWidgetItem(item['name'])
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            
            if item['type'] == 'folder':
                list_item.setIcon(QIcon.fromTheme("folder"))
            else:
                list_item.setIcon(QIcon.fromTheme("text-x-generic"))
            
            self.list_widget.addItem(list_item)
    
    def _on_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """项目改变"""
        if current:
            item = current.data(Qt.ItemDataRole.UserRole)
            if item:
                self.item_clicked.emit(item)
                self._update_preview(item)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """项目被双击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_double_clicked.emit(data)
    
    def _update_preview(self, item: Dict[str, Any]):
        """更新预览"""
        name = item.get('name', '')
        item_type = item.get('type', 'file')
        
        if item_type == 'folder':
            self.preview_label.setText(
                f"📁 {name}\n\n"
                f"类型: 文件夹\n"
                f"CNID: {item.get('id', '-')}\n"
                f"创建日期: {item.get('create_date', '-')}\n"
                f"修改日期: {item.get('mod_date', '-')}"
            )
        else:
            size = item.get('size', 0)
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            
            # 根据扩展名显示类型图标
            type_icon = '📄'
            type_desc = '文件'
            
            if ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'icns'):
                type_icon = '🖼️'
                type_desc = '图片'
            elif ext in ('mp3', 'wav', 'aac', 'flac', 'm4a', 'aiff'):
                type_icon = '🎵'
                type_desc = '音频'
            elif ext in ('mp4', 'mov', 'avi', 'mkv', 'm4v'):
                type_icon = '🎬'
                type_desc = '视频'
            elif ext in ('txt', 'md', 'rtf', 'doc', 'docx', 'pdf'):
                type_icon = '📝'
                type_desc = '文档'
            elif ext in ('zip', 'gz', 'tar', 'dmg', 'iso', '7z', 'rar'):
                type_icon = '📦'
                type_desc = '压缩包'
            elif ext in ('py', 'js', 'c', 'cpp', 'java', 'swift', 'rs'):
                type_icon = '💻'
                type_desc = '源代码'
            elif ext in ('app', 'exe', 'bin', 'sh'):
                type_icon = '⚙️'
                type_desc = '可执行文件'
            elif ext in ('plist', 'json', 'xml', 'yaml', 'yml'):
                type_icon = '📋'
                type_desc = '配置文件'
            
            # 格式化大小
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
            
            self.preview_label.setText(
                f"{type_icon} {name}\n\n"
                f"类型: {type_desc} ({ext.upper() if ext else '未知'})\n"
                f"大小: {size_str}\n"
                f"CNID: {item.get('id', '-')}\n"
                f"创建日期: {item.get('create_date', '-')}\n"
                f"修改日期: {item.get('mod_date', '-')}"
            )


class ViewManager(QWidget):
    """
    视图管理器
    
    管理多种视图模式。
    
    Usage:
        manager = ViewManager(parent)
        manager.set_view_mode(ViewMode.ICON)
        manager.set_items(items)
    """
    
    item_clicked = pyqtSignal(dict)
    item_double_clicked = pyqtSignal(dict)
    column_subitems_requested = pyqtSignal(int)  # 分栏视图请求加载子项
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._current_mode = ViewMode.LIST
        self._pending_column_folder_id = -1
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建堆叠窗口
        self.stack = QStackedWidget()
        
        # 创建各种视图
        self.icon_view = IconViewWidget()
        self.list_view = ListViewWidget()
        self.column_view = ColumnViewWidget()
        self.gallery_view = GalleryViewWidget()
        
        # 连接信号
        self.icon_view.item_clicked.connect(self.item_clicked.emit)
        self.icon_view.item_double_clicked.connect(self.item_double_clicked.emit)
        
        self.list_view.item_clicked.connect(self.item_clicked.emit)
        self.list_view.item_double_clicked.connect(self.item_double_clicked.emit)
        
        self.column_view.item_clicked.connect(self.item_clicked.emit)
        self.column_view.item_double_clicked.connect(self.item_double_clicked.emit)
        self.column_view.load_subitems_requested.connect(self._on_column_load_subitems)
        
        self.gallery_view.item_clicked.connect(self.item_clicked.emit)
        self.gallery_view.item_double_clicked.connect(self.item_double_clicked.emit)
        
        # 添加到堆叠窗口
        self.stack.addWidget(self.icon_view)
        self.stack.addWidget(self.list_view)
        self.stack.addWidget(self.column_view)
        self.stack.addWidget(self.gallery_view)
        
        layout.addWidget(self.stack)
    
    def _on_column_load_subitems(self, folder_id: int):
        """处理分栏视图的子项加载请求"""
        self._pending_column_folder_id = folder_id
        self.column_subitems_requested.emit(folder_id)
    
    def set_column_subitems(self, items: List[Dict[str, Any]]):
        """
        设置分栏视图的子项（由 MainWindow 加载完成后调用）
        
        Args:
            items: 子项目列表
        """
        self.column_view.add_subitems_column(items)
    
    def set_view_mode(self, mode: ViewMode):
        """
        设置视图模式
        
        Args:
            mode: 视图模式
        """
        self._current_mode = mode
        
        if mode == ViewMode.ICON:
            self.stack.setCurrentWidget(self.icon_view)
        elif mode == ViewMode.LIST:
            self.stack.setCurrentWidget(self.list_view)
        elif mode == ViewMode.COLUMN:
            self.stack.setCurrentWidget(self.column_view)
        elif mode == ViewMode.GALLERY:
            self.stack.setCurrentWidget(self.gallery_view)
    
    def set_items(self, items: List[Dict[str, Any]]):
        """
        设置项目列表
        
        Args:
            items: 项目列表
        """
        self.icon_view.set_items(items)
        self.list_view.set_items(items)
        self.column_view.set_root_items(items)
        self.gallery_view.set_items(items)
    
    @property
    def current_mode(self) -> ViewMode:
        """获取当前视图模式"""
        return self._current_mode