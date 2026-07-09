# HFSExplorer 开发进度

## 项目状态
- **开始时间**：2026年7月7日
- **当前阶段**：Alpha 只读浏览器
- **总体进度**：~25%

---

## 当前可用功能

### ✅ 已实现（基本可用）
- [x] HFS+ 卷头解析
- [x] B-tree 基础遍历（Catalog、Extents）
- [x] Unicode 比较（NFD + casefold）
- [x] 目录树显示
- [x] 文件列表显示
- [x] GUI 主窗口框架
- [x] 文件提取功能
- [x] 搜索功能
- [x] 信息面板
- [x] 多种视图模式（图标、列表、分栏、画廊）
- [x] Catalog Thread 记录解析
- [x] 路径构建（通过 CNID）
- [x] 叶节点循环检测
- [x] 分区表解析（APM、GPT、MBR）
- [x] B-tree 变异引擎（插入、删除、分裂、合并）
- [x] Catalog 写入器（创建/删除文件和文件夹）
- [x] 分配位图管理
- [x] CatalogKey.to_bytes / CatalogFolder.to_bytes / CatalogFile.to_bytes

### ⚠️ 框架已实现（未充分测试）
- [ ] FileVault 2 解密（密钥包解析不完整）

### ❌ 尚未实现
- [ ] DMG/UDIF 镜像支持
- [ ] APFS 支持
- [ ] HFS Classic 支持
- [ ] 命令行工具 `unhfs`

---

## 已修复问题

### 核心功能修复
1. B-tree 偏移表顺序错误 - 已修复
2. Catalog 名称解析（HFSUniStr255.length）- 已修复
3. 文件夹/文件记录 struct 格式 - 已修复
4. 文件提取返回空字节 - 已修复
5. GUI 目录浏览 - 已修复

### 新增功能
1. Catalog Thread 记录解析
2. 路径构建（通过 CNID 查找完整路径）
3. 叶节点循环检测（防止损坏镜像无限循环）
4. 分区表解析（APM、GPT、MBR）
5. HFS+ 分区自动检测

---

## 测试状态

- **测试总数**：106 个
- **通过率**：100%
- **新增测试**：39 个（写入功能 + 分区表 + Catalog Thread）

---

## 下一步计划

1. 实现 DMG/UDIF 镜像支持
2. 完善 FileVault 2 解密功能
3. 实现命令行工具 `unhfs`
4. 添加 APFS 支持

---

*最后更新：2026-07-09*
