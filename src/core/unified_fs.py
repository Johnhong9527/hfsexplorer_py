"""
统一文件系统接口

提供统一的接口来访问所有支持的文件系统：
- HFS+ / HFSX
- HFS Classic
- APFS
- CoreStorage
"""

import os
from typing import Optional, List, Dict, Any, BinaryIO
from enum import Enum


class FileSystemType(Enum):
    """文件系统类型"""
    UNKNOWN = "unknown"
    HFS = "hfs"
    HFS_PLUS = "hfs+"
    HFSX = "hfsx"
    APFS = "apfs"
    CORESTORAGE = "corestorage"


class FileSystemDetector:
    """
    文件系统检测器
    
    自动检测文件系统类型
    """
    
    @staticmethod
    def detect(path: str) -> FileSystemType:
        """
        检测文件系统类型
        
        Args:
            path: 文件路径
            
        Returns:
            文件系统类型
        """
        try:
            with open(path, 'rb') as f:
                # 读取前 4096 字节
                data = f.read(4096)
                
                # 检查 APFS
                if b'NXSB' in data[32:36]:
                    return FileSystemType.APFS
                    
                # 检查 HFS+
                if len(data) >= 1026:
                    signature = int.from_bytes(data[1024:1026], 'big')
                    if signature == 0x482B:
                        return FileSystemType.HFS_PLUS
                    elif signature == 0x4858:
                        return FileSystemType.HFSX
                    elif signature == 0x4244:
                        return FileSystemType.HFS
                        
                # 检查 CoreStorage
                for offset in range(0, len(data) - 4, 4):
                    if data[offset:offset + 4] == b'CS\x00\x00':
                        return FileSystemType.CORESTORAGE
                        
        except Exception:
            pass
            
        return FileSystemType.UNKNOWN


class UnifiedVolume:
    """
    统一卷接口
    
    提供统一的文件系统访问接口
    """
    
    def __init__(self, path: str):
        """
        初始化统一卷
        
        Args:
            path: 文件路径
        """
        self.path = path
        self.fs_type = FileSystemDetector.detect(path)
        self._volume = None
        
    def open(self) -> None:
        """打开卷"""
        if self.fs_type == FileSystemType.HFS_PLUS or self.fs_type == FileSystemType.HFSX:
            from src.core.hfs import HFSPlusVolume
            self._volume = HFSPlusVolume(self.path)
            
        elif self.fs_type == FileSystemType.HFS:
            from src.core.hfs_classic_full import HFSClassicVolume
            self._volume = HFSClassicVolume(self.path)
            self._volume.open()
            
        elif self.fs_type == FileSystemType.APFS:
            from src.core.apfs.full_support import APFSContainerReader
            self._volume = APFSContainerReader(self.path)
            self._volume.open()
            
        elif self.fs_type == FileSystemType.CORESTORAGE:
            from src.core.corestorage_full import CoreStorageReader
            self._volume = CoreStorageReader(self.path)
            self._volume.open()
            
        else:
            raise ValueError(f"不支持的文件系统类型: {self.fs_type}")
            
    def close(self) -> None:
        """关闭卷"""
        if self._volume:
            self._volume.close()
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def get_info(self) -> Dict[str, Any]:
        """获取卷信息"""
        if not self._volume:
            return {}
            
        info = self._volume.get_info()
        info['fs_type'] = self.fs_type.value
        info['path'] = self.path
        return info
        
    def list_folder(self, folder_id: int = 2) -> List[Dict]:
        """
        列出文件夹内容
        
        Args:
            folder_id: 文件夹 ID
            
        Returns:
            文件/文件夹列表
        """
        if not self._volume:
            return []
            
        if hasattr(self._volume, 'list_folder'):
            return self._volume.list_folder(folder_id)
        elif hasattr(self._volume, 'list_directory'):
            # APFS 使用 list_directory
            entries = self._volume.list_directory(folder_id)
            # 转换为统一格式
            result = []
            for entry in entries:
                result.append({
                    'name': entry.get('name', ''),
                    'id': entry.get('oid', entry.get('id', 0)),
                    'type': entry.get('type', 'file'),
                    'size': entry.get('size', 0),
                    'create_date': entry.get('create_date', entry.get('date_added', 0)),
                    'mod_date': entry.get('mod_date', 0),
                })
            return result
            
        return []
        
    def read_file(self, file_id: int) -> bytes:
        """
        读取文件数据
        
        Args:
            file_id: 文件 ID
            
        Returns:
            文件数据
        """
        if not self._volume:
            return b''
            
        if hasattr(self._volume, 'read_file'):
            return self._volume.read_file(file_id)
        elif hasattr(self._volume, 'read_file_data'):
            return self._volume.read_file_data(file_id)
            
        return b''
        
    def get_file_info(self, file_id: int) -> Optional[Dict]:
        """
        获取文件信息
        
        Args:
            file_id: 文件 ID
            
        Returns:
            文件信息
        """
        if not self._volume:
            return None
            
        if hasattr(self._volume, 'get_file_info'):
            return self._volume.get_file_info(file_id)
            
        return None
        
    def is_encrypted(self) -> bool:
        """是否加密"""
        if not self._volume:
            return False
            
        if hasattr(self._volume, 'is_encrypted'):
            return self._volume.is_encrypted()
            
        return False
        
    def unlock(self, password: str) -> bool:
        """
        解锁加密卷
        
        Args:
            password: 密码
            
        Returns:
            是否成功
        """
        if not self._volume:
            return False
            
        if self.fs_type == FileSystemType.CORESTORAGE:
            from src.core.corestorage_full import CoreStorageDecryptor
            decryptor = CoreStorageDecryptor(self._volume)
            return decryptor.unlock_with_password(password)
            
        return True  # 未加密的卷直接返回成功


