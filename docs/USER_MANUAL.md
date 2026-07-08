# HFSExplorer 用户手册

## 简介

HFSExplorer 是一个用于浏览和提取 HFS/HFS+/HFSX 文件系统内容的工具。本软件是原 HFSExplorer 的复刻版本，去除了 Java 依赖，运行在 Windows 和 Linux 上。

## 功能特性

### 文件系统支持
- **HFS** (Hierarchical File System)
- **HFS+** (Mac OS Extended)
- **HFSX** (Mac OS Extended, Case-sensitive)
- **APFS** (Apple File System) - 只读

### 磁盘镜像支持
- **DMG** (Apple Disk Image)
- **UDIF** (Universal Disk Image Format)
- **稀疏镜像** (Sparse Image)
- **原始磁盘镜像** (Raw Disk Image)

### 分区表支持
- **Apple Partition Map** (APM)
- **GUID Partition Table** (GPT)
- **Master Boot Record** (MBR)

### 加密支持
- **加密 DMG 镜像** (CEncryptedEncoding)
- **FileVault 2 全盘加密** (CoreStorage)
- **APFS 加密卷**

## 安装

### Windows

1. 下载 `HFSExplorer-windows.zip`
2. 解压到任意目录
3. 运行 `HFSExplorer.exe`

### Linux

1. 下载 `HFSExplorer-linux.AppImage`
2. 添加执行权限：`chmod +x HFSExplorer-linux.AppImage`
3. 运行：`./HFSExplorer-linux.AppImage`

### 从源代码运行

```bash
# 克隆仓库
git clone https://github.com/Johnhong9527/hfsexplorer_py.git
cd hfsexplorer_py

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 使用指南

### 打开文件或设备

1. 点击 **文件 > 打开** 或工具栏上的 **打开** 按钮
2. 选择 HFS 磁盘镜像文件
3. 等待文件加载完成

### 浏览文件

- **目录树**：左侧显示目录结构
- **文件列表**：右侧显示当前文件夹内容
- **地址栏**：可以输入路径直接导航
- **双击文件夹**：进入该文件夹
- **点击向上按钮**：返回上一级目录

### 视图模式

HFSExplorer 提供多种视图模式：

- **图标视图**：以图标形式显示文件
- **列表视图**：以列表形式显示详细信息
- **分栏视图**：以分栏形式显示层级结构
- **画廊视图**：以大图形式显示文件预览

切换视图：**工具 > 视图模式**

### 搜索文件

1. 点击 **工具 > 搜索** 或按 `Ctrl+F`
2. 输入搜索关键词
3. 选择匹配方式和过滤器
4. 点击 **搜索** 按钮

### 提取文件

1. 选择要提取的文件或文件夹
2. 点击 **文件 > 提取** 或工具栏上的 **提取** 按钮
3. 选择目标目录
4. 等待提取完成

### 查看文件信息

1. 选择文件或文件夹
2. 右键点击，选择 **属性**
3. 查看详细信息

### 查看卷信息

点击 **工具 > 卷信息** 或按 `Ctrl+I`

### 解锁加密卷

1. 打开加密的磁盘镜像
2. 在弹出的密码对话框中输入密码
3. 或者选择 **使用恢复密钥** 输入恢复密钥
4. 点击 **解锁** 按钮

### 拖放支持

可以直接将文件拖放到 HFSExplorer 窗口来打开。

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开文件 |
| `Ctrl+E` | 提取文件 |
| `Ctrl+F` | 搜索 |
| `Ctrl+I` | 卷信息 |
| `Ctrl+Q` | 退出 |
| `Backspace` | 向上导航 |
| `Delete` | 删除 |
| `F5` | 刷新 |
| `Ctrl+A` | 全选 |
| `Ctrl+C` | 复制 |
| `Ctrl+V` | 粘贴 |
| `Ctrl+X` | 剪切 |

## 命令行工具

### UnHFS

提取 HFS 文件系统内容。

```bash
python -m src.cli.unhfs [选项] <磁盘镜像> <输出目录>

选项:
  -h, --help     显示帮助信息
  -p, --password 指定密码
  -r, --recursive 递归提取
  -v, --verbose  详细输出
```

示例：
```bash
# 提取整个卷
python -m src.cli.unhfs disk.dmg output/

# 使用密码解密
python -m src.cli.unhfs -p password encrypted.dmg output/

# 递归提取
python -m src.cli.unhfs -r disk.dmg output/
```

## 常见问题

### Q: 无法打开某些 DMG 文件

A: 某些 DMG 文件可能使用了不支持的压缩格式或加密方式。请确保文件未损坏，并尝试使用其他工具转换格式。

### Q: 解密失败

A: 请检查密码是否正确。如果使用恢复密钥，请确保格式正确（24位字母数字，带连字符）。

### Q: 写入操作失败

A: 写入功能目前处于实验阶段，某些操作可能尚未完全实现。请确保目标卷有足够的空间，并备份重要数据。

### Q: 程序崩溃

A: 请尝试以下步骤：
1. 重启程序
2. 检查文件是否损坏
3. 更新到最新版本
4. 提交 Issue 并附上错误日志

## 技术支持

- **GitHub**: https://github.com/Johnhong9527/hfsexplorer_py
- **Issues**: https://github.com/Johnhong9527/hfsexplorer_py/issues

## 许可证

本项目采用 GPL-3.0 许可证。

## 致谢

- 原 HFSExplorer 作者 Erik Larsson (Catacombae Software)
- libfvde 项目 (CoreStorage 支持)
- apfs-fuse 项目 (APFS 支持)