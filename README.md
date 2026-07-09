# HFSExplorer (Alpha)

一个独立的桌面应用程序，用于浏览和提取 HFS+/HFSX 文件系统内容，支持基础写入操作。

> **当前状态**：Alpha 阶段。HFS+/HFSX 读取功能完整可用，写入功能有框架但未充分测试。分区表、DMG、APFS、FileVault 2 等尚未实现。

## 特性

- **跨平台**：支持 Windows 和 Linux
- **独立安装包**：不需要预先安装 Java 或其他运行时
- **HFS+/HFSX 读取**：浏览、搜索、提取文件
- **基础写入**：创建、删除、重命名文件和文件夹（框架已实现，未充分测试）
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
| B-tree 变异引擎 | 节点插入、删除、分裂、合并 |
| Catalog 写入器 | 创建/删除/重命名/移动文件和文件夹 |
| 文件数据写入器 | 块分配、Extent 管理、部分写入 |
| 加密算法库 | AES-XTS、AES Key Wrap、PBKDF2 |
| 打包构建 | PyInstaller、deb、AppImage |
| 分区表解析 | APM、GPT、MBR 自动检测和解析 |
| Catalog Thread 记录 | 通过 CNID 查找路径 |
| 叶节点循环检测 | 防止损坏镜像无限循环 |

### ⚠️ 框架已实现（未充分测试）

| 功能 | 说明 |
|------|------|
| 文件创建/删除 | B-tree 操作已实现，需要实际镜像测试 |
| 文件重命名/移动 | Catalog 操作已实现 |
| 文件内容写入 | 块级写入已实现 |
| FileVault 2 解密 | 加密算法已实现，密钥包解析不完整 |

### ❌ 尚未实现

| 功能 | 说明 |
|------|------|
| DMG 镜像支持 | UDIF、稀疏镜像 |
| APFS 支持 | Apple File System |
| HFS Classic 支持 | 旧版 HFS 文件系统 |
| 命令行工具 `unhfs` | CLI 批量操作 |
| 加密 DMG | CEncryptedEncoding |
| APFS 加密卷 | — |

## 开发

### 项目结构

```
hfsexplorer-rewrite/
├── src/
│   ├── core/               # 核心文件系统库
│   │   ├── hfs/           # HFS+/HFSX 解析和写入
│   │   ├── partition/     # 分区表解析（空）
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
├── tests/                 # 测试（67 个）
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
