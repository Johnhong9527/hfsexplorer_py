"""
国际化 (i18n) 模块

支持中英文切换。
"""

from typing import Dict, Any


# 当前语言
_current_language = 'zh'


# 翻译字典
TRANSLATIONS = {
    'zh': {
        # 菜单
        'menu.file': '文件(&F)',
        'menu.file.open': '打开(&O)...',
        'menu.file.open_device': '打开设备(&D)...',
        'menu.file.new': '新建(&N)',
        'menu.file.new_file': '新建文件(&F)...',
        'menu.file.new_folder': '新建文件夹(&D)...',
        'menu.file.extract': '提取(&E)...',
        'menu.file.format': '格式化(&F)...',
        'menu.file.recent': '最近打开(&R)',
        'menu.file.exit': '退出(&X)',
        
        'menu.edit': '编辑(&E)',
        'menu.edit.copy': '复制(&C)',
        'menu.edit.cut': '剪切(&T)',
        'menu.edit.paste': '粘贴(&P)',
        'menu.edit.duplicate': '复制到此处(&D)',
        'menu.edit.select_all': '全选(&A)',
        
        'menu.tools': '工具(&T)',
        'menu.tools.search': '搜索(&S)...',
        'menu.tools.view_mode': '视图模式(&V)',
        'menu.tools.view_icon': '图标视图',
        'menu.tools.view_list': '列表视图',
        'menu.tools.view_column': '分栏视图',
        'menu.tools.view_gallery': '画廊视图',
        'menu.tools.volume_info': '卷信息(&I)...',
        'menu.tools.preview': '预览文件(&P)',
        
        'menu.help': '帮助(&H)',
        'menu.help.topics': '帮助主题(&H)...',
        'menu.help.about': '关于(&A)...',
        
        # 工具栏
        'toolbar.open': '打开',
        'toolbar.device': '设备',
        'toolbar.up': '向上',
        'toolbar.refresh': '刷新',
        'toolbar.search': '搜索',
        'toolbar.extract': '提取',
        
        # 地址栏
        'address.placeholder': '选择文件或设备...',
        'address.go': '转到',
        
        # 目录树
        'tree.header': '目录结构',
        
        # 状态栏
        'status.ready': '就绪',
        'status.loading': '正在加载: {}',
        'status.loaded': '已加载: {}, 块大小: {:,}, 文件: {:,}, 文件夹: {:,}',
        'status.selected': '选择: {} 个对象',
        'status.created_file': '已创建文件: {} (CNID: {})',
        'status.created_folder': '已创建文件夹: {} (CNID: {})',
        'status.deleted': '已删除: {}',
        'status.renamed': '已重命名为: {}',
        'status.extracted': '已提取: {} 个文件',
        'status.copied': '已复制 {} 个项目',
        'status.cut': '已剪切 {} 个项目',
        'status.pasted': '已粘贴 {} 个项目',
        'status.moved': '已移动 {} 个项目到 {}',
        
        # 对话框
        'dialog.open.title': '打开 HFS 磁盘镜像',
        'dialog.open.filter': '磁盘镜像 (*.dmg *.img *.iso *.raw *.bin);;所有文件 (*)',
        'dialog.extract.title': '提取文件',
        'dialog.extract.select': '选择保存位置',
        'dialog.format.title': '格式化 HFS+ 卷',
        'dialog.search.title': '搜索',
        'dialog.preview.title': '预览 - {}',
        'dialog.device.title': '加载文件系统从设备',
        'dialog.help.title': 'HFSExplorer 帮助',
        'dialog.about.title': '关于 HFSExplorer',
        
        # 设备对话框
        'device.autodetect': '自动检测...',
        'device.autodetect_desc': '自动检测系统中的 HFS/HFS+/HFSX 分区',
        'device.select': '从检测到的设备中选择:',
        'device.warning_cdrom': '(混合 CD-ROM 同时包含 HFS/+/X 和 ISO 文件系统将无法工作)',
        'device.refresh': '刷新设备列表',
        'device.manual': '指定设备名称:',
        'device.load': '加载',
        'device.cancel': '取消',
        'device.warning': '⚠️ 警告：直接访问物理设备可能导致数据损坏！\n请确保您知道自己在做什么。',
        'device.permission_error': '权限错误',
        'device.permission_msg': '无法读取设备: {}\n\n请以管理员身份运行程序',
        'device.autodetect_title': '自动检测',
        'device.autodetect_scanning': '正在扫描: {}',
        'device.autodetect_found': '自动检测完成！找到 {} 个 HFS+ 文件系统。\n请选择要加载的文件系统：',
        'device.autodetect_notfound': '未检测到 HFS/HFS+/HFSX 文件系统。\n\n可能的原因：\n1. 没有连接 HFS+ 格式的硬盘\n2. 需要管理员权限才能访问设备\n3. 分区表格式不支持',
        
        # 搜索对话框
        'search.placeholder': '输入搜索关键词...',
        'search.button': '搜索',
        'search.match_contains': '包含',
        'search.match_exact': '精确匹配',
        'search.match_starts': '开头匹配',
        'search.match_ends': '结尾匹配',
        'search.match_regex': '正则表达式',
        'search.filter_all': '所有',
        'search.filter_files': '仅文件',
        'search.filter_folders': '仅文件夹',
        'search.results': '搜索结果: {} 个项目',
        'search.no_results': '未找到匹配的项目',
        'search.no_query': '请输入搜索关键词',
        
        # 格式化对话框
        'format.target_file': '目标文件',
        'format.browse': '浏览...',
        'format.settings': '卷设置',
        'format.volume_name': '卷名称:',
        'format.block_size': '块大小:',
        'format.volume_size': '卷大小:',
        'format.format_button': '格式化',
        'format.confirm_title': '确认格式化',
        'format.confirm_msg': '确定要格式化吗？\n\n目标文件: {}\n卷名称: {}\n块大小: {:,} 字节\n卷大小: {} MB\n\n警告：此操作将覆盖目标文件！',
        'format.success_title': '格式化成功',
        'format.success_msg': 'HFS+ 卷已成功创建！\n\n文件: {}\n总块数: {:,}\n空闲块: {:,}',
        'format.open_title': '打开卷',
        'format.open_msg': '是否打开新创建的卷？',
        
        # 属性对话框
        'info.name': '名称',
        'info.type': '类型',
        'info.size': '大小',
        'info.create_date': '创建时间',
        'info.modify_date': '修改时间',
        'info.access_date': '访问时间',
        'info.permissions': '权限',
        'info.owner': '所有者',
        'info.group': '组',
        
        # 卷信息
        'volume.title': '卷信息',
        'volume.signature': '签名',
        'volume.version': '版本',
        'volume.block_size': '块大小',
        'volume.total_blocks': '总块数',
        'volume.free_blocks': '空闲块',
        'volume.file_count': '文件数',
        'volume.folder_count': '文件夹数',
        'volume.journaled': '日志',
        'volume.locked': '锁定',
        
        # 关于对话框
        'about.title': '关于 HFSExplorer',
        'about.text': '''HFSExplorer (Alpha)

HFS+/HFSX 文件系统浏览器，支持读写操作。

功能:
- 浏览 HFS+/HFSX 卷
- 提取文件和文件夹
- 创建、删除、重命名文件和文件夹
- 搜索功能
- 格式化 HFS+ 卷
- DMG 镜像支持

当前状态：Alpha 原型。
原作者: Erik Larsson (Catacombae Software)''',
        
        # 错误消息
        'error.title': '错误',
        'error.load_failed': '无法加载文件:\n{}',
        'error.create_file_failed': '创建文件失败: {}',
        'error.create_folder_failed': '创建文件夹失败: {}',
        'error.delete_failed': '删除失败: {}',
        'error.rename_failed': '重命名失败: {}',
        'error.extract_failed': '提取失败: {}',
        'error.no_selection': '请先选择要操作的项目',
        'error.no_file_selection': '请先选择要提取的文件',
        'error.no_files_in_selection': '选中的项目中没有文件',
        'error.no_volume': '未打开任何卷',
        'error.no_write_support': '无法初始化写入支持',
        'error.clipboard_empty': '剪贴板为空',
        'error.no_folder_selection': '请先选择要移动的项目',
        'error.folder_not_found': '未找到目标文件夹: {}',
        
        # 确认对话框
        'confirm.delete_title': '确认删除',
        'confirm.delete_msg': '确定要删除{} \'{}\' 吗？',
        'confirm.rename_title': '重命名',
        'confirm.rename_msg': '请输入新名称:',
        'confirm.paste_title': '确认粘贴',
        'confirm.paste_msg': '确定要{} {} 个项目到当前文件夹吗？',
        'confirm.duplicate_title': '确认复制',
        'confirm.duplicate_msg': '确定要复制 {} 个项目到当前位置吗？',
        'confirm.move_title': '确认移动',
        'confirm.move_msg': '确定要移动 {} 个项目到 '{}' 吗？',
        
        # 提取对话框
        'extract.progress_title': '提取文件',
        'extract.progress_msg': '正在提取: {}',
        'extract.success_title': '提取完成',
        'extract.success_msg': '已成功提取 {} 个文件到:\n{}',
        
        # 预览
        'preview.title': '预览',
        'preview.file_info': '文件: {}\n大小: {}\n\n此文件类型不支持预览。',
        'preview.too_large': '\n\n... (文件太大，仅显示前 50000 个字符)',
        
        # 单位
        'size.bytes': '{} B',
        'size.kb': '{:.1f} KB',
        'size.mb': '{:.1f} MB',
        'size.gb': '{:.2f} GB',
        
        # 文件类型
        'type.folder': '文件夹',
        'type.file': '文件',
        'type.volume': '卷',
        
        # 欢迎引导
        'welcome.title': '欢迎使用 HFSExplorer',
        'welcome.message': '''欢迎使用 HFSExplorer!

这是一个用于浏览和提取 HFS+/HFSX 文件系统内容的工具。

快速开始：
1. 点击 "打开" 按钮选择 DMG/IMG 镜像文件
2. 或点击 "设备" 按钮打开物理硬盘
3. 浏览文件并提取您需要的内容

快捷键：
- Ctrl+O: 打开文件
- Ctrl+D: 打开设备
- Ctrl+F: 搜索
- Ctrl+E: 提取文件
- F1: 帮助

点击 "确定" 开始使用。''',
    },
    
    'en': {
        # Menu
        'menu.file': '&File',
        'menu.file.open': '&Open...',
        'menu.file.open_device': 'Open &Device...',
        'menu.file.new': '&New',
        'menu.file.new_file': 'New &File...',
        'menu.file.new_folder': 'New Fo&lder...',
        'menu.file.extract': '&Extract...',
        'menu.file.format': '&Format...',
        'menu.file.recent': '&Recent',
        'menu.file.exit': 'E&xit',
        
        'menu.edit': '&Edit',
        'menu.edit.copy': '&Copy',
        'menu.edit.cut': 'Cu&t',
        'menu.edit.paste': '&Paste',
        'menu.edit.duplicate': '&Duplicate',
        'menu.edit.select_all': 'Select &All',
        
        'menu.tools': '&Tools',
        'menu.tools.search': '&Search...',
        'menu.tools.view_mode': '&View Mode',
        'menu.tools.view_icon': 'Icon View',
        'menu.tools.view_list': 'List View',
        'menu.tools.view_column': 'Column View',
        'menu.tools.view_gallery': 'Gallery View',
        'menu.tools.volume': 'Volume &Info...',
        'menu.tools.preview': '&Preview File',
        
        'menu.help': '&Help',
        'menu.help.topics': 'Help &Topics...',
        'menu.help.about': '&About...',
        
        # Toolbar
        'toolbar.open': 'Open',
        'toolbar.device': 'Device',
        'toolbar.up': 'Up',
        'toolbar.refresh': 'Refresh',
        'toolbar.search': 'Search',
        'toolbar.extract': 'Extract',
        
        # Address bar
        'address.placeholder': 'Select file or device...',
        'address.go': 'Go',
        
        # Tree
        'tree.header': 'Directory Structure',
        
        # Status bar
        'status.ready': 'Ready',
        'status.loading': 'Loading: {}',
        'status.loaded': 'Loaded: {}, Block Size: {:,}, Files: {:,}, Folders: {:,}',
        'status.selected': 'Selected: {} objects',
        'status.created_file': 'Created file: {} (CNID: {})',
        'status.created_folder': 'Created folder: {} (CNID: {})',
        'status.deleted': 'Deleted: {}',
        'status.renamed': 'Renamed to: {}',
        'status.extracted': 'Extracted: {} files',
        'status.copied': 'Copied {} items',
        'status.cut': 'Cut {} items',
        'status.pasted': 'Pasted {} items',
        'status.moved': 'Moved {} items to {}',
        
        # Dialogs
        'dialog.open.title': 'Open HFS Disk Image',
        'dialog.open.filter': 'Disk Images (*.dmg *.img *.iso *.raw *.bin);;All Files (*)',
        'dialog.extract.title': 'Extract Files',
        'dialog.extract.select': 'Select save location',
        'dialog.format.title': 'Format HFS+ Volume',
        'dialog.search.title': 'Search',
        'dialog.preview.title': 'Preview - {}',
        'dialog.device.title': 'Load File System from Device',
        'dialog.help.title': 'HFSExplorer Help',
        'dialog.about.title': 'About HFSExplorer',
        
        # Device dialog
        'device.autodetect': 'Autodetect...',
        'device.autodetect_desc': 'Automatically detects HFS/HFS+/HFSX partitions on your system',
        'device.select': 'Select a device:',
        'device.warning_cdrom': '(hybrid CD-ROMs with both HFS/+/X and ISO filesystems won\'t work)',
        'device.refresh': 'Refresh Device List',
        'device.manual': 'Specify device name:',
        'device.load': 'Load',
        'device.cancel': 'Cancel',
        'device.warning': '⚠️ Warning: Direct access to physical devices may cause data corruption!\nPlease make sure you know what you are doing.',
        'device.permission_error': 'Permission Error',
        'device.permission_msg': 'Cannot read device: {}\n\nPlease run the program as administrator',
        'device.autodetect_title': 'Autodetect',
        'device.autodetect_scanning': 'Scanning: {}',
        'device.autodetect_found': 'Autodetection complete! Found {} HFS+ file systems.\nPlease choose which one to load:',
        'device.autodetect_notfound': 'No HFS/HFS+/HFSX file systems detected.\n\nPossible reasons:\n1. No HFS+ formatted disk connected\n2. Administrator privileges required\n3. Partition table format not supported',
        
        # Search dialog
        'search.placeholder': 'Enter search keywords...',
        'search.button': 'Search',
        'search.match_contains': 'Contains',
        'search.match_exact': 'Exact Match',
        'search.match_starts': 'Starts With',
        'search.match_ends': 'Ends With',
        'search.match_regex': 'Regex',
        'search.filter_all': 'All',
        'search.filter_files': 'Files Only',
        'search.filter_folders': 'Folders Only',
        'search.results': 'Search Results: {} items',
        'search.no_results': 'No matching items found',
        'search.no_query': 'Please enter search keywords',
        
        # Format dialog
        'format.target_file': 'Target File',
        'format.browse': 'Browse...',
        'format.settings': 'Volume Settings',
        'format.volume_name': 'Volume Name:',
        'format.block_size': 'Block Size:',
        'format.volume_size': 'Volume Size:',
        'format.format_button': 'Format',
        'format.confirm_title': 'Confirm Format',
        'format.confirm_msg': 'Are you sure you want to format?\n\nTarget File: {}\nVolume Name: {}\nBlock Size: {:,} bytes\nVolume Size: {} MB\n\nWarning: This operation will overwrite the target file!',
        'format.success_title': 'Format Successful',
        'format.success_msg': 'HFS+ volume created successfully!\n\nFile: {}\nTotal Blocks: {:,}\nFree Blocks: {:,}',
        'format.open_title': 'Open Volume',
        'format.open_msg': 'Do you want to open the newly created volume?',
        
        # Info dialog
        'info.name': 'Name',
        'info.type': 'Type',
        'info.size': 'Size',
        'info.create_date': 'Created',
        'info.modify_date': 'Modified',
        'info.access_date': 'Accessed',
        'info.permissions': 'Permissions',
        'info.owner': 'Owner',
        'info.group': 'Group',
        
        # Volume info
        'volume.title': 'Volume Information',
        'volume.signature': 'Signature',
        'volume.version': 'Version',
        'volume.block_size': 'Block Size',
        'volume.total_blocks': 'Total Blocks',
        'volume.free_blocks': 'Free Blocks',
        'volume.file_count': 'File Count',
        'volume.folder_count': 'Folder Count',
        'volume.journaled': 'Journaled',
        'volume.locked': 'Locked',
        
        # About dialog
        'about.title': 'About HFSExplorer',
        'about.text': '''HFSExplorer (Alpha)

HFS+/HFSX file system browser with read/write support.

Features:
- Browse HFS+/HFSX volumes
- Extract files and folders
- Create, delete, rename files and folders
- Search functionality
- Format HFS+ volumes
- DMG image support

Current status: Alpha prototype.
Original author: Erik Larsson (Catacombae Software)''',
        
        # Error messages
        'error.title': 'Error',
        'error.load_failed': 'Cannot load file:\n{}',
        'error.create_file_failed': 'Failed to create file: {}',
        'error.create_folder_failed': 'Failed to create folder: {}',
        'error.delete_failed': 'Delete failed: {}',
        'error.rename_failed': 'Rename failed: {}',
        'error.extract_failed': 'Extract failed: {}',
        'error.no_selection': 'Please select an item first',
        'error.no_file_selection': 'Please select files to extract',
        'error.no_files_in_selection': 'No files in selection',
        'error.no_volume': 'No volume opened',
        'error.no_write_support': 'Cannot initialize write support',
        'error.clipboard_empty': 'Clipboard is empty',
        'error.no_folder_selection': 'Please select items to move',
        'error.folder_not_found': 'Target folder not found: {}',
        
        # Confirm dialogs
        'confirm.delete_title': 'Confirm Delete',
        'confirm.delete_msg': 'Are you sure you want to delete {} \'{}\'?',
        'confirm.rename_title': 'Rename',
        'confirm.rename_msg': 'Enter new name:',
        'confirm.paste_title': 'Confirm Paste',
        'confirm.paste_msg': 'Are you sure you want to {} {} items to the current folder?',
        'confirm.duplicate_title': 'Confirm Duplicate',
        'confirm.duplicate_msg': 'Are you sure you want to duplicate {} items here?',
        'confirm.move_title': 'Confirm Move',
        'confirm.move_msg': 'Are you sure you want to move {} items to '{}'?',
        
        # Extract dialog
        'extract.progress_title': 'Extracting Files',
        'extract.progress_msg': 'Extracting: {}',
        'extract.success_title': 'Extraction Complete',
        'extract.success_msg': 'Successfully extracted {} files to:\n{}',
        
        # Preview
        'preview.title': 'Preview',
        'preview.file_info': 'File: {}\nSize: {}\n\nThis file type is not supported for preview.',
        'preview.too_large': '\n\n... (File too large, showing first 50000 characters only)',
        
        # Units
        'size.bytes': '{} B',
        'size.kb': '{:.1f} KB',
        'size.mb': '{:.1f} MB',
        'size.gb': '{:.2f} GB',
        
        # File types
        'type.folder': 'Folder',
        'type.file': 'File',
        'type.volume': 'Volume',
        
        # Welcome guide
        'welcome.title': 'Welcome to HFSExplorer',
        'welcome.message': '''Welcome to HFSExplorer!

This is a tool for browsing and extracting HFS+/HFSX file system contents.

Quick Start:
1. Click "Open" button to select a DMG/IMG image file
2. Or click "Device" button to open a physical disk
3. Browse files and extract what you need

Keyboard Shortcuts:
- Ctrl+O: Open file
- Ctrl+D: Open device
- Ctrl+F: Search
- Ctrl+E: Extract files
- F1: Help

Click "OK" to start.''',
    }
}


def set_language(language: str):
    """
    设置语言
    
    Args:
        language: 语言代码 ('zh' 或 'en')
    """
    global _current_language
    if language in TRANSLATIONS:
        _current_language = language


def get_language() -> str:
    """获取当前语言"""
    return _current_language


def t(key: str, *args) -> str:
    """
    获取翻译文本
    
    Args:
        key: 翻译键
        *args: 格式化参数
    
    Returns:
        翻译后的文本
    """
    # 获取翻译
    translations = TRANSLATIONS.get(_current_language, TRANSLATIONS['en'])
    text = translations.get(key, key)
    
    # 格式化
    if args:
        try:
            return text.format(*args)
        except:
            return text
    
    return text


def get_available_languages() -> Dict[str, str]:
    """获取可用语言"""
    return {
        'zh': '中文',
        'en': 'English',
    }
