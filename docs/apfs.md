# APFS 支持

HFSExplorer 现在支持读取 APFS (Apple File System) 镜像文件。

## 功能特性

### 已实现功能

- **容器解析**: 读取 APFS 容器超级块，获取容器基本信息
- **卷管理**: 列出和读取容器中的所有卷
- **目录浏览**: 遍历目录结构，列出文件和文件夹
- **文件读取**: 读取文件数据（通过对象映射）
- **对象映射**: 支持虚拟对象 ID 到物理地址的映射
- **B-tree 遍历**: 支持 APFS 的 B-tree 结构遍历

### 待实现功能

- **加密支持**: 解密加密的 APFS 卷
- **快照支持**: 读取和浏览快照
- **克隆支持**: 处理文件克隆
- **压缩支持**: 解压压缩的文件数据
- **写入支持**: 写入 APFS 卷（目前只读）

## 使用方法

### 基本使用

```python
from src.core.apfs import APFSReader, APFSContainer

# 打开 APFS 镜像
with APFSReader("/path/to/apfs.img") as reader:
    # 创建容器管理器
    container = APFSContainer(reader)
    container.load()
    
    # 获取容器信息
    info = container.get_info()
    print(f"块大小: {info['block_size']}")
    print(f"总块数: {info['block_count']}")
    
    # 列出所有卷
    volumes = container.list_volumes()
    for vol in volumes:
        print(f"卷 {vol['index']}: {vol['name']}")
```

### 读取卷内容

```python
from src.core.apfs import APFSReader, APFSContainer

with APFSReader("/path/to/apfs.img") as reader:
    container = APFSContainer(reader)
    container.load()
    
    # 获取第一个卷
    volume = container.get_volume(0)
    if volume:
        # 列出根目录
        entries = volume.list_directory(2)  # 根目录 OID 通常是 2
        for entry in entries:
            print(f"{entry['type']}: {entry['name']}")
            
        # 搜索文件
        results = volume.search_files("*.txt")
        for result in results:
            print(f"找到: {result['path']}")
```

### 读取文件数据

```python
from src.core.apfs import APFSReader, APFSContainer

with APFSReader("/path/to/apfs.img") as reader:
    container = APFSContainer(reader)
    container.load()
    
    volume = container.get_volume(0)
    if volume:
        # 读取文件数据（需要知道文件的 OID）
        file_oid = 12345  # 示例 OID
        data = volume.read_file_data(file_oid)
        print(f"文件大小: {len(data)} 字节")
```

## 数据结构

### 容器超级块 (NXSuperblock)

容器超级块位于 APFS 镜像的开头，包含以下信息：

- **magic**: 魔数 "NXSB"
- **block_size**: 块大小（字节）
- **block_count**: 总块数
- **uuid**: 容器 UUID
- **next_xid**: 下一个事务 ID
- **next_oid**: 下一个对象 ID
- **max_volumes**: 最大卷数

### 卷超级块 (APFSSuperblock)

卷超级块包含卷的元数据：

- **magic**: 魔数 "APSB"
- **name**: 卷名
- **uuid**: 卷 UUID
- **block_size**: 块大小
- **total_blocks_used**: 已使用的总块数
- **omap_oid**: 对象映射 B-tree 的根对象 ID
- **root_tree_oid**: 根目录 B-tree 的根对象 ID

### 对象映射 (OMAP)

对象映射将虚拟对象 ID 映射到物理块号：

- **tree_oid**: 映射树的根对象 ID
- **snap_count**: 快照数量

## 测试

运行 APFS 模块测试：

```bash
pytest tests/test_apfs.py -v
```

测试覆盖：
- 数据结构解析测试
- 读取器初始化测试
- 容器和卷管理测试
- 集成测试

## 限制

1. **只读支持**: 目前只支持读取，不支持写入
2. **加密卷**: 不支持加密的 APFS 卷
3. **快照**: 不支持浏览快照
4. **压缩**: 不支持透明解压压缩文件
5. **性能**: 大文件读取可能较慢

## 参考资源

- [Apple File System Reference](https://developer.apple.com/support/apple-file-system/Reference.pdf)
- [apfs-fuse](https://github.com/sgan81/apfs-fuse) - C++ 实现的 APFS FUSE 驱动
- [apfsprogs](https://github.com/linux-apfs/apfsprogs) - APFS 工具集

## 开发计划

### 短期目标 (P1)

- [x] 基本容器和卷解析
- [x] 目录浏览
- [x] 文件读取
- [ ] 性能优化

### 中期目标 (P2)

- [ ] 加密卷支持
- [ ] 快照浏览
- [ ] 压缩文件支持

### 长期目标 (P3)

- [ ] 写入支持
- [ ] 克隆支持
- [ ] 完整的 APFS 规范支持
