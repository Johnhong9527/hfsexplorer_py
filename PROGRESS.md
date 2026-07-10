# HFSExplorer 开发进度

## 项目状态
- **开始时间**：2026年7月7日
- **当前阶段**：Alpha 读写浏览器
- **总体进度**：~50%

---

## 当前可用功能

### ✅ 已实现（基本可用）

| 模块 | 功能 | 说明 |
|------|------|------|
| **核心解析** | HFS+ / HFSX 卷头解析 | 完整支持 |
| **核心解析** | B-tree 遍历 | Catalog、Extents Overflow |
| **核心解析** | Unicode 比较 | FastUnicodeCompare 算法（参考 Java 版本） |
| **核心解析** | Catalog Thread 记录 | 通过 CNID 查找路径 |
| **核心解析** | 叶节点循环检测 | 防止损坏镜像无限循环 |
| **核心解析** | Fork Filter | 文件分支流式读取（参考 Java 版本） |
| **分区表** | APM 解析 | Apple Partition Map |
| **分区表** | GPT 解析 | GUID Partition Table |
| **分区表** | MBR 解析 | Master Boot Record |
| **分区表** | EBR 解析 | Extended Boot Record |
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
| **GUI** | 文件预览 | 空格键快速预览文本文件 |
| **写入** | B-tree 变异引擎 | 节点插入、删除、分裂、合并 |
| **写入** | Catalog 写入器 | 创建文件/文件夹（含线程记录） |
| **写入** | 分配位图管理 | 空闲块查找和分配 |
| **写入** | 数据结构序列化 | to_bytes 方法 |
| **写入** | HFS+ 格式化 | 创建新的 HFS+ 文件系统 |

### ✅ 已实现（基本可用）

| 功能 | 说明 |
|------|------|
| 文件内容写入 | 块级写入已实现 |
| FileVault 2 解密 | 加密算法已实现，密钥包解析完整 |

### ❌ 尚未实现

| 功能 | 优先级 | 说明 |
|------|--------|------|
| APFS 完整支持 | P1 | 需要完善加密、快照等高级特性 |
| HFS Classic 支持 | P3 | 旧版 HFS 文件系统 |
| 文件标签 | P3 | 支持文件标签功能 |
| 智能文件夹 | P3 | 支持智能文件夹功能 |
| 压缩/解压缩 | P3 | 支持压缩/解压缩功能 |

### ✅ 新增：DMG/UDIF 镜像支持

| 功能 | 说明 |
|------|------|
| koly 块解析 | UDIF Trailer 解析 |
| 块映射表 | 支持 RAW、ZERO、压缩块 |
| 分区读取 | 支持读取 DMG 分区数据 |
| 稀疏镜像 | 稀疏镜像基础支持 |
| 测试覆盖 | 13 个单元测试，100% 通过 |

### ✅ 新增：命令行工具 unhfs

| 功能 | 说明 |
|------|------|
| 文件列表 | 支持列出 HFS+ 卷中的文件 |
| 文件提取 | 支持提取单个文件和整个目录 |
| 递归操作 | 支持递归列出和提取 |
| 路径解析 | 支持卷内路径解析 |
| 测试覆盖 | 14 个单元测试，100% 通过 |

### ✅ 新增：APFS 支持（P1）

| 功能 | 说明 |
|------|------|
| APFS 数据结构 | 容器超级块、卷超级块、B-tree 节点、目录条目等 |
| APFS 读取器 | 支持打开 APFS 镜像文件，解析容器和卷 |
| 容器管理 | 读取容器信息，列出卷 |
| 卷管理 | 读取卷信息，浏览目录，读取文件数据 |
| 对象映射 | 支持虚拟对象 ID 到物理地址的映射 |
| 测试覆盖 | 15 个单元测试，100% 通过 |

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
8. formatter.py 叶节点偏移表计算错误 - 已修复
9. hfs_unicode_compare 无限循环 - 已修复
10. btree_mutator.py _delete_from_node 未实现 - 已修复
11. btree_mutator.py 使用字节比较而非 HFS+ Unicode 比较 - 已修复
12. writer.py 缺少线程记录创建 - 已修复
13. test_write_integration.py 叶节点缺少偏移表 - 已修复

### 新增功能
1. Catalog Thread 记录解析
2. 路径构建（通过 CNID 查找完整路径）
3. 叶节点循环检测（防止损坏镜像无限循环）
4. 分区表解析（APM、GPT、MBR、EBR）
5. HFS+ 分区自动检测
6. B-tree 变异引擎（插入、删除、分裂、合并）
7. Catalog 写入器（创建文件/文件夹，含线程记录）
8. 分配位图管理
9. CatalogKey/CatalogFolder/CatalogFile 序列化方法
10. GUI 增删改集成（新建、删除、重命名文件/文件夹）
11. Fork Filter（参考 Java 版本，流式读取文件分支）
12. FastUnicodeCompare 算法（参考 Java 版本，使用 Apple TN1150 的 lower case 表）
13. 搜索引擎路径构建（使用线程记录递归构建完整路径）