class UnifiedFileSystem:
    """
    统一文件系统管理器
    
    管理多个文件系统实例
    """
    
    def __init__(self):
        """初始化文件系统管理器"""
        self.volumes: Dict[str, UnifiedVolume] = {}
        
    def open(self, path: str) -> UnifiedVolume:
        """
        打开文件系统
        
        Args:
            path: 文件路径
            
        Returns:
            卷实例
        """
        if path in self.volumes:
            return self.volumes[path]
            
        volume = UnifiedVolume(path)
        volume.open()
        self.volumes[path] = volume
        return volume
        
    def close(self, path: str) -> None:
        """
        关闭文件系统
        
        Args:
            path: 文件路径
        """
        if path in self.volumes:
            self.volumes[path].close()
            del self.volumes[path]
            
    def close_all(self) -> None:
        """关闭所有文件系统"""
        for path in list(self.volumes.keys()):
            self.close(path)
            
    def get_volume(self, path: str) -> Optional[UnifiedVolume]:
        """
        获取卷实例
        
        Args:
            path: 文件路径
            
        Returns:
            卷实例
        """
        return self.volumes.get(path)
        
    def list_volumes(self) -> List[Dict]:
        """
        列出所有打开的卷
        
        Returns:
            卷信息列表
        """
        result = []
        for path, volume in self.volumes.items():
            info = volume.get_info()
            info['path'] = path
            result.append(info)
        return result


# =============================================================================
# 便捷函数
# =============================================================================

def open_volume(path: str) -> UnifiedVolume:
    """
    打开文件系统
    
    Args:
        path: 文件路径
        
    Returns:
        卷实例
    """
    volume = UnifiedVolume(path)
    volume.open()
    return volume


def detect_filesystem(path: str) -> FileSystemType:
    """
    检测文件系统类型
    
    Args:
        path: 文件路径
        
    Returns:
        文件系统类型
    """
    return FileSystemDetector.detect(path)


def get_supported_filesystems() -> List[str]:
    """
    获取支持的文件系统列表
    
    Returns:
        文件系统类型列表
    """
    return [fs.value for fs in FileSystemType if fs != FileSystemType.UNKNOWN]


def is_supported(path: str) -> bool:
    """
    检查文件是否支持
    
    Args:
        path: 文件路径
        
    Returns:
        是否支持
    """
    fs_type = detect_filesystem(path)
    return fs_type != FileSystemType.UNKNOWN
