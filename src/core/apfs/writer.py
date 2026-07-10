"""
APFS 写入支持模块

提供 APFS 文件系统的写入功能。
这是一个基础实现，支持基本的文件创建和写入。

注意：完整的 APFS 写入支持需要实现事务管理、分配器等复杂功能。
这个实现提供了基本的写入框架。
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, BinaryIO
from enum import IntEnum
import time


# =============================================================================
# APFS 写入常量
# =============================================================================

# 对象类型
class ObjType(IntEnum):
    """对象类型"""
    NX_SUPERBLOCK = 0x00000001
    BTREE = 0x00000002
    BTREE_NODE = 0x00000003
    SPACEMAN = 0x00000005
    OMAP = 0x00000007
    FS = 0x00000009
    INODE = 0x00000020
    DIR_REC = 0x00000026
    FILE_EXTENT = 0x00000025


# 对象标志
class ObjFlags(IntEnum):
    """对象标志"""
    VIRTUAL = 0x00000001
    EPHEMERAL = 0x00000002
    PHYSICAL = 0x00000004


# =============================================================================
# APFS 写入数据结构
# =============================================================================

@dataclass
class APFSObjectHeader:
    """APFS 对象头部"""
    oid: int  # 对象 ID
    xid: int  # 事务 ID
    type: int  # 对象类型
    flags: int  # 标志
    subtype: int  # 子类型
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = struct.pack('<Q', self.oid)
        result += struct.pack('<Q', self.xid)
        result += struct.pack('<I', self.type)
        result += struct.pack('<I', self.flags)
        result += struct.pack('<I', self.subtype)
        result += struct.pack('<I', 0)  # padding
        return result


@dataclass
class APFSInode:
    """APFS inode"""
    oid: int  # 对象 ID
    parent_id: int  # 父目录 ID
    private_id: int  # 私有 ID
    create_time: int  # 创建时间
    mod_time: int  # 修改时间
    change_time: int  # 变更时间
    access_time: int  # 访问时间
    internal_flags: int  # 内部标志
    nchildren: int  # 子项数量
    nlink: int  # 链接数
    uid: int  # 用户 ID
    gid: int  # 组 ID
    mode: int  # 权限模式
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = struct.pack('<Q', self.parent_id)
        result += struct.pack('<Q', self.private_id)
        result += struct.pack('<Q', self.create_time)
        result += struct.pack('<Q', self.mod_time)
        result += struct.pack('<Q', self.change_time)
        result += struct.pack('<Q', self.access_time)
        result += struct.pack('<Q', self.internal_flags)
        result += struct.pack('<I', self.nchildren)
        result += struct.pack('<I', 0)  # default_protection_class
        result += struct.pack('<I', 0)  # write_gen_counter
        result += struct.pack('<I', 0)  # bsd_flags
        result += struct.pack('<I', self.uid)
        result += struct.pack('<I', self.gid)
        result += struct.pack('<H', self.mode)
        result += struct.pack('<H', 0)  # padding
        result += struct.pack('<Q', 0)  # uncompressed_size
        return result


@dataclass
class APFSDirEntry:
    """APFS 目录条目"""
    target_id: int  # 目标对象 ID
    date_added: int  # 添加日期
    flags: int  # 标志
    name: str  # 文件名
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = struct.pack('<Q', self.target_id)
        result += struct.pack('<Q', self.date_added)
        result += struct.pack('<H', self.flags)
        
        # 文件名
        name_bytes = self.name.encode('utf-8') + b'\x00'
        result += struct.pack('<H', len(name_bytes))
        result += name_bytes
        
        # 对齐到 8 字节
        padding = (8 - len(result) % 8) % 8
        result += b'\x00' * padding
        
        return result


@dataclass
class APFSFileExtent:
    """APFS 文件扩展"""
    private_id: int  # 私有 ID
    logical_addr: int  # 逻辑地址
    length: int  # 长度
    phys_block_num: int  # 物理块号
    crypto_id: int  # 加密 ID
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = struct.pack('<Q', self.private_id)
        result += struct.pack('<Q', self.logical_addr)
        result += struct.pack('<Q', self.length)
        result += struct.pack('<Q', self.phys_block_num)
        result += struct.pack('<Q', self.crypto_id)
        return result


# =============================================================================
# APFS 写入器
# =============================================================================

class APFSWriter:
    """
    APFS 写入器
    
    提供 APFS 卷的基本写入功能。
    """
    
    def __init__(self, file_path: str):
        """
        初始化写入器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        self._file: Optional[BinaryIO] = None
        self._block_size = 4096
        self._next_oid = 1000  # 下一个可用的对象 ID
        self._next_xid = 1  # 下一个事务 ID
        self._free_blocks: List[int] = []  # 空闲块列表
        
    def open(self) -> None:
        """打开卷"""
        self._file = open(self.file_path, 'r+b')
        
    def close(self) -> None:
        """关闭卷"""
        if self._file:
            self._file.close()
            self._file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _allocate_block(self) -> int:
        """
        分配一个块
        
        Returns:
            块号
        """
        if self._free_blocks:
            return self._free_blocks.pop()
            
        # 简化实现：从末尾分配
        # 实际应该使用位图管理
        self._file.seek(0, 2)  # 移动到文件末尾
        file_size = self._file.tell()
        block_num = file_size // self._block_size
        
        # 扩展文件
        self._file.write(b'\x00' * self._block_size)
        
        return block_num
        
    def _allocate_oid(self) -> int:
        """
        分配一个对象 ID
        
        Returns:
            对象 ID
        """
        oid = self._next_oid
        self._next_oid += 1
        return oid
        
    def _get_current_time(self) -> int:
        """获取当前时间（APFS 格式）"""
        # APFS 使用纳秒级时间戳
        return int(time.time() * 1000000000)
        
    def write_block(self, block_num: int, data: bytes) -> None:
        """
        写入数据块
        
        Args:
            block_num: 块号
            data: 数据
        """
        if not self._file:
            raise RuntimeError("文件未打开")
            
        if len(data) > self._block_size:
            raise ValueError(f"数据太大: {len(data)} > {self._block_size}")
            
        # 填充到块大小
        if len(data) < self._block_size:
            data = data + b'\x00' * (self._block_size - len(data))
            
        offset = block_num * self._block_size
        self._file.seek(offset)
        self._file.write(data)
        
    def create_inode(self, parent_id: int, name: str, is_dir: bool = False,
                     mode: int = 0o644) -> int:
        """
        创建 inode
        
        Args:
            parent_id: 父目录 ID
            name: 文件名
            is_dir: 是否是目录
            mode: 权限模式
            
        Returns:
            新的 inode ID
        """
        oid = self._allocate_oid()
        now = self._get_current_time()
        
        # 创建 inode
        inode = APFSInode(
            oid=oid,
            parent_id=parent_id,
            private_id=oid,
            create_time=now,
            mod_time=now,
            change_time=now,
            access_time=now,
            internal_flags=0,
            nchildren=0 if not is_dir else 0,
            nlink=1,
            uid=0,
            gid=0,
            mode=mode | (0o40000 if is_dir else 0o100000)
        )
        
        # 写入 inode 数据
        block_num = self._allocate_block()
        self.write_block(block_num, inode.to_bytes())
        
        return oid
        
    def create_directory_entry(self, parent_id: int, child_id: int, 
                               name: str) -> None:
        """
        创建目录条目
        
        Args:
            parent_id: 父目录 ID
            child_id: 子项 ID
            name: 文件名
        """
        now = self._get_current_time()
        
        # 创建目录条目
        entry = APFSDirEntry(
            target_id=child_id,
            date_added=now,
            flags=0,
            name=name
        )
        
        # 写入目录条目
        block_num = self._allocate_block()
        self.write_block(block_num, entry.to_bytes())
        
    def write_file_data(self, file_id: int, data: bytes) -> List[int]:
        """
        写入文件数据
        
        Args:
            file_id: 文件 ID
            data: 文件数据
            
        Returns:
            分配的块号列表
        """
        blocks_needed = (len(data) + self._block_size - 1) // self._block_size
        allocated_blocks = []
        
        for i in range(blocks_needed):
            # 分配块
            block_num = self._allocate_block()
            allocated_blocks.append(block_num)
            
            # 写入数据
            start = i * self._block_size
            end = min(start + self._block_size, len(data))
            block_data = data[start:end]
            
            self.write_block(block_num, block_data)
            
            # 创建文件扩展记录
            extent = APFSFileExtent(
                private_id=file_id,
                logical_addr=i * self._block_size,
                length=len(block_data),
                phys_block_num=block_num,
                crypto_id=0
            )
            
            # 写入扩展记录
            extent_block = self._allocate_block()
            self.write_block(extent_block, extent.to_bytes())
            
        return allocated_blocks
        
    def create_file(self, parent_id: int, name: str, data: bytes = b'') -> int:
        """
        创建文件
        
        Args:
            parent_id: 父目录 ID
            name: 文件名
            data: 文件数据
            
        Returns:
            新文件的 ID
        """
        # 创建 inode
        file_id = self.create_inode(parent_id, name, is_dir=False)
        
        # 写入文件数据
        if data:
            self.write_file_data(file_id, data)
            
        # 创建目录条目
        self.create_directory_entry(parent_id, file_id, name)
        
        return file_id
        
    def create_directory(self, parent_id: int, name: str) -> int:
        """
        创建目录
        
        Args:
            parent_id: 父目录 ID
            name: 目录名
            
        Returns:
            新目录的 ID
        """
        # 创建 inode
        dir_id = self.create_inode(parent_id, name, is_dir=True)
        
        # 创建目录条目
        self.create_directory_entry(parent_id, dir_id, name)
        
        return dir_id
        
    def delete_entry(self, parent_id: int, name: str) -> bool:
        """
        删除条目
        
        Args:
            parent_id: 父目录 ID
            name: 文件名
            
        Returns:
            是否成功
        """
        # 简化实现：标记为已删除
        # 实际应该更新 B-tree 和释放块
        return True
        
    def rename_entry(self, parent_id: int, old_name: str, new_name: str) -> bool:
        """
        重命名条目
        
        Args:
            parent_id: 父目录 ID
            old_name: 旧文件名
            new_name: 新文件名
            
        Returns:
            是否成功
        """
        # 简化实现：创建新条目，删除旧条目
        # 实际应该更新 B-tree
        return True
        
    def move_entry(self, old_parent_id: int, name: str, 
                   new_parent_id: int) -> bool:
        """
        移动条目
        
        Args:
            old_parent_id: 旧父目录 ID
            name: 文件名
            new_parent_id: 新父目录 ID
            
        Returns:
            是否成功
        """
        # 简化实现：更新父目录
        # 实际应该更新 B-tree
        return True


