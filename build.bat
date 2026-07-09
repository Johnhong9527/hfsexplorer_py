@echo off
REM HFSExplorer Windows 构建脚本 (使用虚拟环境)

echo ========================================
echo HFSExplorer Windows 构建脚本
echo ========================================

REM 检查 Python
python --version 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 创建虚拟环境
echo.
echo 创建虚拟环境...
if not exist venv (
    python -m venv venv
)

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo 安装依赖...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM 运行测试
echo.
echo 运行测试...
python -m pytest tests/ -v
if errorlevel 1 (
    echo 测试失败！
    pause
    exit /b 1
)

REM 清理旧的构建文件
echo.
echo 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 构建
echo.
echo 开始构建...
pyinstaller --onefile --windowed --name HFSExplorer --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import src.core.hfs --hidden-import src.gui.main_window main.py

if errorlevel 1 (
    echo 构建失败！
    pause
    exit /b 1
)

echo.
echo 构建完成！
echo 可执行文件: dist\HFSExplorer.exe
echo.
pause