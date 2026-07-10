"""
APFS 读取器

负责读取和解析 APFS 容器和卷
"""

import struct
from typing import Optional, List, Dict, BinaryIO, Tuple
from pathlib import Path

from .structures import (
    NX_MAGIC, APFS_MAGIC, NXSuperblock, APFSSuperblock,
    BTNodeDescriptor, BTInfo, JKey, JInode, JDirEntry,
    OMAP, OMAPEntry, ObjType, ObjFlags
)


class APFSReader:
    """
    APFS 读取器
    
    负责打开 APFS 镜像文件，读取容器和卷信息
    """
    
    def __init__(self, file_path: str):
        """
        初始化 APFS 读取器
        
        Args:
            file_path: APFS 镜像文件路径
        """
        self.file_path = Path(file_path)
        self.file: Optional[BinaryIO] = None
        self.container: Optional[NXSuperblock] = None
        self.block_size: int = 4096  # 默认块大小
        self.volumes: Dict[int, APFSSuperblock] = {}
        
    def open(self) -> None:
        """打开 APFS 镜像文件"""
        self.file = open(self.file_path, 'rb')
        self._read_container()
        
    def close(self) -> None:
        """关闭文件"""
        if self.file:
            self.file.close()
            self.file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _read_block(self, block_num: int) -> bytes:
        """
        读取指定块号的数据
        
        Args:
            block_num: 块号
            
        Returns:
            块数据（bytes）
        """
        if not self.file:
            raise RuntimeError("文件未打开")
            
        offset = block_num * self.block_size
        self.file.seek(offset)
        return self.file.read(self.block_size)
        
    def _read_container(self) -> None:
        """读取容器超级块"""
        if not self.file:
            raise RuntimeError("文件未打开")
            
        # 读取第一个块（容器超级块）
        self.file.seek(0)
        data = self.file.read(4096)  # 读取足够的数据
        
        # 检查魔数
        if data[32:36] != NX_MAGIC:
            # 尝试不同的偏移（可能是 GPT 分区）
            for offset in [0, 512, 4096]:
                self.file.seek(offset)
                data = self.file.read(4096)
                if len(data) >= 36 and data[32:36] == NX_MAGIC:
                    break
            else:
                raise ValueError("不是有效的 APFS 容器（未找到 NXSB 魔数）")
        
        # 解析容器超级块
        self.container = NXSuperblock.from_bytes(data)
        self.block_size = self.container.block_size
        
        # 读取卷
        self._read_volumes()
        
    def _read_volumes(self) -> None:
        """读取所有卷"""
        if not self.container:
            raise RuntimeError("容器未初始化")
            
        # 遍历卷 OID 数组
        for i, oid in enumerate(self.container.volume_oids):
            if oid == 0:
                continue
                
            try:
                volume = self._read_volume(oid)
                self.volumes[i] = volume
            except Exception as e:
                print(f"警告: 无法读取卷 {i}: {e}")
                
    def _read_volume(self, oid: int) -> APFSSuperblock:
        """
        读取卷超级块
        
        Args:
            oid: 卷对象 ID
            
        Returns:
            卷超级块
        """
        # 通过对象映射查找物理位置
        paddr = self._resolve_oid(oid)
        
        # 读取卷超级块
        data = self._read_block(paddr)
        return APFSSuperblock.from_bytes(data)
        
    def _resolve_oid(self, oid: int) -> int:
        """
        解析对象 ID 到物理地址
        
        Args:
            oid: 对象 ID
            
        Returns:
            物理块号
        """
        if not self.container:
            raise RuntimeError("容器未初始化")
            
        # 读取对象映射
        omap_data = self._read_block(self.container.omap_oid)
        omap = OMAP.from_bytes(omap_data)
        
        # 在对象映射树中查找
        return self._search_omap_tree(omap.tree_oid, oid)
        
    def _search_omap_tree(self, tree_oid: int, target_oid: int) -> int:
        """
        在对象映射树中搜索目标 OID
        
        Args:
            tree_oid: 树对象 ID
            target_oid: 目标对象 ID
            
        Returns:
            物理块号
        """
        # 读取树节点
        paddr = self._resolve_oid(tree_oid)
        data = self._read_block(paddr)
        
        # 解析节点描述符
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 如果是叶节点，搜索条目
        if node_desc.type & 0x01:  # 叶节点标志
            return self._search_omap_leaf(data, target_oid)
        else:
            # 索引节点，继续搜索子树
            return self._search_omap_index(data, target_oid)
            
    def _search_omap_leaf(self, data: bytes, target_oid: int) -> int:
        """
        在叶节点中搜索目标 OID
        
        Args:
            data: 节点数据
            target_oid: 目标对象 ID
            
        Returns:
            物理块号
        """
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 读取偏移表
        offset_table_offset = len(data) - 2
        num_entries = struct.unpack_from('<H', data, offset_table_offset)[0]
        
        # 遍历条目
        for i in range(num_entries):
            entry_offset = struct.unpack_from('<H', data, offset_table_offset - (i + 1) * 2)[0]
            
            # 解析 OMAP 条目
            entry = OMAPEntry.from_bytes(data, entry_offset)
            
            if entry.oid == target_oid:
                return entry.paddr
                
        raise ValueError(f"未找到对象 ID: {target_oid}")
        
    def _search_omap_index(self, data: bytes, target_oid: int) -> int:
        """
        在索引节点中搜索目标 OID
        
        Args:
            data: 节点数据
            target_oid: 目标对象 ID
            
        Returns:
            物理块号
        """
        # 简单实现：读取第一个子节点
        # 实际应该使用二分查找
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 读取偏移表
        offset_table_offset = len(data) - 2
        num_entries = struct.unpack_from('<H', data, offset_table_offset)[0]
        
        if num_entries > 0:
            # 读取第一个条目
            entry_offset = struct.unpack_from('<H', data, offset_table_offset - 2)[0]
            
            # 解析键（对象 ID）
            key_oid = struct.unpack_from('<Q', data, entry_offset)[0]
            
            # 解析值（子节点指针）
            child_ptr = struct.unpack_from('<Q', data, entry_offset + 8)[0]
            
            # 递归搜索子节点
            return self._search_omap_tree(child_ptr, target_oid)
            
        raise ValueError(f"未找到对象 ID: {target_oid}")
        
    def get_volume_count(self) -> int:
        """获取卷数量"""
        return len(self.volumes)
        
    def get_volume(self, index: int = 0) -> Optional[APFSSuperblock]:
        """
        获取指定索引的卷
        
        Args:
            index: 卷索引（默认 0）
            
        Returns:
            卷超级块，如果不存在返回 None
        """
        return self.volumes.get(index)
        
    def list_volumes(self) -> List[Tuple[int, str]]:
        """
        列出所有卷
        
        Returns:
            卷列表 [(索引, 名称), ...]
        """
        result = []
        for index, volume in self.volumes.items():
            result.append((index, volume.name))
        return result
        
    def read_btree(self, oid: int) -> List[Tuple[bytes, bytes]]:
        """
        读取 B-tree 内容
        
        Args:
            oid: B-tree 根节点对象 ID
            
        Returns:
            键值对列表 [(key, value), ...]
        """
        result = []
        self._read_btree_recursive(oid, result)
        return result
        
    def _read_btree_recursive(self, oid: int, result: List[Tuple[bytes, bytes]]) -> None:
        """
        递归读取 B-tree
        
        Args:
            oid: 节点对象 ID
            result: 结果列表
        """
        # 解析对象 ID 到物理地址
        paddr = self._resolve_oid(oid)
        data = self._read_block(paddr)
        
        # 解析节点描述符
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        # 读取偏移表
        offset_table_offset = len(data) - 2
        num_entries = struct.unpack_from('<H', data, offset_table_offset)[0]
        
        # 遍历条目
        for i in range(num_entries):
            entry_offset = struct.unpack_from('<H', data, offset_table_offset - (i + 1) * 2)[0]
            
            if node_desc.type & 0x01:  # 叶节点
                # 读取键和值
                key_len = struct.unpack_from('<H', data, entry_offset)[0]
                key = data[entry_offset + 2:entry_offset + 2 + key_len]
                
                val_offset = entry_offset + 2 + key_len
                val_len = struct.unpack_from('<H', data, val_offset)[0]
                value = data[val_offset + 2:val_offset + 2 + val_len]
                
                result.append((key, value))
            else:
                # 索引节点，递归读取子树
                child_oid = struct.unpack_from('<Q', data, entry_offset + 8)[0]
                self._read_btree_recursive(child_oid, result)
                
    def read_directory(self, dir_oid: int) -> List[Tuple[str, int, bool]]:
        """
        读取目录内容
        
        Args:
            dir_oid: 目录对象 ID
            
        Returns:
            目录条目列表 [(名称, 目标 OID, 是否目录), ...]
        """
        # 读取目录 B-tree
        entries = self.read_btree(dir_oid)
        
        result = []
        for key, value in entries:
            # 解析键
            jkey = JKey.from_bytes(key)
            
            # 解析目录条目
            if len(value) >= 16:
                target_id = struct.unpack_from('<Q', value, 0)[0]
                date_added = struct.unpack_from('<Q', value, 8)[0]
                flags = struct.unpack_from('<H', value, 16)[0]
                
                # 读取文件名
                name_offset = 18
                name_bytes = value[name_offset:]
                null_pos = name_bytes.find(b'\x00')
                if null_pos >= 0:
                    name_bytes = name_bytes[:null_pos]
                name = name_bytes.decode('utf-8', errors='replace')
                
                is_dir = (flags & 0x10) != 0  # 目录标志
                result.append((name, target_id, is_dir))
                
        return result
        
    def read_inode(self, inode_oid: int) -> Optional[JInode]:
        """
        读取 inode 信息
        
        Args:
            inode_oid: inode 对象 ID
            
        Returns:
            inode 信息，如果不存在返回 None
        """
        # 读取 inode B-tree
        entries = self.read_btree(inode_oid)
        
        for key, value in entries:
            # 解析键
            jkey = JKey.from_bytes(key)
            
            # 检查是否是 inode 类型
            if jkey.type == 1:  # inode 类型
                return JInode.from_bytes(value)
                
        return None
        
    def read_file_extent(self, file_oid: int) -> List[Tuple[int, int, int]]:
        """
        读取文件扩展信息
        
        Args:
            file_oid: 文件对象 ID
            
        Returns:
            扩展列表 [(逻辑偏移, 物理块号, 长度), ...]
        """
        # 读取文件扩展 B-tree
        entries = self.read_btree(file_oid)
        
        result = []
        for key, value in entries:
            # 解析键
            jkey = JKey.from_bytes(key)
            
            # 检查是否是文件扩展类型
            if jkey.type == 8:  # 文件扩展类型
                if len(value) >= 24:
                    len_and_flags = struct.unpack_from('<Q', value, 0)[0]
                    phys_block_num = struct.unpack_from('<Q', value, 8)[0]
                    crypto_id = struct.unpack_from('<Q', value, 16)[0]
                    
                    length = len_and_flags & 0x00FFFFFFFFFFFFFF
                    result.append((jkey.obj_id, phys_block_num, length))
                    
        return result
