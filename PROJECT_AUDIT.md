# HFSExplorer 项目审查报告

审查日期：2026-07-09

## 结论

项目目前属于“GUI 原型 + 部分 HFS+ 数据结构实验”，还不能作为可用的 HFSExplorer，也不适合启用写入功能。`PROGRESS.md` 中“100% 完成”的描述与实际代码严重不符。

## 严重问题

### 1. 核心 Catalog 解析无法处理真实 HFS+ 数据

- B-tree 偏移表顺序错误：`src/core/hfs/btree.py:298`
- Catalog 名称忽略 `HFSUniStr255.length` 字段：`src/core/hfs/btree.py:605`
- 文件夹和文件记录的结构格式、字段数量错误：
  - `src/core/hfs/btree.py:668`
  - `src/core/hfs/btree.py:746`

最小复现结果：

```text
Catalog 名称: '\x08test.txt'
Folder: ValueError too many values to unpack
File:   ValueError too many values to unpack
```

Apple TN1150 格式规范明确规定：

- 第一个记录的偏移位于 B-tree 节点最后两个字节。
- HFS+ 文件名使用 `HFSUniStr255`，包含独立的 16 位字符数量字段。

参考：

- <https://developer.apple.com/library/archive/technotes/tn/tn1150.html>

### 2. GUI 实际无法浏览目录

文件加载线程只读取卷头，Catalog 初始化部分直接使用 `pass`：

- `src/gui/main_window.py:65`

后续目录加载使用偏移 `0`，并把卷的分配块大小错误地当作 B-tree 节点大小：

- `src/gui/main_window.py:104`
- `src/gui/main_window.py:533`

因此，即使输入是合法的原始 HFS+ 卷，GUI 通常也无法找到或解析 Catalog B-tree。

### 3. 文件读取和提取没有实现

`FileExtractor._read_file_data()` 对非空文件仍然返回空字节：

- `src/core/hfs/extractor.py:154`

GUI 的提取按钮也只是显示“功能待实现”：

- `src/gui/main_window.py:760`

当前提取器还存在以下问题：

- 没有读取 Catalog 文件记录中的初始 extents。
- 没有处理 Extents Overflow。
- 没有处理 Resource Fork、压缩文件和符号链接。
- 没有对镜像内文件名进行安全清理，恶意名称可能造成输出路径逃逸。

### 4. 写入功能存在数据损坏风险

应立即禁用全部写入入口。

主要问题：

- Extent 更新、Catalog 更新、块释放等核心操作为空实现。
- 创建和删除接口可能没有修改 Catalog，却返回成功：
  - `src/core/hfs/file_writer.py:485`
  - `src/core/hfs/file_writer.py:525`
  - `src/core/hfs/file_writer.py:554`
  - `src/core/hfs/file_writer.py:582`
- 数据写入直接使用 `block_number * block_size`，没有经过文件 extent 映射，可能覆盖卷头、Catalog 或其他文件数据：
  - `src/core/hfs/file_writer.py:254`
- B-tree 节点写回、节点分配、节点释放和父节点维护没有实现：
  - `src/core/hfs/btree_mutator.py:814`

此外，`BTreeMutator` 使用了不存在的 `BTNodeDescriptor.STRUCT_SIZE`，相关路径会直接失败：

- `src/core/hfs/btree_mutator.py:279`
- `src/core/hfs/btree_mutator.py:437`

### 5. FileVault 仅有算法框架

CoreStorage 密钥包读取固定返回空数据：

- `src/core/crypto/encrypted_volume.py:388`

GUI 也明确提示解密功能尚未完成：

- `src/gui/main_window.py:405`

因此当前实现不能完成真实 FileVault 2 卷的元数据解析、密钥解包和透明逻辑卷映射。

## 底层实现问题

### B-tree

- 节点偏移表顺序与磁盘格式相反。
- 没有验证偏移单调性、范围、记录大小或节点类型。
- 叶节点链表遍历没有检测循环，损坏镜像可能导致无限循环。
- B-tree 文件被当作连续磁盘区域处理，无法读取分段的特殊文件 fork。
- 查找过程直接比较原始 key 字节，没有实现 HFS+ Unicode 归一化和大小写折叠规则。
- 初始节点大小依赖外部传入，GUI 错误地使用卷分配块大小。

### Catalog

- Catalog key 缺少名称长度字段解析。
- 文件记录缺少 `reserved1`，后续字段偏移不正确。
- 文件夹和文件记录的 `struct` 格式会产生字段数量不匹配异常。
- 没有实现文件和文件夹 thread record。
- 没有实现 CNID 到完整路径的可靠反向解析。

### Extents

- 文件记录没有保留完整的 `HFSPlusForkData`，只读取大小和块数。
- 文件读取器固定返回空内容。
- Extents Overflow 的 `startBlock` 计算逻辑不正确。
- 没有为 Catalog、Extents、Attributes 等特殊文件提供逻辑 fork 流。

### 卷识别

卷头读取器只检查偏移 1024 处的 HFS+/HFSX 签名：

- `src/core/hfs/reader.py:49`

它不支持：

- HFS wrapper 中嵌入的 HFS+ 卷。
- GPT、MBR、APM 分区内的 HFS+ 卷。
- DMG、UDIF、Sparse Image。
- 物理设备中的分区偏移。

