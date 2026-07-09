# HFSExplorer 项目审查报告

审查日期：2026-07-09

## 结论

项目属于"GUI 原型 + 部分 HFS+ 数据结构实验"，不能作为可用的 HFSExplorer，不适合启用写入功能。`PROGRESS.md` 中"100% 完成"与实际代码严重不符。

---

## 问题优先级与代码位置

### P0 - 核心 Catalog 解析无法处理真实 HFS+ 数据

| 问题 | 位置 |
|------|------|
| B-tree 偏移表顺序错误 | `src/core/hfs/btree.py:298` |
| Catalog 名称忽略 `HFSUniStr255.length` | `src/core/hfs/btree.py:605` |
| 文件夹记录 struct 格式错误 | `src/core/hfs/btree.py:668` |
| 文件记录 struct 格式错误 | `src/core/hfs/btree.py:746` |

复现：`Catalog 名称: '\x08test.txt'`，Folder/File 均抛出 `ValueError too many values to unpack`

### P0 - GUI 无法浏览目录

| 问题 | 位置 |
|------|------|
| Catalog 初始化为 `pass` | `src/gui/main_window.py:65` |
| 目录加载使用偏移 `0` | `src/gui/main_window.py:104` |
| 错误地将分配块大小当作 B-tree 节点大小 | `src/gui/main_window.py:533` |

### P0 - 文件读取和提取没有实现

| 问题 | 位置 |
|------|------|
| `_read_file_data()` 对非空文件返回空字节 | `src/core/hfs/extractor.py:154` |
| 提取按钮显示"功能待实现" | `src/gui/main_window.py:760` |

缺失：初始 extents、Extents Overflow、Resource Fork、压缩文件、符号链接、路径逃逸清理。

### P0 - 写入功能存在数据损坏风险

| 问题 | 位置 |
|------|------|
| 创建文件返回成功但未修改 Catalog | `src/core/hfs/file_writer.py:485` |
| 删除文件返回成功但未修改 Catalog | `src/core/hfs/file_writer.py:525` |
| 创建文件夹返回成功但未修改 Catalog | `src/core/hfs/file_writer.py:554` |
| 删除文件夹返回成功但未修改 Catalog | `src/core/hfs/file_writer.py:582` |
| 数据写入无 extent 映射，可能覆盖卷头 | `src/core/hfs/file_writer.py:254` |
| B-tree 节点写回/分配/释放未实现 | `src/core/hfs/btree_mutator.py:814` |
| 使用不存在的 `STRUCT_SIZE` 属性 | `src/core/hfs/btree_mutator.py:279` |
| 使用不存在的 `STRUCT_SIZE` 属性 | `src/core/hfs/btree_mutator.py:437` |

### P1 - FileVault 仅有算法框架

| 问题 | 位置 |
|------|------|
| 密钥包读取固定返回空数据 | `src/core/crypto/encrypted_volume.py:388` |
| GUI 提示解密功能未完成 | `src/gui/main_window.py:405` |

### P1 - 卷识别能力不足

| 问题 | 位置 |
|------|------|
| 只检查偏移 1024 处签名 | `src/core/hfs/reader.py:49` |

不支持：HFS wrapper、GPT/MBR/APM 分区、DMG/UDIF、物理设备偏移。卷头验证只检查签名。

### P1 - B-tree 底层缺陷

- 偏移表顺序与磁盘格式相反
- 叶节点链表遍历无循环检测（损坏镜像可致无限循环）
- 查找直接比较原始 key 字节，未实现 Unicode 归一化和大小写折叠
- 初始节点大小依赖外部传入，GUI 错误使用卷分配块大小

### P1 - Catalog 底层缺陷

- 缺少名称长度字段解析
- 文件记录缺少 `reserved1`，后续字段偏移不正确
- 未实现 thread record
- 未实现 CNID 到完整路径的反向解析

### P1 - Extents 底层缺陷

- 文件记录未保留完整 `HFSPlusForkData`
- `startBlock` 计算逻辑不正确
- 未为特殊文件提供逻辑 fork 流

### P2 - 空模块

`src/core/dmg/__init__.py`、`src/core/partition/__init__.py`、`src/core/utils/__init__.py`、`src/platform/__init__.py`、`src/cli/__init__.py`

### P2 - 工程问题

- `pyproject.toml:41` 和 `setup.py:37` 的 `unhfs` 入口指向不存在的 `src.cli.unhfs`
- `PROGRESS.md` 宣称 100%，`IMPLEMENTATION_PLAN.md` 标记 5%
- 源码约 90 处 TODO/pass/"尚未实现"
- `requirements.txt` 同时安装 `pycryptodome` 和 `pycryptodomex`
- `setup.py` 与 `pyproject.toml` 重复维护

### P2 - 测试问题

67 个测试全部通过，但测试数据按错误实现构造（`tests/test_btree.py:205`、`tests/test_full.py:397`），形成"测试和实现共同违反磁盘格式但测试仍通过"的情况。缺少真实镜像测试、Unicode 排序测试、损坏镜像测试、写入一致性测试。

---

## 验证结果

- 工作区在审查前后均无受版本控制的改动
- Python 语法编译检查通过
- 67 个现有测试通过
- 环境未安装 pytest/mypy/flake8/PyQt6/pycryptodome，未执行正式测试
- 最小复现确认：
  - B-tree 偏移表无法解析规范格式
  - Catalog 名称解析包含错误的长度字符
  - Catalog 文件和文件夹记录抛出字段解包异常

---

## 修复顺序

### 第一阶段：收缩范围并保证安全

1. 禁用或删除全部写入入口
2. 版本状态恢复为 Alpha/Prototype
3. 删除 README 中尚未实现的功能声明
4. 明确只支持"只读 HFS+/HFSX"

### 第二阶段：重建只读核心

1. 实现分区、HFS wrapper 和逻辑卷偏移抽象
2. 实现基于 `HFSPlusForkData` 的逻辑 fork 流
3. 按 TN1150 修复 B-tree 节点和偏移表
4. 修复 Catalog key、文件、文件夹和 thread record
5. 实现正确的 Unicode 比较规则
6. 实现初始 extents 和 Extents Overflow

### 第三阶段：建立可信测试

1. 添加最小真实 HFS+ 和 HFSX 镜像
2. 为镜像中的文件、目录和内容保存 golden manifest
3. 对提取结果执行大小和 SHA-256 校验
4. 添加碎片化、Unicode、损坏镜像和边界条件测试
5. CI 中启用 pytest、覆盖率、mypy、ruff/flake8 和产物启动检查

### 第四阶段：接通用户功能

1. GUI 目录浏览
2. 文件和文件夹属性
3. 文件、目录和 Resource Fork 提取
4. 搜索及路径解析
5. CLI 提取工具

### 第五阶段：扩展格式

1. 分区表
2. DMG/UDIF
3. FileVault/CoreStorage
4. HFS Classic
5. APFS

写入功能应最后实施，必须具备事务、日志、一致性检查、故障注入和重新挂载验证。
