# HFSExplorer 编译指南

## Windows 编译

### 前提条件
- Python 3.9+ (https://www.python.org/downloads/)
- 安装时勾选 "Add Python to PATH"

### 编译步骤

```bash
# 1. 克隆项目
git clone https://github.com/Johnhong9527/hfsexplorer_py.git
cd hfsexplorer_py

# 2. 运行构建脚本（自动创建虚拟环境）
build.bat
```

或者手动编译：

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 4. 运行测试
python -m pytest tests/ -v

# 5. 编译
pyinstaller --onefile --windowed --name HFSExplorer --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import src.core.hfs --hidden-import src.gui.main_window main.py

# 6. 输出文件
dist\HFSExplorer.exe
```

### 清理

```bash
# 删除虚拟环境和构建文件
rmdir /s /q venv
rmdir /s /q build
rmdir /s /q dist
```

## Linux 编译

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 4. 编译
pyinstaller --onefile --windowed --name HFSExplorer --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import src.core.hfs --hidden-import src.gui.main_window main.py

# 5. 输出文件
dist/HFSExplorer
```

## 依赖说明

| 依赖 | 用途 |
|------|------|
| PyQt6 | GUI 框架 |
| pycryptodome | 加密库 |
| pyinstaller | 打包工具 |
| pytest | 测试框架 |

## 虚拟环境

- 虚拟环境目录：`venv/`
- 不会提交到 Git（已在 .gitignore 中排除）
- 删除项目时一起删除即可