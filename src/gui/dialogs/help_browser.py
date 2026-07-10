"""
帮助浏览器

提供内置帮助文档的查看功能。
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPushButton, QTreeWidget, QTreeWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt


HELP_CONTENT = {
    "入门": {
        "简介": """
<h2>HFSExplorer 简介</h2>
<p>HFSExplorer 是一个用于浏览和提取 HFS+/HFSX 文件系统内容的工具。</p>

<h3>主要功能</h3>
<ul>
<li>浏览 HFS+/HFSX 卷的内容</li>
<li>提取文件和文件夹</li>
<li>创建、删除、重命名文件和文件夹</li>
<li>支持 DMG 镜像文件</li>
<li>支持物理设备访问</li>
<li>搜索文件</li>
<li>格式化 HFS+ 卷</li>
</ul>

<h3>支持的文件系统</h3>
<ul>
<li>HFS+ (Mac OS Extended)</li>
<li>HFSX (Mac OS Extended, Case-sensitive)</li>
</ul>
""",
        "快速开始": """
<h2>快速开始</h2>

<h3>打开镜像文件</h3>
<ol>
<li>点击 <b>文件 → 打开</b> 或按 <b>Ctrl+O</b></li>
<li>选择 DMG、IMG 或其他镜像文件</li>
<li>浏览文件内容</li>
</ol>

<h3>打开物理设备</h3>
<ol>
<li>点击 <b>文件 → 打开设备</b> 或按 <b>Ctrl+D</b></li>
<li>选择要打开的设备</li>
<li>选择 HFS+ 分区</li>
</ol>

<h3>提取文件</h3>
<ol>
<li>选择要提取的文件或文件夹</li>
<li>点击 <b>文件 → 提取</b> 或按 <b>Ctrl+E</b></li>
<li>选择保存位置</li>
</ol>
""",
        "系统要求": """
<h2>系统要求</h2>
<ul>
<li>Windows 10/11, Linux, macOS</li>
<li>Python 3.9+</li>
<li>PyQt6</li>
</ul>

<h3>权限要求</h3>
<p>访问物理设备需要管理员/root 权限：</p>
<ul>
<li><b>Windows</b>: 以管理员身份运行</li>
<li><b>Linux/macOS</b>: 使用 sudo</li>
</ul>
"""
    },
    "功能": {
        "文件浏览": """
<h2>文件浏览</h2>

<h3>视图模式</h3>
<ul>
<li><b>图标视图</b>: 显示文件图标</li>
<li><b>列表视图</b>: 显示详细信息列表</li>
<li><b>分栏视图</b>: 类似 macOS Finder</li>
<li><b>画廊视图</b>: 预览图片</li>
</ul>

<h3>导航</h3>
<ul>
<li>双击文件夹进入</li>
<li>点击 <b>向上</b> 按钮返回上级</li>
<li>使用地址栏输入路径</li>
</ul>
""",
        "搜索": """
<h2>搜索</h2>

<h3>搜索方式</h3>
<ul>
<li><b>包含</b>: 文件名包含搜索词</li>
<li><b>精确匹配</b>: 完全匹配</li>
<li><b>开头匹配</b>: 以搜索词开头</li>
<li><b>结尾匹配</b>: 以搜索词结尾</li>
<li><b>正则表达式</b>: 使用正则表达式</li>
</ul>

<h3>搜索过滤</h3>
<ul>
<li><b>所有</b>: 搜索文件和文件夹</li>
<li><b>仅文件</b>: 只搜索文件</li>
<li><b>仅文件夹</b>: 只搜索文件夹</li>
</ul>

<h3>快捷键</h3>
<p><b>Ctrl+F</b>: 打开搜索对话框</p>
""",
        "写入操作": """
<h2>写入操作</h2>

<h3>创建文件/文件夹</h3>
<ul>
<li>右键菜单 → 新建 → 文件/文件夹</li>
<li><b>Ctrl+N</b>: 新建文件</li>
<li><b>Ctrl+Shift+N</b>: 新建文件夹</li>
</ul>

<h3>删除</h3>
<ul>
<li>选择项目 → 右键 → 删除</li>
<li>会显示确认对话框</li>
</ul>

<h3>重命名</h3>
<ul>
<li>选择项目 → 右键 → 重命名</li>
<li>输入新名称</li>
</ul>

<h3>注意事项</h3>
<p>写入操作需要以读写模式打开文件。某些只读设备无法写入。</p>
""",
        "格式化": """
<h2>格式化</h2>

<h3>创建新卷</h3>
<ol>
<li>点击 <b>文件 → 格式化</b></li>
<li>选择目标文件</li>
<li>设置卷名称、块大小、卷大小</li>
<li>点击 <b>格式化</b></li>
</ol>

<h3>参数说明</h3>
<ul>
<li><b>卷名称</b>: 最长 255 个字符</li>
<li><b>块大小</b>: 512-65536 字节，建议 4096</li>
<li><b>卷大小</b>: 建议至少 1 MB</li>
</ul>
"""
    },
    "快捷键": {
        "文件操作": """
<h2>文件操作快捷键</h2>
<table border="1" cellpadding="5">
<tr><td><b>Ctrl+O</b></td><td>打开文件</td></tr>
<tr><td><b>Ctrl+D</b></td><td>打开设备</td></tr>
<tr><td><b>Ctrl+E</b></td><td>提取文件</td></tr>
<tr><td><b>Ctrl+N</b></td><td>新建文件</td></tr>
<tr><td><b>Ctrl+Shift+N</b></td><td>新建文件夹</td></tr>
<tr><td><b>Ctrl+F</b></td><td>搜索</td></tr>
<tr><td><b>Ctrl+I</b></td><td>卷信息</td></tr>
<tr><td><b>Space</b></td><td>预览文件</td></tr>
<tr><td><b>Delete</b></td><td>删除</td></tr>
<tr><td><b>F2</b></td><td>重命名</td></tr>
<tr><td><b>F5</b></td><td>刷新</td></tr>
</table>
""",
        "导航快捷键": """
