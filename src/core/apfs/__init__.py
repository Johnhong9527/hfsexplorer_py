"""
APFS (Apple File System) 支持模块

APFS 是 Apple 在 macOS 10.13 (High Sierra) 中引入的新文件系统。
它支持容器（container）和卷（volume）的概念，具有克隆、快照、加密等特性。

参考资源：
- Apple File System Reference (https://developer.apple.com/support/apple-file-system/Reference.pdf)
- apfs-fuse (https://github.com/sgan81/apfs-fuse)
- apfsprogs (https://github.com/linux-apfs/apfsprogs)
"""

from .structures import (
    APFS_MAGIC,
    NX_MAGIC,
    APFS_TYPE_MASK,
    APFS_TYPE_SHIFT,
    
    # 容器超级块
    NXSuperblock,
    
    # 卷超级块
    APFSSuperblock,
    
    # B-tree 结构
    BTNodeDescriptor,
    BTInfo,
    
    # 文件系统对象
    JKey,
    JInode,
    JDirEntry,
    JFileExtent,
    
    # 常量
    OMAP,
    OMAPEntry,
)

from .reader import APFSReader
from .container import APFSContainer
from .volume import APFSVolume

__all__ = [
    'APFS_MAGIC',
    'NX_MAGIC',
    'APFS_TYPE_MASK',
    'APFS_TYPE_SHIFT',
    'NXSuperblock',
    'APFSSuperblock',
    'BTNodeDescriptor',
    'BTInfo',
    'JKey',
    'JInode',
    'JDirEntry',
    'JFileExtent',
    'OMAP',
    'OMAPEntry',
    'APFSReader',
    'APFSContainer',
    'APFSVolume',
]
