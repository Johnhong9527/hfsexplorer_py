#!/bin/bash
# HFSExplorer Windows 构建脚本 (使用 Docker + Wine)

set -e

echo "========================================"
echo "HFSExplorer Windows 构建脚本"
echo "========================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误: 未找到 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker 是否运行
if ! docker info &> /dev/null; then
    echo "错误: Docker 未运行"
    echo "请启动 Docker 服务"
    exit 1
fi

echo ""
echo "开始构建 Windows 版本..."
echo "这可能需要几分钟时间..."

# 构建 Docker 镜像
docker build -f Dockerfile.windows -t hfsexplorer-windows-builder .

# 创建输出目录
mkdir -p dist/windows

# 复制构建产物
docker create --name extract hfsexplorer-windows-builder
docker cp extract:/app/dist/HFSExplorer.exe ./dist/windows/
docker rm extract

echo ""
echo "========================================"
echo "构建完成！"
echo "可执行文件: dist/windows/HFSExplorer.exe"
echo "========================================"

# 显示文件信息
ls -lh dist/windows/HFSExplorer.exe