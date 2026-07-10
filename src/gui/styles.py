"""
GUI 样式表

提供统一的界面样式。
"""

# 主题颜色
COLORS = {
    'primary': '#2196F3',      # 蓝色
    'primary_dark': '#1976D2',
    'primary_light': '#BBDEFB',
    'accent': '#FF9800',       # 橙色
    'background': '#FAFAFA',
    'surface': '#FFFFFF',
    'error': '#F44336',
    'success': '#4CAF50',
    'warning': '#FF9800',
    'text_primary': '#212121',
    'text_secondary': '#757575',
    'divider': '#BDBDBD',
}

# 主样式表
MAIN_STYLESHEET = """
/* 主窗口 */
QMainWindow {
    background-color: #FAFAFA;
}

/* 菜单栏 */
QMenuBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E0E0E0;
    padding: 2px;
}

QMenuBar::item {
    padding: 6px 12px;
    margin: 0px 2px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    margin: 2px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

QMenu::separator {
    height: 1px;
    background-color: #E0E0E0;
    margin: 4px 8px;
}

/* 工具栏 */
QToolBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E0E0E0;
    padding: 4px;
    spacing: 4px;
}

QToolBar::separator {
    width: 1px;
    background-color: #E0E0E0;
    margin: 4px 8px;
}

QToolButton {
    padding: 6px 12px;
    border: none;
    border-radius: 4px;
    color: #212121;
}

QToolButton:hover {
    background-color: #E3F2FD;
    color: #1976D2;
}

QToolButton:pressed {
    background-color: #BBDEFB;
}

QToolButton:disabled {
    color: #BDBDBD;
}

/* 状态栏 */
QStatusBar {
    background-color: #FFFFFF;
    border-top: 1px solid #E0E0E0;
    padding: 4px;
    color: #757575;
}

QStatusBar::item {
    border: none;
}

QStatusBar QLabel {
    padding: 0 8px;
}

/* 地址栏 */
QLineEdit {
    padding: 8px 12px;
    border: 2px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
    color: #212121;
    selection-background-color: #BBDEFB;
}

QLineEdit:focus {
    border-color: #2196F3;
}

QLineEdit:hover {
    border-color: #BDBDBD;
}

QPushButton {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    background-color: #2196F3;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #1976D2;
}

QPushButton:pressed {
    background-color: #0D47A1;
}

QPushButton:disabled {
    background-color: #BDBDBD;
    color: #757575;
}

/* 分割窗口 */
QSplitter::handle {
    background-color: #E0E0E0;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #2196F3;
}

/* 树视图 */
QTreeWidget {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 4px;
}

QTreeWidget::item {
    padding: 6px;
    margin: 2px;
    border-radius: 4px;
}

QTreeWidget::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

QTreeWidget::item:hover {
    background-color: #F5F5F5;
}

QTreeWidget::branch {
    background-color: #FFFFFF;
}

QTreeWidget::branch:has-siblings:!adjoins-item {
    border-image: url(vline.png) 0;
}

QTreeWidget::branch:has-siblings:adjoins-item {
    border-image: url(branch-more.png) 0;
}

QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
    border-image: url(branch-end.png) 0;
}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: url(branch-closed.png) 0;
}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    border-image: url(branch-open.png) 0;
}

/* 表格视图 */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    gridline-color: #F5F5F5;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

QTableWidget::item:hover {
    background-color: #F5F5F5;
}

QHeaderView::section {
    background-color: #FAFAFA;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #E0E0E0;
    font-weight: bold;
    color: #757575;
}

QHeaderView::section:hover {
    background-color: #E3F2FD;
    color: #1976D2;
}

/* 标签页 */
QTabWidget::pane {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QTabBar::tab {
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    color: #757575;
}

QTabBar::tab:selected {
    border-bottom-color: #2196F3;
    color: #2196F3;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #E3F2FD;
}

/* 滚动条 */
QScrollBar:vertical {
    border: none;
    background-color: #F5F5F5;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #BDBDBD;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #9E9E9E;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background-color: #F5F5F5;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #BDBDBD;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #9E9E9E;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* 进度条 */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #E0E0E0;
    text-align: center;
    color: #FFFFFF;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #2196F3;
    border-radius: 4px;
}

/* 对话框 */
QDialog {
    background-color: #FAFAFA;
}

/* 消息框 */
QMessageBox {
    background-color: #FFFFFF;
}

QMessageBox QLabel {
    color: #212121;
}

/* 输入对话框 */
QInputDialog {
    background-color: #FFFFFF;
}

/* 文件对话框 */
QFileDialog {
    background-color: #FFFFFF;
}

/* 列表视图 */
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 4px;
}

QListWidget::item {
    padding: 8px;
    margin: 2px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #E3F2FD;
    color: #1976D2;
}

QListWidget::item:hover {
    background-color: #F5F5F5;
}

/* 组合框 */
QComboBox {
    padding: 8px 12px;
    border: 2px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
    color: #212121;
}

QComboBox:focus {
    border-color: #2196F3;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    selection-background-color: #E3F2FD;
}

/* 旋转框 */
QSpinBox {
    padding: 8px 12px;
    border: 2px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
    color: #212121;
}

QSpinBox:focus {
    border-color: #2196F3;
}

/* 复选框 */
QCheckBox {
    spacing: 8px;
    color: #212121;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #2196F3;
    border-color: #2196F3;
}

QCheckBox::indicator:hover {
    border-color: #2196F3;
}

/* 单选按钮 */
QRadioButton {
    spacing: 8px;
    color: #212121;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #E0E0E0;
    border-radius: 9px;
    background-color: #FFFFFF;
}

QRadioButton::indicator:checked {
    background-color: #2196F3;
    border-color: #2196F3;
}

QRadioButton::indicator:hover {
    border-color: #2196F3;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    margin-top: 16px;
    padding-top: 24px;
    font-weight: bold;
    color: #212121;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #757575;
}

/* 文本编辑 */
QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 8px;
    color: #212121;
}

QTextEdit:focus {
    border-color: #2196F3;
}

/* 标签 */
QLabel {
    color: #212121;
}

/* 工具提示 */
QToolTip {
    background-color: #FFFFFF;
    color: #212121;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 8px;
}
"""


def get_stylesheet() -> str:
    """获取样式表"""
    return MAIN_STYLESHEET


def get_dark_stylesheet() -> str:
    """获取暗色主题样式表"""
    return """
    QMainWindow {
        background-color: #1E1E1E;
    }
    
    QMenuBar {
        background-color: #2D2D2D;
        color: #FFFFFF;
    }
    
    QMenu {
        background-color: #2D2D2D;
        color: #FFFFFF;
    }
    
    QToolBar {
        background-color: #2D2D2D;
    }
    
    QStatusBar {
        background-color: #2D2D2D;
        color: #BDBDBD;
    }
    
    QTreeWidget, QTableWidget, QListWidget {
        background-color: #2D2D2D;
        color: #FFFFFF;
        border-color: #3E3E3E;
    }
    
    QLineEdit, QTextEdit {
        background-color: #3E3E3E;
        color: #FFFFFF;
        border-color: #4E4E4E;
    }
    
    QPushButton {
        background-color: #2196F3;
        color: #FFFFFF;
    }
    """
