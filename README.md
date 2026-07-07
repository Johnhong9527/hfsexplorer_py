# HFSExplorer 复刻版本

一个独立的桌面应用程序，用于浏览和提取 HFS/HFS+/HFSX 文件系统内容，支持读写操作和 FileVault 2 加密。

## 特性

- **跨平台**：支持 Windows 和 Linux
- **独立安装包**：不需要预先安装 Java 或其他运行时
- **完整功能**：保留原 HFSExplorer 所有功能
- **读写支持**：支持创建、删除、修改文件和文件夹
- **访达体验**：类似 macOS Finder 的用户界面
- **加密支持**：支持 FileVault 2 加密卷（输入密码解密）

## 安装

### 从源代码安装

```bash
# 克隆仓库
git clone https://github.com/hfsexplorer/hfsexplorer.git
cd hfsexplorer

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt

# 安装项目
pip install -e .
```

### 使用预编译包

下载对应平台的安装包：
- Windows: `hfsexplorer-windows-setup.exe`
- Linux: `hfsexplorer-linux.AppImage`

## 使用

### 图形界面

```bash
hfsexplorer
```

### 命令行工具

```bash
# 提取 HFS 文件系统内容
unhfs /path/to/disk.img /output/dir

# 查看帮助
unhfs --help
```

## 功能

### 文件系统支持
- HFS (Hierarchical File System)
- HFS+ (Mac OS Extended)
- HFSX (Mac OS Extended, Case-sensitive)
- APFS (Apple File System) - 只读

### 磁盘镜像支持
- DMG (Apple Disk Image)
- UDIF (Universal Disk Image Format)
- 稀疏镜像 (Sparse Image)
- 原始磁盘镜像 (Raw Disk Image)

### 分区表支持
- Apple Partition Map (APM)
- GUID Partition Table (GPT)
- Master Boot Record (MBR)

### 加密支持
- 加密 DMG 镜像 (CEncryptedEncoding)
- FileVault 2 全盘加密 (CoreStorage)
- APFS 加密卷

### 文件操作
- 浏览文件和文件夹
- 提取文件到本地系统
- 创建新文件和文件夹
- 删除文件和文件夹
- 重命名文件和文件夹
- 修改文件内容
- 查看文件属性

## 开发

### 项目结构

```
hfsexplorer-rewrite/
├── src/
│   ├── core/               # 核心文件系统库
│   │   ├── hfs/           # HFS/HFS+/HFSX 解析
│   │   ├── partition/     # 分区表解析
│   │   ├── dmg/           # DMG 支持
│   │   └── utils/         # 工具函数
│   ├── gui/               # GUI 组件
│   │   ├── main_window.py
│   │   ├── browser.py
│   │   ├── panels/
│   │   └── dialogs/
│   ├── cli/               # 命令行工具
│   └── platform/          # 平台特定代码
├── resources/             # 图标、资源文件
├── tests/                 # 测试
├── build/                 # 构建脚本
└── dist/                  # 打包输出
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行带覆盖率的测试
pytest --cov=src

# 运行特定测试文件
pytest tests/test_hfs.py
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

### 构建安装包

```bash
# Windows
pyinstaller --onefile --windowed src/gui/main_window.py

# Linux
pyinstaller --onefile src/gui/main_window.py
```

## 技术栈

- **Python 3.9+**：主要编程语言
- **PyQt6**：跨平台 GUI 框架
- **pycryptodome**：加密算法库
- **PyInstaller**：打包工具
- **pytest**：测试框架

## 许可证

本项目采用 GPL-3.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 原 HFSExplorer 作者 Erik Larsson (Catacombae Software)
- libfvde 项目 (CoreStorage 支持)
- apfs-fuse 项目 (APFS 支持)

## 支持

- 问题报告：[GitHub Issues](https://github.com/hfsexplorer/hfsexplorer/issues)
- 文档：[项目文档](https://hfsexplorer.readthedocs.io)