# HFSExplorer 开发进度

## 项目状态
- **开始时间**：2026年7月7日
- **当前阶段**：Alpha 读写浏览器
- **总体进度**：~45%

---

## 当前可用功能

### ✅ 已实现（基本可用）

| 模块 | 功能 | 说明 |
|------|------|------|
| **核心解析** | HFS+ / HFSX 卷头解析 | 完整支持 |
| **核心解析** | B-tree 遍历 | Catalog、Extents Overflow |
| **核心解析** | Unicode 比较 | NFD + casefold，符合 TN1150 规范 |
| **核心解析** | Catalog Thread 记录 | 通过 CNID 查找路径 |
| **核心解析** | 叶节点循环检测 | 防止损坏镜像无限循环 |
| **分区表** | APM 解析 | Apple Partition Map |
| **分区表** | GPT 解析 | GUID Partition Table |
| **分区表** | MBR 解析 | Master Boot Record |
| **分区表** | 自动检测 | 自动识别分区表类型 |
| **GUI** | 目录浏览 | 树形目录、文件列表 |
| **GUI** | 文件提取 | 单文件、批量提取，支持进度显示 |
| **GUI** | 搜索功能 | 按名称搜索，支持多种匹配模式 |
| **GUI** | 信息面板 | 文件/文件夹属性、卷信息 |
| **GUI** | 视图模式 | 图标、列表、分栏、画廊四种视图 |
| **GUI** | 分区选择 | 多分区镜像自动弹出选择对话框 |
| **GUI** | 新建文件/文件夹 | 右键菜单、文件菜单、快捷键支持 |
| **GUI** | 删除项目 | 右键菜单删除，带确认对话框 |
| **GUI** | 重命名项目 | 右键菜单重命名，支持输入新名称 |
| **写入** | B-tree 变异引擎 | 节点插入、删除、分裂、合并 |
| **写入** | Catalog 写入器 | 创建文件/文件夹 |
| **写入** | 分配位图管理 | 空闲块查找和分配 |
| **写入** | 数据结构序列化 | to_bytes 方法 |

### ⚠️ 框架已实现（未充分测试）

| 功能 | 说明 |
|------|------|
| 文件内容写入 | 块级写入已实现 |
| FileVault 2 解密 | 加密算法已实现，密钥包解析不完整 |

### ❌ 尚未实现

| 功能 | 优先级 | 说明 |
|------|--------|------|
| DMG/UDIF 镜像支持 | P2 | 稀疏镜像、压缩镜像 |
| APFS 支持 | P1 | Apple File System |
| HFS Classic 支持 | P3 | 旧版 HFS 文件系统 |
| 命令行工具 unhfs | P2 | CLI 批量操作 |

---

## 已修复问题

### 核心功能修复
1. B-tree 偏移表顺序错误 - 已修复
2. Catalog 名称解析（HFSUniStr255.length）- 已修复
3. 文件夹/文件记录 struct 格式 - 已修复
4. 文件提取返回空字节 - 已修复
5. GUI 目录浏览 - 已修复
6. HFSPlusCatalogFile.from_bytes 格式字符串 - 已修复
7. HFSPlusCatalogFolder.from_bytes 格式字符串 - 已修复

### 新增功能
1. Catalog Thread 记录解析
2. 路径构建（通过 CNID 查找完整路径）
3. 叶节点循环检测（防止损坏镜像无限循环）
4. 分区表解析（APM、GPT、MBR）
5. HFS+ 分区自动检测
6. B-tree 变异引擎（插入、删除、分裂、合并）
7. Catalog 写入器（创建文件/文件夹）
8. 分配位图管理
9. CatalogKey/CatalogFolder/CatalogFile 序列化方法
10. GUI 增删改集成（新建、删除、重命名文件/文件夹）

---

## 测试状态

- **测试总数**：106 个
- **通过率**：100%
- **测试模块**：
  - `test_btree.py` - B-tree 基础结构测试
  - `test_hfs_volume_header.py` - 卷头解析测试
  - `test_full.py` - 完整功能测试
  - `test_partition.py` - 分区表解析测试
  - `test_writer.py` - 写入功能测试
  - `test_write_integration.py` - 写入集成测试

---

## 代码统计

| 文件 | 说明 |
|------|------|
| `src/core/hfs/btree.py` | B-tree 核心（~1300 行） |
| `src/core/hfs/btree_mutator.py` | B-tree 变异引擎（~1100 行） |
| `src/core/hfs/writer.py` | 写入器（~500 行） |
| `src/core/hfs/reader.py` | 读取器（~450 行） |
| `src/core/partition/__init__.py` | 分区表解析（~400 行） |
| `src/gui/main_window.py` | GUI 主窗口（~1200 行） |

---

## 下一步计划

1. 实现 DMG/UDIF 镜像支持
2. 完善 FileVault 2 解密功能
3. 实现命令行工具 unhfs
4. 添加 APFS 支持

---

*最后更新：2026-07-09*
