"""
APFS 容器管理

负责管理 APFS 容器的结构和操作
"""

from typing import Optional, List, Dict, BinaryIO
from pathlib import Path

from .structures import NXSuperblock, APFSSuperblock, OMAP


class APFSContainer:
    """
    APFS 容器类
    
    管理 APFS 容器的结构和操作
    """
    
    def __init__(self, reader: 'APFSReader'):
        """
        初始化容器
        
        Args:
            reader: APFS 读取器
        """
        self.reader = reader
        self.superblock: Optional[NXSuperblock] = None
        self.volumes: Dict[int, APFSSuperblock] = {}
        
    def load(self) -> None:
        """加载容器"""
        self.superblock = self.reader.container
        if not self.superblock:
            raise RuntimeError("容器未初始化")
            
        self.volumes = self.reader.volumes.copy()
        
    @property
    def block_size(self) -> int:
        """块大小"""
        if self.superblock:
            return self.superblock.block_size
        return 4096
        
    @property
    def block_count(self) -> int:
        """总块数"""
        if self.superblock:
            return self.superblock.block_count
        return 0
        
    @property
    def uuid(self) -> bytes:
        """容器 UUID"""
        if self.superblock:
            return self.superblock.uuid
        return b'\x00' * 16
        
    @property
    def volume_count(self) -> int:
        """卷数量"""
        return len(self.volumes)
        
    def get_volume(self, index: int = 0) -> Optional[APFSSuperblock]:
        """
        获取指定索引的卷
        
        Args:
            index: 卷索引
            
        Returns:
            卷超级块
        """
        return self.volumes.get(index)
        
    def list_volumes(self) -> List[Dict]:
        """
        列出所有卷
        
        Returns:
            卷信息列表
        """
        result = []
        for index, volume in self.volumes.items():
            result.append({
                'index': index,
                'name': volume.name,
                'uuid': volume.uuid.hex(),
                'block_size': volume.block_size,
                'total_blocks_used': volume.total_blocks_used,
            })
        return result
        
    def get_info(self) -> Dict:
        """
        获取容器信息
        
        Returns:
            容器信息字典
        """
        if not self.superblock:
            return {}
            
        return {
            'magic': self.superblock.magic.decode(),
            'block_size': self.superblock.block_size,
            'block_count': self.superblock.block_count,
            'uuid': self.superblock.uuid.hex(),
            'features': self.superblock.features,
            'read_only_features': self.superblock.read_only_features,
            'incompatible_features': self.superblock.incompatible_features,
            'next_xid': self.superblock.next_xid,
            'next_oid': self.superblock.next_oid,
            'max_volumes': self.superblock.max_volumes,
            'volume_count': self.volume_count,
        }
