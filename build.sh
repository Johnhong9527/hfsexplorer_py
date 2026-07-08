#!/bin/bash
# HFSExplorer 构建脚本

set -e

echo "========================================"
echo "HFSExplorer 构建脚本"
echo "========================================"

# 检查 Python 版本
python_version=$(python3 --version 2>&1)
echo "Python 版本: $python_version"

# 检查依赖
echo ""
echo "检查依赖..."
pip3 install -q pyinstaller
pip3 install -q -r requirements.txt

# 运行测试
echo ""
echo "运行测试..."
python3 -m pytest tests/ -v --tb=short

# 清理旧的构建文件
echo ""
echo "清理旧的构建文件..."
rm -rf build/ dist/

# 构建
echo ""
echo "开始构建..."

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux 构建
    echo "构建 Linux 版本..."
    pyinstaller \
        --onefile \
        --windowed \
        --name HFSExplorer \
        --add-data "resources:resources" \
        --hidden-import PyQt6.QtWidgets \
        --hidden-import PyQt6.QtCore \
        --hidden-import PyQt6.QtGui \
        --hidden-import Crypto.Cipher.AES \
        --hidden-import Crypto.Protocol.KDF \
        --hidden-import src.core.hfs \
        --hidden-import src.gui.main_window \
        main.py
    
    echo ""
    echo "构建完成！"
    echo "可执行文件: dist/HFSExplorer"
    
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows 构建
    echo "构建 Windows 版本..."
    pyinstaller \
        --onefile \
        --windowed \
        --name HFSExplorer \
        --add-data "resources;resources" \
        --hidden-import PyQt6.QtWidgets \
        --hidden-import PyQt6.QtCore \
        --hidden-import PyQt6.QtGui \
        --hidden-import Crypto.Cipher.AES \
        --hidden-import Crypto.Protocol.KDF \
        --hidden-import src.core.hfs \
        --hidden-import src.gui.main_window \
        main.py
    
    echo ""
    echo "构建完成！"
    echo "可执行文件: dist/HFSExplorer.exe"
    
else
    echo "不支持的操作系统: $OSTYPE"
    exit 1
fi

echo ""
echo "========================================"
echo "构建完成！"
echo "========================================"