# HFSExplorer 项目审查报告

审查日期：2026-07-09
更新日期：2026-07-09 (最新修复)

## 结论

项目已完成第一阶段和第二阶段的核心修复。Catalog 解析按 TN1150 规范修复，文件提取功能已实现，GUI 可以正常启动。当前状态为 **Alpha 只读 HFS+/HFSX 浏览器**。

---

## 已修复问题

### 1. 核心 Catalog 解析 ✅ 已修复

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| B-tree 偏移表顺序错误 | `src/core/hfs/btree.py:459-488` | ✅ 已修复 |
| Catalog 名称忽略 HFSUniStr255.length | `src/core/hfs/btree.py:796` | ✅ 已修复 |
| 文件夹记录格式错误 | `src/core/hfs/btree.py:853-903` | ✅ 已修复 (88 bytes) |
| 文件记录格式错误 | `src/core/hfs/btree.py:960-1022` | ✅ 已修复 (248 bytes) |

### 2. GUI 目录浏览 ✅ 已修复

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| Catalog 初始化为 pass | `src/gui/main_window.py:60-95` | ✅ 使用 HFSPlusVolume |
| 目录加载使用偏移 0 | `src/gui/main_window.py:98-120` | ✅ 使用 HFSPlusVolume |
| B-tree 节点大小错误 | 移除 node_size 参数 | ✅ 从 B-tree 头记录读取 |

### 3. 文件读取和提取 ✅ 已修复

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| _read_file_data 返回空字节 | `src/core/hfs/extractor.py:154-181` | ✅ 使用 HFSPlusFileReader |
| 提取按钮"功能待实现" | `src/gui/main_window.py:782-786` | ✅ 已实现文件提取功能 |
| 向上导航功能缺失 | `src/gui/main_window.py` | ✅ 已实现向上导航 |
| 搜索结果路径为空 | `src/core/hfs/search.py` | ✅ 已实现路径构建 |
| 信息面板数据未接通 | `src/gui/panels/info_panels.py` | ✅ 已实现字典数据接口 |

### 4. 写入功能 ✅ 已禁用

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| 写入模块公开导出 | `src/core/hfs/__init__.py:123-125` | ✅ 只导出 WriteError |

### 5. Unicode 比较 ✅ 已实现

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| 原始字节比较 | `src/core/hfs/btree.py:35-108` | ✅ NFD + casefold |
| Catalog key 比较 | `src/core/hfs/btree.py:110-145` | ✅ parentID + nodeName |
| Extent key 比较 | `src/core/hfs/btree.py:148-175` | ✅ forkType + fileID + startBlock |

### 6. Extents Overflow ✅ 已实现

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| 无 overflow 支持 | `src/core/hfs/btree.py:1226-1283` | ✅ get_extents_for_fork |

### 7. 版本和文档 ✅ 已修复

| 问题 | 修复位置 | 状态 |
|------|----------|------|
| 版本号 1.0.0 | `pyproject.toml`, `setup.py` | ✅ 0.1.0-alpha |
| README 声明未实现功能 | `README.md` | ✅ 已精简 |
| unhfs 入口不存在 | `pyproject.toml:43`, `setup.py:40` | ✅ 已移除 |

---

## 当前可用功能

```python
from src.core.hfs import HFSPlusVolume

with HFSPlusVolume("disk.img") as vol:
    info = vol.get_info()              # ✅ 卷信息
    contents = vol.list_folder(2)      # ✅ 列出根目录
    data = vol.read_file(file_id)      # ✅ 读取文件数据
    file_info = vol.get_file_info(id)  # ✅ 文件属性
```

---

## 仍缺失的功能

| 功能 | 优先级 | 位置 | 说明 |
|------|--------|------|------|
| 分区表解析 (APM/GPT/MBR) | P2 | `src/core/partition/` | 空模块 |
| DMG/UDIF 支持 | P2 | `src/core/dmg/` | 空模块 |
| FileVault 2 解密 | P1 | `src/core/crypto/` | 框架存在，密钥包返回空 |
| Catalog thread records | P2 | `src/core/hfs/btree.py` | 定义但未解析 |
| 叶节点循环检测 | P2 | `src/core/hfs/btree.py:624` | 损坏镜像可能无限循环 |
| CLI 工具 unhfs | P2 | `src/cli/` | 空模块 |

---

## 验证结果

- ✅ Python 语法编译检查通过
- ✅ 67 个测试全部通过
- ✅ GUI 可以正常启动 (offscreen 模式)
- ✅ deb 包构建成功 (104K)
- ✅ 核心模块导入成功

---

## 修复历史

| 提交 | 日期 | 内容 |
|------|------|------|
| `87ec61f` | 2026-07-09 | 按 TN1150 修复 Catalog 解析 |
| `a0efe78` | 2026-07-09 | 实现 Unicode 比较、Extents Overflow、HFSPlusVolume |
| `834aba8` | 2026-07-09 | 修复 HFSPlusVolume 初始化、文件提取器、GUI 集成 |
| `8951140` | 2026-07-09 | 修复 view_manager.py QHeaderView 导入 |

---

*最后更新：2026-07-09*
