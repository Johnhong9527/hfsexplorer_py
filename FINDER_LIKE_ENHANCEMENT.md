# HFSExplorer 访达级增强计划

## 目标
实现与 macOS 访达（Finder）完全一致的文件管理体验，支持所有 macOS 硬盘文件系统（HFS+、HFSX、APFS、HFS Classic）的完整读写操作。

## 功能清单

### 1. 核心文件操作 ✅ 已实现 / 🔄 需增强 / ❌ 需新增

| 功能 | 状态 | 说明 |
|------|------|------|
| 打开文件/文件夹 | ✅ | 双击打开 |
| 新建文件夹 | ✅ | Cmd+Shift+N |
| 新建文件 | ✅ | Cmd+N |
| 删除项目 | ✅ | Cmd+Delete |
| 重命名项目 | ✅ | Enter 键 |
| 移动项目 | 🔄 | 需要完善拖放和剪切粘贴 |
| 复制项目 | ❌ | 需要实现 |
| 粘贴项目 | ❌ | 需要实现 |
| 剪切项目 | ❌ | 需要实现 |
| 复制到剪贴板 | ❌ | 需要实现 |
| 从剪贴板粘贴 | ❌ | 需要实现 |

### 2. 视图功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 图标视图 | ✅ | 已实现 |
| 列表视图 | ✅ | 已实现 |
| 分栏视图 | ✅ | 已实现 |
| 画廊视图 | ✅ | 已实现 |
| 排序选项 | 🔄 | 需要增强 |
| 显示隐藏文件 | ❌ | 需要实现 |
| 显示路径栏 | ❌ | 需要实现 |
| 显示状态栏 | ❌ | 需要实现 |

### 3. 搜索功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 按名称搜索 | ✅ | 已实现 |
| 按内容搜索 | ❌ | 需要实现 |
| 按日期搜索 | ❌ | 需要实现 |
| 按大小搜索 | ❌ | 需要实现 |
| 按类型搜索 | ❌ | 需要实现 |

### 4. 文件预览

| 功能 | 状态 | 说明 |
|------|------|------|
| 快速预览 | 🔄 | 需要增强 |
| 文本文件预览 | ✅ | 已实现 |
| 图片预览 | ❌ | 需要实现 |
| PDF 预览 | ❌ | 需要实现 |
| 音频/视频预览 | ❌ | 需要实现 |

### 5. 文件系统支持

| 文件系统 | 读取 | 写入 | 状态 |
|----------|------|------|------|
| HFS+ | ✅ | ✅ | 完整支持 |
| HFSX | ✅ | ✅ | 完整支持 |
| APFS | 🔄 | ❌ | 需要增强 |
| HFS Classic | 🔄 | ❌ | 需要增强 |
| Core Storage | ❌ | ❌ | 需要实现 |

### 6. 高级功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 文件标签 | ❌ | 需要实现 |
| 智能文件夹 | ❌ | 需要实现 |
| 压缩/解压缩 | ❌ | 需要实现 |
| 磁盘工具 | ❌ | 需要实现 |
| 终端集成 | ❌ | 需要实现 |

## 实现计划

### 阶段 1：核心文件操作增强（1-2天）
1. 实现复制/粘贴/剪切功能
2. 完善拖放支持
3. 实现批量操作
4. 添加剪贴板支持

### 阶段 2：视图增强（1天）
1. 实现显示隐藏文件
2. 添加路径栏
3. 增强排序选项
4. 实现状态栏

### 阶段 3：搜索增强（1天）
1. 实现按内容搜索
2. 实现按日期搜索
3. 实现按大小搜索
4. 实现按类型搜索

### 阶段 4：文件预览增强（1-2天）
1. 实现图片预览
2. 实现 PDF 预览
3. 实现音频/视频预览
4. 增强快速预览功能

### 阶段 5：文件系统增强（2-3天）
1. 完善 APFS 支持
2. 完善 HFS Classic 支持
3. 实现 Core Storage 支持

### 阶段 6：高级功能（3-5天）
1. 实现文件标签
2. 实现智能文件夹
3. 实现压缩/解压缩
4. 实现磁盘工具

## 技术实现

### 复制/粘贴/剪切实现

```python
class ClipboardManager:
    """剪贴板管理器"""
    
    def __init__(self):
        self.clipboard = QApplication.clipboard()
        self.file_paths = []
        self.operation = None  # 'copy' or 'cut'
    
    def copy(self, file_paths: List[str]):
        """复制到剪贴板"""
        self.file_paths = file_paths
        self.operation = 'copy'
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(p) for p in file_paths])
        self.clipboard.setMimeData(mime_data)
    
    def cut(self, file_paths: List[str]):
        """剪切到剪贴板"""
        self.file_paths = file_paths
        self.operation = 'cut'
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(p) for p in file_paths])
        self.clipboard.setMimeData(mime_data)
    
    def paste(self, target_dir: str):
        """粘贴"""
        if not self.file_paths:
            return
        
        for file_path in self.file_paths:
            if self.operation == 'copy':
                self._copy_file(file_path, target_dir)
            elif self.operation == 'cut':
                self._move_file(file_path, target_dir)
        
        if self.operation == 'cut':
            self.file_paths = []
            self.operation = None
    
    def _copy_file(self, src: str, dst_dir: str):
        """复制文件"""
        # 实现文件复制逻辑
        pass
    
    def _move_file(self, src: str, dst_dir: str):
        """移动文件"""
        # 实现文件移动逻辑
        pass
```

### 拖放实现

```python
class DragDropManager:
    """拖放管理器"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """放下事件"""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            # 处理拖入的文件
            self._handle_dropped_file(file_path)
    
    def _handle_dropped_file(self, file_path: str):
        """处理拖入的文件"""
        # 实现拖入文件处理逻辑
        pass
```

### 批量操作实现

```python
class BatchOperationManager:
    """批量操作管理器"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.selected_items = []
    
    def select_all(self):
        """全选"""
        # 实现全选逻辑
        pass
    
    def deselect_all(self):
        """取消全选"""
        # 实现取消全选逻辑
        pass
    
    def invert_selection(self):
        """反选"""
        # 实现反选逻辑
        pass
    
    def batch_delete(self):
        """批量删除"""
        # 实现批量删除逻辑
        pass
    
    def batch_move(self, target_dir: str):
        """批量移动"""
        # 实现批量移动逻辑
        pass
    
    def batch_copy(self, target_dir: str):
        """批量复制"""
        # 实现批量复制逻辑
        pass
```

## 测试计划

### 单元测试
1. 复制/粘贴/剪切功能测试
2. 拖放功能测试
3. 批量操作测试
4. 剪贴板管理测试

### 集成测试
1. 文件操作完整性测试
2. 视图切换测试
3. 搜索功能测试
4. 文件预览测试

### 端到端测试
1. 完整工作流程测试
2. 边界条件测试
3. 错误处理测试
4. 性能测试

## 文档更新

1. 更新 README.md
2. 更新用户手册
3. 更新 API 文档
4. 更新开发文档

## 里程碑

- **v0.2.0**：核心文件操作增强
- **v0.3.0**：视图和搜索增强
- **v0.4.0**：文件预览增强
- **v0.5.0**：文件系统增强
- **v1.0.0**：完整访达级功能