<h2>导航快捷键</h2>
<table border="1" cellpadding="5">
<tr><td><b>Backspace</b></td><td>向上</td></tr>
<tr><td><b>Enter</b></td><td>打开选中项</td></tr>
<tr><td><b>Alt+Left</b></td><td>后退</td></tr>
<tr><td><b>Alt+Right</b></td><td>前进</td></tr>
</table>
"""
    },
    "常见问题": {
        "无法打开设备": """
<h2>无法打开设备</h2>

<h3>问题</h3>
<p>提示"权限错误"或"无法读取设备"</p>

<h3>解决方案</h3>
<ul>
<li><b>Windows</b>: 右键命令提示符 → 以管理员身份运行</li>
<li><b>Linux</b>: 使用 <code>sudo python3 main.py</code></li>
<li><b>macOS</b>: 使用 <code>sudo python3 main.py</code></li>
</ul>
""",
        "找不到 HFS+ 分区": """
<h2>找不到 HFS+ 分区</h2>

<h3>可能原因</h3>
<ul>
<li>设备上没有 HFS+ 分区</li>
<li>分区表格式不支持</li>
<li>需要使用"自动检测"功能</li>
</ul>

<h3>解决方案</h3>
<ol>
<li>点击 <b>自动检测...</b> 按钮</li>
<li>确保设备已连接并格式化为 HFS+</li>
<li>尝试手动指定分区偏移</li>
</ol>
""",
        "文件提取失败": """
<h2>文件提取失败</h2>

<h3>可能原因</h3>
<ul>
<li>目标路径没有写入权限</li>
<li>磁盘空间不足</li>
<li>文件系统损坏</li>
</ul>

<h3>解决方案</h3>
<ol>
<li>检查目标文件夹权限</li>
<li>确保有足够的磁盘空间</li>
<li>尝试提取到其他位置</li>
</ol>
"""
    }
}


class HelpBrowserDialog(QDialog):
    """
    帮助浏览器对话框
    
    Usage:
        dialog = HelpBrowserDialog(parent)
        dialog.exec()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HFSExplorer 帮助")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._load_help_topics()
        self._show_default_page()
    
    def _setup_ui(self):
        """设置界面"""
        layout = QHBoxLayout(self)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧目录树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("目录")
        self.tree.setMinimumWidth(200)
        self.tree.currentItemChanged.connect(self._on_topic_selected)
        splitter.addWidget(self.tree)
        
        # 右侧内容
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        splitter.addWidget(self.browser)
        
        # 设置分割比例
        splitter.setSizes([200, 500])
        
        layout.addWidget(splitter)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        home_button = QPushButton("首页")
        home_button.clicked.connect(self._show_default_page)
        button_layout.addWidget(home_button)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _load_help_topics(self):
        """加载帮助主题"""
        for category, topics in HELP_CONTENT.items():
            category_item = QTreeWidgetItem(self.tree, [category])
            category_item.setFlags(category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            
            for topic_name in topics:
                topic_item = QTreeWidgetItem(category_item, [topic_name])
                topic_item.setData(0, Qt.ItemDataRole.UserRole, (category, topic_name))
            
            category_item.setExpanded(True)
    
    def _on_topic_selected(self, current, previous):
        """主题被选中"""
        if current is None:
            return
        
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if data:
            category, topic_name = data
            if category in HELP_CONTENT and topic_name in HELP_CONTENT[category]:
                self.browser.setHtml(HELP_CONTENT[category][topic_name])
    
    def _show_default_page(self):
        """显示默认页面"""
        default_html = """
<h1>HFSExplorer 帮助</h1>
<p>欢迎使用 HFSExplorer!</p>

<h2>目录</h2>
<ul>
<li><b>入门</b>: 简介、快速开始、系统要求</li>
<li><b>功能</b>: 文件浏览、搜索、写入操作、格式化</li>
<li><b>快捷键</b>: 文件操作、导航快捷键</li>
<li><b>常见问题</b>: 常见问题解答</li>
</ul>

<h2>关于</h2>
<p>HFSExplorer 是一个用于浏览和提取 HFS+/HFSX 文件系统内容的工具。</p>
<p>原作者: Erik Larsson (Catacombae Software)</p>
"""
        self.browser.setHtml(default_html)
    
    def show_topic(self, category: str, topic: str):
        """
        显示指定主题
        
        Args:
            category: 类别
            topic: 主题名称
        """
        if category in HELP_CONTENT and topic in HELP_CONTENT[category]:
            self.browser.setHtml(HELP_CONTENT[category][topic])
            
            # 选中对应的树节点
            for i in range(self.tree.topLevelItemCount()):
                category_item = self.tree.topLevelItem(i)
                for j in range(category_item.childCount()):
                    topic_item = category_item.child(j)
                    data = topic_item.data(0, Qt.ItemDataRole.UserRole)
                    if data == (category, topic):
                        self.tree.setCurrentItem(topic_item)
                        return


def show_help(parent=None):
    """显示帮助对话框"""
    dialog = HelpBrowserDialog(parent)
    dialog.exec()
