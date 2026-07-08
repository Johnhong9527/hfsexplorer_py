@echo off
REM HFSExplorer Windows 构建脚本

echo ========================================
echo HFSExplorer 构建脚本
echo ========================================

REM 检查 Python 版本
python --version 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

REM 检查依赖
echo.
echo 检查依赖...
pip install -q pyinstaller
pip install -q -r requirements.txt

REM 运行测试
echo.
echo 运行测试...
python -m pytest tests/ -v --tb=short
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
pyinstaller ^
    --onefile ^
    --windowed ^
    --name HFSExplorer ^
    --add-data "resources;resources" ^
    --hidden-import PyQt6.QtWidgets ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import Crypto.Cipher.AES ^
    --hidden-import Crypto.Protocol.KDF ^
    --hidden-import src.core.hfs ^
    --hidden-import src.gui.main_window ^
    main.py

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