---

## 测试状态

- **测试总数**：402 个
- **通过率**：100%
- **测试模块**：
  - `test_btree.py` - B-tree 基础结构测试
  - `test_hfs_volume_header.py` - 卷头解析测试
  - `test_full.py` - 完整功能测试
  - `test_partition.py` - 分区表解析测试
  - `test_writer.py` - 写入功能测试
  - `test_write_integration.py` - 写入集成测试
  - `test_formatter.py` - 格式化功能测试
  - `test_search.py` - 搜索功能测试
  - `test_dmg.py` - DMG 镜像测试
  - `test_e2e_flow.py` - 端到端流程测试
  - `test_new_modules.py` - 新模块测试
  - `test_apfs.py` - APFS 模块测试
  - `test_apfs_integration.py` - APFS 集成测试
  - `test_filevault2.py` - FileVault 2 解密测试
  - `test_dmg_support.py` - DMG/UDIF 镜像支持测试
  - `test_unhfs.py` - unhfs 命令行工具测试

---

## 代码统计

| 文件 | 说明 |
|------|------|
| `src/core/hfs/btree.py` | B-tree 核心（~1300 行） |
| `src/core/hfs/btree_mutator.py` | B-tree 变异引擎（~1100 行） |
| `src/core/hfs/writer.py` | 写入器（~500 行） |
| `src/core/hfs/reader.py` | 读取器（~450 行） |
| `src/core/hfs/fork_filter.py` | Fork 过滤器（~300 行） |
| `src/core/hfs/fast_unicode_compare.py` | FastUnicodeCompare（~300 行） |
| `src/core/hfs/search.py` | 搜索引擎（~250 行） |
| `src/core/partition/__init__.py` | 分区表解析（~400 行） |
| `src/gui/main_window.py` | GUI 主窗口（~1200 行） |
| `src/core/apfs/__init__.py` | APFS 模块入口（~80 行） |
| `src/core/apfs/structures.py` | APFS 数据结构（~400 行） |
| `src/core/apfs/reader.py` | APFS 读取器（~350 行） |
| `src/core/apfs/container.py` | APFS 容器管理（~100 行） |
| `src/core/apfs/volume.py` | APFS 卷管理（~250 行） |

---

## 新增功能：访达级文件操作

### ✅ 已实现

| 功能 | 说明 |
|------|------|
| 复制/粘贴/剪切 | 支持 Ctrl+C/X/V 快捷键 |
| 复制到此处 | 支持 Ctrl+Shift+D 快捷键 |
| 移动到特殊文件夹 | 支持移动到桌面、文稿、下载等 |
| 移动到选择的文件夹 | 支持选择任意目标文件夹 |
| 剪贴板管理器 | 管理复制/剪切操作 |
| 批量操作 | 支持多选文件进行批量操作 |
| 右键菜单增强 | 添加编辑、移动等子菜单 |
| 确认对话框 | 所有破坏性操作都有确认对话框 |
| 错误处理 | 完善的错误处理和用户提示 |

### ✅ 新增：APFS 写入支持（完整实现）

| 功能 | 说明 |
|------|------|
| 块分配 | 集成 SpaceManager 进行位图管理 |
| B-tree 目录管理 | 使用 BTreeManager 管理目录树 |
| 创建文件 | 创建 inode + 目录条目 + 文件数据块 |
| 创建目录 | 创建 inode + 目录条目 |
| 删除操作 | 删除目录条目 + 释放数据块 + 更新 inode |
| 重命名操作 | 更新目录条目名称 |
| 移动操作 | 从旧目录删除 + 在新目录创建条目 |
| 复制操作 | 复制文件/目录及其内容 |
| 文件数据读写 | 正确分配和写入文件扩展 |
| 测试覆盖 | 27 个单元测试，100% 通过 |

---

## 下一步计划

1. ✅ 完善 FileVault 2 解密功能
2. ✅ 实现 DMG/UDIF 镜像支持
3. ✅ 实现命令行工具 unhfs
4. ✅ 实现复制/粘贴/剪切功能
5. ✅ 实现移动功能
6. ✅ 完善 APFS 写入支持
7. 实现 HFS Classic 支持（旧版 HFS 文件系统）
8. 实现文件标签功能
9. 实现智能文件夹功能
10. 实现压缩/解压缩功能
11. 实现跨平台打包（Windows 安装程序、AppImage、.deb/.rpm 包）

---

*最后更新：2026-07-10 16:30*
