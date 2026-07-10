"""
APFS 卷管理

负责管理 APFS 卷的结构和操作
"""

from typing import Optional, List, Dict, Tuple
from pathlib import Path

from .structures import (
    APFSSuperblock, JKey, JInode, JDirEntry, JFileExtent,
    DirEntryType, OMAP
)


class APFSVolume:
    """
    APFS 卷类
    
    管理 APFS 卷的结构和操作
    """
    
    def __init__(self, reader: 'APFSReader', volume: APFSSuperblock):
        """
        初始化卷
        
        Args:
            reader: APFS 读取器
            volume: 卷超级块
        """
        self.reader = reader
        self.superblock = volume
        self._root_tree: Optional[List[Tuple[bytes, bytes]]] = None
        
    @property
    def name(self) -> str:
        """卷名"""
        return self.superblock.name
        
    @property
    def uuid(self) -> bytes:
        """卷 UUID"""
        return self.superblock.uuid
        
    @property
    def block_size(self) -> int:
        """块大小"""
        return self.superblock.block_size
        
    @property
    def total_blocks_used(self) -> int:
        """已使用的总块数"""
        return self.superblock.total_blocks_used
        
    @property
    def version(self) -> Tuple[int, int]:
        """APFS 版本"""
        return (self.superblock.version, self.superblock.minor_version)
        
    def get_info(self) -> Dict:
        """
        获取卷信息
        
        Returns:
            卷信息字典
        """
        return {
            'name': self.name,
            'uuid': self.uuid.hex(),
            'block_size': self.block_size,
            'total_blocks_used': self.total_blocks_used,
            'version': f"{self.superblock.version}.{self.superblock.minor_version}",
            'features': self.superblock.features,
            'read_only_features': self.superblock.read_only_features,
            'incompatible_features': self.superblock.incompatible_features,
            'next_obj_id': self.superblock.next_obj_id,
            'next_xid': self.superblock.next_xid,
            'num_snapshots': self.superblock.num_snapshots,
        }
        
    def _load_root_tree(self) -> None:
        """加载根目录树"""
        if self._root_tree is None:
            self._root_tree = self.reader.read_btree(self.superblock.root_tree_oid)
            
    def list_directory(self, dir_oid: int = 2) -> List[Dict]:
        """
        列出目录内容
        
        Args:
            dir_oid: 目录对象 ID（默认 2，即根目录）
            
        Returns:
            目录条目列表
        """
        # 读取目录树
        entries = self.reader.read_btree(dir_oid)
        
        result = []
        for key, value in entries:
            try:
                # 解析键
                jkey = JKey.from_bytes(key)
                
                # 解析目录条目
                if len(value) >= 18:
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
                    
                    # 判断类型
                    is_dir = (flags & 0x10) != 0
                    is_file = (flags & 0x20) != 0
                    
                    entry_type = 'directory' if is_dir else 'file'
                    
                    result.append({
                        'name': name,
                        'oid': target_id,
                        'type': entry_type,
                        'flags': flags,
                        'date_added': date_added,
                    })
            except Exception as e:
                print(f"警告: 无法解析目录条目: {e}")
                continue
                
        return result
        
    def get_inode(self, inode_oid: int) -> Optional[Dict]:
        """
        获取 inode 信息
        
        Args:
            inode_oid: inode 对象 ID
            
        Returns:
            inode 信息字典
        """
        inode = self.reader.read_inode(inode_oid)
        if not inode:
            return None
            
        return {
            'parent_id': inode.parent_id,
            'private_id': inode.private_id,
            'create_time': inode.create_time,
            'mod_time': inode.mod_time,
            'change_time': inode.change_time,
            'access_time': inode.access_time,
            'internal_flags': inode.internal_flags,
            'nchildren': inode.nchildren,
            'nlink': inode.nlink,
            'uid': inode.uid,
            'gid': inode.gid,
            'mode': inode.mode,
            'bsd_flags': inode.bsd_flags,
            'rdev': inode.rdev,
        }
        
    def get_file_extents(self, file_oid: int) -> List[Dict]:
        """
        获取文件扩展信息
        
        Args:
            file_oid: 文件对象 ID
            
        Returns:
            扩展信息列表
        """
        extents = self.reader.read_file_extent(file_oid)
        
        result = []
        for logical_offset, phys_block_num, length in extents:
            result.append({
                'logical_offset': logical_offset,
                'physical_block': phys_block_num,
                'length': length,
            })
            
        return result
        
    def read_file_data(self, file_oid: int, offset: int = 0, 
                       length: Optional[int] = None) -> bytes:
        """
        读取文件数据
        
        Args:
            file_oid: 文件对象 ID
            offset: 起始偏移（字节）
            length: 读取长度（字节），None 表示读取全部
            
        Returns:
            文件数据
        """
        # 获取文件扩展
        extents = self.get_file_extents(file_oid)
        
        if not extents:
            return b''
            
        # 计算文件总大小
        total_size = sum(ext['length'] for ext in extents)
        
        # 调整读取范围
        if offset >= total_size:
            return b''
            
        if length is None:
            length = total_size - offset
        else:
            length = min(length, total_size - offset)
            
        # 读取数据
        result = b''
        current_offset = 0
        
        for extent in extents:
            extent_start = extent['logical_offset']
            extent_end = extent_start + extent['length']
            
            # 检查是否在读取范围内
            if extent_end <= offset:
                current_offset = extent_end
                continue
                
            if extent_start >= offset + length:
                break
                
            # 计算读取范围
            read_start = max(offset, extent_start) - extent_start
            read_end = min(offset + length, extent_end) - extent_start
            
            # 读取数据
            phys_block = extent['physical_block']
            data = self.reader._read_block(phys_block)
            
            # 提取所需部分
            result += data[read_start:read_end]
            
        return result
        
    def search_files(self, pattern: str, dir_oid: int = 2) -> List[Dict]:
        """
        搜索文件
        
        Args:
            pattern: 搜索模式（支持 * 和 ? 通配符）
            dir_oid: 起始目录 OID
            
        Returns:
            匹配的文件列表
        """
        import fnmatch
        
        results = []
        self._search_recursive(dir_oid, pattern, results, '')
        return results
        
    def _search_recursive(self, dir_oid: int, pattern: str, 
                          results: List[Dict], parent_path: str) -> None:
        """
        递归搜索文件
        
        Args:
            dir_oid: 目录 OID
            pattern: 搜索模式
            results: 结果列表
            parent_path: 父目录路径
        """
        import fnmatch
        
        try:
            entries = self.list_directory(dir_oid)
        except Exception:
            return
            
        for entry in entries:
            name = entry['name']
            full_path = f"{parent_path}/{name}" if parent_path else name
            
            # 检查是否匹配
            if fnmatch.fnmatch(name.lower(), pattern.lower()):
                results.append({
                    'name': name,
                    'path': full_path,
                    'oid': entry['oid'],
                    'type': entry['type'],
                })
                
            # 如果是目录，递归搜索
            if entry['type'] == 'directory':
                self._search_recursive(entry['oid'], pattern, results, full_path)


# 需要导入 struct
import struct
