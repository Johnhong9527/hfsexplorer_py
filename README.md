# HFSExplorer (Alpha)

一个独立的桌面应用程序，用于浏览和提取 HFS+/HFSX 文件系统内容。

> **当前状态**：Alpha 原型阶段，仅支持只读 HFS+/HFSX。写入功能、分区表、DMG、APFS、FileVault 2 等均未实现。

## 特性

- **跨平台**：支持 Windows 和 Linux
- **独立安装包**：不需要预先安装 Java 或其他运行时
- **只读 HFS+/HFSX**：浏览和提取文件
- **访达体验**：类似 macOS Finder 的用户界面

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

## 已实现功能

- HFS+ / HFSX 卷头解析
- B-tree 遍历（Catalog、Extents）
- 目录浏览和文件提取
- 基础搜索功能

## 未实现功能

以下功能在代码中存在骨架或声明，但**尚未可用**：

- 文件创建、删除、重命名、修改
- 分区表解析（APM、GPT、MBR）
- DMG / UDIF / 稀疏镜像支持
- FileVault 2 加密卷解密
- APFS 支持
- HFS Classic 支持
- 命令行工具 `unhfs`

## 开发

### 运行测试

```bash
pytest
```

## 技术栈

- **Python 3.9+**
- **PyQt6**：GUI 框架
- **pycryptodome**：加密算法库
- **pytest**：测试框架

## 许可证

GPL-3.0 - 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 原 HFSExplorer 作者 Erik Larsson (Catacombae Software)
