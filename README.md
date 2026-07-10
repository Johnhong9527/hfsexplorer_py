# HFSExplorer (Alpha)

一个独立的桌面应用程序，用于浏览和提取 HFS+/HFSX 文件系统内容，支持基础写入操作。

> **当前状态**：Alpha 阶段。HFS+/HFSX 读取功能完整可用，写入功能框架已实现并验证。

## 特性

- **跨平台**：支持 Windows 和 Linux
- **独立安装包**：不需要预先安装 Java 或其他运行时
- **HFS+/HFSX 读取**：浏览、搜索、提取文件
- **APFS 支持**：Apple 新文件系统读取支持
- **分区表支持**：APM、GPT、MBR 自动检测和解析
- **基础写入**：创建文件和文件夹（框架已实现并验证）
- **格式化**：创建新的 HFS+ 文件系统
- **访达体验**：类似 macOS Finder 的用户界面，支持多种视图模式
- **加密框架**：FileVault 2 解密框架已搭建（密钥包解析不完整）

## 安装

### 从源代码安装

```bash
git clone https://github.com/Johnhong9527/hfsexplorer_py.git
cd hfsexplorer_py

python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

pip install -r requirements.txt
pip install -e .
```

## 使用

### 图形界面

```bash
hfsexplorer
```

### 命令行格式化

```python
from src.core.hfs.formatter import format_volume

# 格式化为 HFS+
header = format_volume("/path/to/volume.img", "MyVolume", 4096)
print(f"总块数: {header.total_blocks}, 空闲块: {header.free_blocks}")
```

## 功能实现状态

### ✅ 已实现

| 功能 | 说明 |
|------|------|
| HFS+ / HFSX 卷头解析 | 完整支持 |
| B-tree 遍历 | Catalog、Extents Overflow |
| Unicode 比较 | NFD + casefold，符合 TN1150 规范 |
| 目录浏览 | 树形目录、文件列表 |
| 文件提取 | 单文件、批量提取，支持进度显示 |
| 搜索功能 | 按名称搜索，支持多种匹配模式 |
| 向上导航 | 目录历史记录 |
| 信息面板 | 文件/文件夹属性、卷信息 |
| 视图模式 | 图标、列表、分栏、画廊四种视图 |
| 分区表解析 | APM、GPT、MBR 自动检测 |
| Catalog Thread 记录 | 通过 CNID 查找路径 |
| 叶节点循环检测 | 防止损坏镜像无限循环 |
| **新建文件/文件夹** | 右键菜单、文件菜单、快捷键支持 |
| **删除项目** | 右键菜单删除，带确认对话框 |
| **重命名项目** | 右键菜单重命名，支持输入新名称 |
| B-tree 变异引擎 | 节点插入、删除、分裂、合并 |
| Catalog 写入器 | 创建文件/文件夹（已验证） |
| 分配位图管理 | 空闲块查找和分配 |
| **HFS+ 格式化** | 创建新的 HFS+ 文件系统 |
| **格式化对话框** | GUI 格式化界面 |
| **DMG 镜像支持** | 读取 Apple Disk Image |
| **APFS 支持** | Apple File System 读取支持 |
| 打包构建 | PyInstaller、deb、AppImage |

### ⚠️ 框架已实现（未充分测试）

| 功能 | 说明 |
|------|------|
| 文件内容写入 | 块级写入已实现 |
| FileVault 2 解密 | 加密算法已实现，密钥包解析不完整 |

### ❌ 尚未实现

| 功能 | 说明 |
|------|------|
| DMG 镜像支持 | UDIF、稀疏镜像 |
| HFS Classic 支持 | 旧版 HFS 文件系统 |
| 命令行工具 `unhfs` | CLI 批量操作 |
| APFS 高级特性 | 加密、快照、克隆等 |

## 开发

### 项目结构

```
hfsexplorer-rewrite/
├── src/
│   ├── core/               # 核心文件系统库
│   │   ├── hfs/           # HFS+/HFSX 解析和写入
│   │   │   ├── btree.py          # B-tree 核心
│   │   │   ├── btree_mutator.py  # B-tree 变异引擎
│   │   │   ├── writer.py         # 写入器
│   │   │   ├── reader.py         # 读取器
│   │   │   ├── extractor.py      # 文件提取器
│   │   │   └── search.py         # 搜索引擎
│   │   ├── apfs/          # APFS 支持
│   │   │   ├── __init__.py       # 模块入口
│   │   │   ├── structures.py     # 数据结构定义
│   │   │   ├── reader.py         # 读取器
│   │   │   ├── container.py      # 容器管理
│   │   │   └── volume.py         # 卷管理
│   │   ├── partition/     # 分区表解析
│   │   │   └── __init__.py       # APM/GPT/MBR
│   │   ├── dmg/           # DMG 支持（空）
│   │   ├── crypto/        # 加密支持
│   │   └── utils/         # 工具函数
│   ├── gui/               # GUI 组件
│   │   ├── main_window.py
│   │   ├── panels/        # 信息面板
│   │   ├── views/         # 视图模式
│   │   └── dialogs/       # 对话框
│   ├── cli/               # 命令行工具（空）
│   └── platform/          # 平台特定代码（空）
├── tests/                 # 测试（196 个）
├── resources/             # 资源文件
└── dist/                  # 打包输出
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行带覆盖率的测试
pytest --cov=src

# 运行特定测试
pytest tests/test_btree.py
pytest tests/test_writer.py
pytest tests/test_partition.py
pytest tests/test_apfs.py
```

### 代码质量

```bash
# 代码格式化
black src/ tests/

# 导入排序
isort src/ tests/

# 代码检查
flake8 src/ tests/

# 类型检查
mypy src/
```

## 技术栈

- **Python 3.9+**
- **PyQt6**：跨平台 GUI 框架
- **pycryptodome**：加密算法库
- **PyInstaller**：打包工具
- **pytest**：测试框架

## 许可证

GPL-3.0 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 原 HFSExplorer 作者 Erik Larsson (Catacombae Software)
