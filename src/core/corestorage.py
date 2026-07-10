"""
CoreStorage 支持

CoreStorage 是 Apple 的逻辑卷管理器，用于 FileVault 2 加密。
它提供了一个抽象层，允许在物理卷上创建逻辑卷。
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import IntEnum


class CoreStorageError(Exception):
    """CoreStorage 相关错误"""
    pass


# CoreStorage 签名
CORESTORAGE_SIGNATURE = b'CS'


class CoreStorageVolumeType(IntEnum):
    """CoreStorage 卷类型"""
    PHYSICAL = 0x01      # 物理卷
    LOGICAL = 0x02       # 逻辑卷
    ENCRYPTED = 0x03     # 加密卷


@dataclass
class CoreStorageHeader:
    """
    CoreStorage 头部
    
    Attributes:
        signature: 签名 'CS'
        version: 版本
        volume_type: 卷类型
        uuid: 卷 UUID
        block_size: 块大小
        total_blocks: 总块数
        free_blocks: 空闲块数
        data_start: 数据起始块
        data_length: 数据长度（块数）
    """
    signature: bytes
    version: int
    volume_type: int
    uuid: str
    block_size: int
    total_blocks: int
    free_blocks: int
    data_start: int
    data_length: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'CoreStorageHeader':
        """从字节序列解析"""
        if len(data) < 512:
            raise CoreStorageError("数据太短")
        
        signature = data[88:90]
        if signature != CORESTORAGE_SIGNATURE:
            raise CoreStorageError(f"无效的签名: {signature}")
        
        version = struct.unpack_from('>I', data, 90)[0]
        volume_type = struct.unpack_from('>I', data, 94)[0]
        
        # UUID (16 bytes)
        uuid_data = data[98:114]
        uuid = _format_uuid(uuid_data)
        
        block_size = struct.unpack_from('>I', data, 114)[0]
        total_blocks = struct.unpack_from('>Q', data, 118)[0]
        free_blocks = struct.unpack_from('>Q', data, 126)[0]
        
        data_start = struct.unpack_from('>Q', data, 134)[0]
        data_length = struct.unpack_from('>Q', data, 142)[0]
        
        return cls(
            signature=signature,
            version=version,
            volume_type=volume_type,
            uuid=uuid,
            block_size=block_size,
            total_blocks=total_blocks,
            free_blocks=free_blocks,
            data_start=data_start,
            data_length=data_length
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == CORESTORAGE_SIGNATURE
    
    @property
    def is_encrypted(self) -> bool:
        """是否加密"""
        return self.volume_type == CoreStorageVolumeType.ENCRYPTED
    
    @property
    def volume_size(self) -> int:
        """卷大小（字节）"""
        return self.block_size * self.total_blocks
    
    def __str__(self) -> str:
        """字符串表示"""
        type_names = {
            CoreStorageVolumeType.PHYSICAL: "物理卷",
            CoreStorageVolumeType.LOGICAL: "逻辑卷",
            CoreStorageVolumeType.ENCRYPTED: "加密卷",
        }
        
        return (
            f"CoreStorage Header:\n"
            f"  Signature: {self.signature}\n"
            f"  Version: {self.version}\n"
            f"  Type: {type_names.get(self.volume_type, '未知')}\n"
            f"  UUID: {self.uuid}\n"
            f"  Block Size: {self.block_size:,}\n"
            f"  Total Blocks: {self.total_blocks:,}\n"
            f"  Free Blocks: {self.free_blocks:,}\n"
            f"  Volume Size: {self.volume_size:,} bytes\n"
            f"  Encrypted: {self.is_encrypted}"
        )


@dataclass
class CoreStorageKey:
    """
    CoreStorage 密钥
    
    Attributes:
        uuid: 密钥 UUID
        key_data: 密钥数据
        wrapped_key: 包装后的密钥
    """
    uuid: str
    key_data: bytes
    wrapped_key: bytes


def _format_uuid(data: bytes) -> str:
    """格式化 UUID"""
    if len(data) < 16:
        return "00000000-0000-0000-0000-000000000000"
    
    return (
        f"{data[0:4].hex()}-"
        f"{data[4:6].hex()}-"
        f"{data[6:8].hex()}-"
        f"{data[8:10].hex()}-"
        f"{data[10:16].hex()}"
    )


def parse_corestorage_header(stream, offset: int = 0) -> CoreStorageHeader:
    """
    解析 CoreStorage 头部
    
    Args:
        stream: 二进制流
        offset: 偏移量
    
    Returns:
        CoreStorageHeader 对象
    """
    stream.seek(offset)
    data = stream.read(512)
    
    return CoreStorageHeader.from_bytes(data)


def is_corestorage(stream, offset: int = 0) -> bool:
    """
    检查是否是 CoreStorage 卷
    
    Args:
        stream: 二进制流
        offset: 偏移量
    
    Returns:
        是否是 CoreStorage 卷
    """
    try:
        stream.seek(offset + 88)
        signature = stream.read(2)
        return signature == CORESTORAGE_SIGNATURE
    except:
        return False


def find_corestorage_keybag(stream, header: CoreStorageHeader) -> Optional[int]:
    """
    查找 CoreStorage 密钥包
    
    Args:
        stream: 二进制流
        header: CoreStorage 头部
    
    Returns:
        密钥包偏移，如果未找到则返回 None
    """
    # 密钥包通常在卷的开头
    # 这里提供一个简化的查找逻辑
    
    try:
        # 查找 'kbag' 签名
        stream.seek(0)
        data = stream.read(4096)
        
        pos = data.find(b'kbag')
        if pos >= 0:
            return pos
    except:
        pass
    
    return None


@dataclass
class CoreStorageVolume:
    """
    CoreStorage 卷
    
    Attributes:
        header: 头部信息
        stream: 文件流
    """
    header: CoreStorageHeader
    stream: Any  # BinaryIO
    
    @classmethod
    def open(cls, path: str) -> 'CoreStorageVolume':
        """
        打开 CoreStorage 卷
        
        Args:
            path: 文件路径
        
        Returns:
            CoreStorageVolume 对象
        """
        stream = open(path, 'rb')
        
        try:
            header = parse_corestorage_header(stream)
            return cls(header=header, stream=stream)
        except Exception:
            stream.close()
            raise
    
    def close(self):
        """关闭文件"""
        self.stream.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    @property
    def is_encrypted(self) -> bool:
        """是否加密"""
        return self.header.is_encrypted
    
    def get_info(self) -> Dict[str, Any]:
        """获取卷信息"""
        return {
            'signature': self.header.signature.decode('ascii', errors='replace'),
            'version': self.header.version,
            'type': 'encrypted' if self.header.is_encrypted else 'normal',
            'uuid': self.header.uuid,
            'block_size': self.header.block_size,
            'total_blocks': self.header.total_blocks,
            'free_blocks': self.header.free_blocks,
            'volume_size': self.header.volume_size,
        }