卷头验证也只检查签名，没有验证版本、块大小、块数量和文件长度。

## 声明但未实现的功能

以下模块为空：

- `src/core/dmg/__init__.py`
- `src/core/partition/__init__.py`
- `src/core/utils/__init__.py`
- `src/platform/__init__.py`
- `src/cli/__init__.py`

README 声明但代码中没有相应实现的功能包括：

- HFS Classic
- APFS
- DMG/UDIF/Sparse Image
- APM/GPT/MBR
- 加密 DMG
- APFS 加密
- 完整文件提取
- 文件创建、删除、重命名和内容修改
- 完整 FileVault 2 解密

`unhfs` 安装入口指向不存在的模块：

- `pyproject.toml:41`
- `setup.py:37`

执行 `unhfs` 会因为缺少 `src.cli.unhfs` 而失败。

## GUI 问题

尚未实现或未接通的功能包括：

- Catalog 初始化。
- 文件提取。
- 向上导航。
- 文件和文件夹完整属性加载。
- 文件预览。
- 子项目加载。
- FileVault 解密后的数据流接入。
- 写入功能接入。

搜索功能虽然存在代码，但：

- Catalog 本身无法正确加载。
- 搜索结果的完整路径固定为空。
- 未识别的 Catalog 记录会被错误标记为文件夹。
- 正则表达式错误不会反馈给用户。

## 测试问题

仓库中有 67 个测试函数。通过轻量测试驱动器执行后为：

```text
passed=67 failed=0
```

但是这些测试主要验证：

- 常量值。
- 数据类属性。
- 人工构造的内存字节。
- 基础加密参数校验。

测试数据本身按照当前错误实现构造，例如：

- `tests/test_btree.py:205`
- `tests/test_full.py:397`

因此出现了“测试和实现共同违反磁盘格式，但测试仍通过”的情况。

当前缺少：

- 真实 HFS+/HFSX 镜像测试。
- HFS wrapper 测试。
- 分区镜像测试。
- 多 extent 和碎片化文件测试。
- 文件内容提取及哈希校验。
- Catalog Unicode 和大小写排序测试。
- 损坏镜像、循环链表和越界数据测试。
- 写入后重新挂载及一致性检查。
- FileVault 真实样本测试。
- GUI 和 CLI 集成测试。

## 工程和发布问题

- `PROGRESS.md` 宣称 100% 完成，但 `IMPLEMENTATION_PLAN.md` 仍标记约 5%。
- 源码中统计到约 90 处明确的 TODO、`pass`、“尚未实现”或占位说明。
- README、包元数据和实际 GitHub 地址不一致。
- `setup.py` 与 `pyproject.toml` 重复维护包配置，容易发生漂移。
- `requirements.txt` 同时安装 `pycryptodome` 和 `pycryptodomex`，没有明确统一导入策略。
- 运行依赖、开发依赖和打包依赖混杂。
- CI 只执行当前低覆盖率测试，没有 lint、类型检查、真实镜像测试或产物启动检查。
- 文档宣称已有安装包，但仓库没有可以证明发布产物可用的自动验收。

## 本次验证结果

- 工作区在审查前后均无受版本控制的改动。
- Python 语法编译检查通过。
- 67 个现有测试函数通过轻量测试驱动器执行。
- 当前环境没有安装 `pytest`、`mypy`、`flake8`、`PyQt6` 或 `pycryptodome`，因此没有执行正式 pytest、类型检查、GUI 启动和加密向量测试。
- 已通过最小复现确认：
  - B-tree 偏移表无法解析规范格式。
  - Catalog 名称解析包含错误的长度字符。
  - Catalog 文件和文件夹记录会抛出字段解包异常。

## 建议修复顺序

### 第一阶段：收缩范围并保证安全

1. 禁用或删除全部写入入口。
2. 把版本状态恢复为 Alpha/Prototype。
3. 删除 README 中尚未实现的功能声明。
4. 先明确只支持“只读 HFS+/HFSX”。

### 第二阶段：重建只读核心

1. 实现分区、HFS wrapper 和逻辑卷偏移抽象。
2. 实现基于 `HFSPlusForkData` 的逻辑 fork 流。
3. 按 TN1150 修复 B-tree 节点和偏移表。
4. 修复 Catalog key、文件、文件夹和 thread record。
5. 实现正确的 Unicode 比较规则。
6. 实现初始 extents 和 Extents Overflow。

### 第三阶段：建立可信测试

1. 添加最小真实 HFS+ 和 HFSX 镜像。
2. 为镜像中的文件、目录和内容保存 golden manifest。
3. 对提取结果执行大小和 SHA-256 校验。
4. 添加碎片化、Unicode、损坏镜像和边界条件测试。
5. CI 中启用 pytest、覆盖率、mypy、ruff/flake8 和产物启动检查。

### 第四阶段：接通用户功能

1. GUI 目录浏览。
2. 文件和文件夹属性。
3. 文件、目录和 Resource Fork 提取。
4. 搜索及路径解析。
5. CLI 提取工具。

### 第五阶段：扩展格式

在只读 HFS+ 稳定后，依次考虑：

1. 分区表。
2. DMG/UDIF。
3. FileVault/CoreStorage。
4. HFS Classic。
5. APFS。

写入功能应最后实施，并且必须具备事务、日志、一致性检查、故障注入和重新挂载验证。