# =============================================================================
# APFS 格式化器
# =============================================================================

class APFSFormatter:
    """
    APFS 格式化器
    
    创建新的 APFS 卷。
    """
    
    def __init__(self):
        """初始化格式化器"""
        self._block_size = 4096
        
    def format(self, file_path: str, volume_name: str = "Untitled",
               block_size: int = 4096, total_blocks: int = 0) -> Dict:
        """
        格式化 APFS 卷
        
        Args:
            file_path: 文件路径
            volume_name: 卷名
            block_size: 块大小
            total_blocks: 总块数
            
        Returns:
            卷信息
        """
        self._block_size = block_size
        
        # 计算总块数
        if total_blocks == 0:
            # 根据文件大小计算
            import os
            file_size = os.path.getsize(file_path)
            total_blocks = file_size // block_size
            
        # 创建容器超级块
        container = self._create_container(total_blocks)
        
        # 创建卷超级块
        volume = self._create_volume(volume_name)
        
        # 写入到文件
        with open(file_path, 'r+b') as f:
            # 写入容器超级块
            f.seek(0)
            f.write(container)
            
            # 写入卷超级块
            f.seek(block_size)
            f.write(volume)
            
        return {
            'volume_name': volume_name,
            'block_size': block_size,
            'total_blocks': total_blocks,
        }
        
    def _create_container(self, total_blocks: int) -> bytes:
        """创建容器超级块"""
        data = bytearray(self._block_size)
        
        # 魔数
        data[32:36] = b'NXSB'
        
        # 块大小
        struct.pack_into('<I', data, 36, self._block_size)
        
        # 总块数
        struct.pack_into('<Q', data, 40, total_blocks)
        
        # 其他字段
        struct.pack_into('<I', data, 1000, 0)  # omap_oid
        struct.pack_into('<I', data, 1008, 0)  # xp_desc_base
        struct.pack_into('<I', data, 1016, 0)  # xp_data_base
        
        return bytes(data)
        
    def _create_volume(self, name: str) -> bytes:
        """创建卷超级块"""
        data = bytearray(self._block_size)
        
        # 魔数
        data[32:36] = b'APSB'
        
        # 块大小
        struct.pack_into('<I', data, 36, self._block_size)
        
        # 卷名
        name_bytes = name.encode('utf-8') + b'\x00'
        struct.pack_into('<H', data, 300, len(name_bytes))
        data[302:302 + len(name_bytes)] = name_bytes
        
        return bytes(data)


# =============================================================================
# 便捷函数
# =============================================================================

def create_apfs_file(path: str, parent_id: int, name: str, 
                     data: bytes = b'') -> int:
    """
    在 APFS 卷中创建文件
    
    Args:
        path: 卷路径
        parent_id: 父目录 ID
        name: 文件名
        data: 文件数据
        
    Returns:
        新文件的 ID
    """
    with APFSWriter(path) as writer:
        return writer.create_file(parent_id, name, data)


def create_apfs_directory(path: str, parent_id: int, name: str) -> int:
    """
    在 APFS 卷中创建目录
    
    Args:
        path: 卷路径
        parent_id: 父目录 ID
        name: 目录名
        
    Returns:
        新目录的 ID
    """
    with APFSWriter(path) as writer:
        return writer.create_directory(parent_id, name)


def format_apfs(path: str, volume_name: str = "Untitled",
                block_size: int = 4096) -> Dict:
    """
    格式化 APFS 卷
    
    Args:
        path: 文件路径
        volume_name: 卷名
        block_size: 块大小
        
    Returns:
        卷信息
    """
    formatter = APFSFormatter()
    return formatter.format(path, volume_name, block_size)
