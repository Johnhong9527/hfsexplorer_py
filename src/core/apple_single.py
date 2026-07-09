"""
Apple Single 文件支持

Apple Single 是一种文件格式，用于在非 Apple 文件系统上存储 Mac 文件。
它包含数据分支、资源分支和 Finder 信息。

文件格式：
- Header (26 bytes)
  - Magic: 0x00051600
  - Version: 0x00020000
  - Filler: 16 bytes
  - Number of entries: 2 bytes
- Entries
  - Entry ID (4 bytes)
  - Offset (4 bytes)
  - Length (4 bytes)
- Data
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import IntEnum


class AppleSingleError(Exception):
    """Apple Single 相关错误"""
    pass


class AppleSingleEntryType(IntEnum):
    """Apple Single 条目类型"""
    DATA_FORK = 1          # 数据分支
    RESOURCE_FORK = 2      # 资源分支
    REAL_NAME = 3          # 真实名称
    COMMENT = 4            # 注释
    ICON_BW = 5            # 黑白图标
    ICON_COLOR = 6         # 彩色图标
    FILE_INFO = 7          # 文件信息
    FINDER_INFO = 9        # Finder 信息
    DATES = 13             # 日期信息
    MACINTOSH_FILE_INFO = 14  # Mac 文件信息
    PRODOS_FILE_INFO = 15    # ProDOS 文件信息
    MSDOS_FILE_INFO = 16     # MS-DOS 文件信息
    SHORT_NAME = 18        # 短名称
    AFP_FILE_INFO = 19     # AFP 文件信息


# Apple Single 魔数
APPLE_SINGLE_MAGIC = 0x00051600
APPLE_DOUBLE_MAGIC = 0x00051607

# 版本
APPLE_SINGLE_VERSION = 0x00020000


@dataclass
class AppleSingleEntry:
    """
    Apple Single 条目
    
    Attributes:
        entry_type: 条目类型
        offset: 数据偏移
        length: 数据长度
        data: 条目数据
    """
    entry_type: int
    offset: int
    length: int
    data: bytes = b''


@dataclass
class AppleSingleFile:
    """
    Apple Single 文件
    
    Attributes:
        magic: 魔数
        version: 版本
        entries: 条目列表
        data_fork: 数据分支
        resource_fork: 资源分支
        finder_info: Finder 信息
        real_name: 真实名称
        comment: 注释
    """
    magic: int
    version: int
    entries: List[AppleSingleEntry]
    data_fork: bytes = b''
    resource_fork: bytes = b''
    finder_info: bytes = b''
    real_name: str = ''
    comment: str = ''
    
    @property
    def is_apple_single(self) -> bool:
        """是否为 Apple Single 文件"""
        return self.magic == APPLE_SINGLE_MAGIC
    
    @property
    def is_apple_double(self) -> bool:
        """是否为 Apple Double 文件"""
        return self.magic == APPLE_DOUBLE_MAGIC
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'AppleSingleFile':
        """
        从字节序列解析
        
        Args:
            data: 文件数据
        
        Returns:
            AppleSingleFile 对象
        """
        if len(data) < 26:
            raise AppleSingleError("数据太短，无法解析 Apple Single 文件")
        
        # 解析头部
        magic = struct.unpack_from('>I', data, 0)[0]
        version = struct.unpack_from('>I', data, 4)[0]
        
        # 验证魔数
        if magic not in (APPLE_SINGLE_MAGIC, APPLE_DOUBLE_MAGIC):
            raise AppleSingleError(f"无效的魔数: 0x{magic:08X}")
        
        # 填充字节 (16 bytes)
        filler = data[8:24]
        
        # 条目数量
        num_entries = struct.unpack_from('>H', data, 24)[0]
        
        # 解析条目
        entries = []
        offset = 26
        
        for i in range(num_entries):
            if offset + 12 > len(data):
                break
            
            entry_type = struct.unpack_from('>I', data, offset)[0]
            entry_offset = struct.unpack_from('>I', data, offset + 4)[0]
            entry_length = struct.unpack_from('>I', data, offset + 8)[0]
            
            # 读取条目数据
            if entry_offset + entry_length <= len(data):
                entry_data = data[entry_offset:entry_offset + entry_length]
            else:
                entry_data = b''
            
            entries.append(AppleSingleEntry(
                entry_type=entry_type,
                offset=entry_offset,
                length=entry_length,
                data=entry_data
            ))
            
            offset += 12
        
        # 创建文件对象
        apple_file = cls(
            magic=magic,
            version=version,
            entries=entries
        )
        
        # 解析各个条目
        for entry in entries:
            if entry.entry_type == AppleSingleEntryType.DATA_FORK:
                apple_file.data_fork = entry.data
            elif entry.entry_type == AppleSingleEntryType.RESOURCE_FORK:
                apple_file.resource_fork = entry.data
            elif entry.entry_type == AppleSingleEntryType.FINDER_INFO:
                apple_file.finder_info = entry.data
            elif entry.entry_type == AppleSingleEntryType.REAL_NAME:
                try:
                    apple_file.real_name = entry.data.decode('utf-8', errors='replace')
                except:
                    apple_file.real_name = entry.data.decode('mac-roman', errors='replace')
            elif entry.entry_type == AppleSingleEntryType.COMMENT:
                try:
                    apple_file.comment = entry.data.decode('utf-8', errors='replace')
                except:
                    apple_file.comment = entry.data.decode('mac-roman', errors='replace')
        
        return apple_file
    
    def to_bytes(self) -> bytes:
        """
        转换为字节序列
        
        Returns:
            文件数据
        """
        # 计算头部大小
        header_size = 26 + len(self.entries) * 12
        
        # 准备数据
        result = bytearray()
        
        # 写入头部
        result += struct.pack('>I', self.magic)
        result += struct.pack('>I', self.version)
        result += b'\x00' * 16  # 填充
        result += struct.pack('>H', len(self.entries))
        
        # 计算数据偏移
        data_offset = header_size
        
        # 写入条目头
        entries_data = bytearray()
        all_data = bytearray()
        
        for entry in self.entries:
            entries_data += struct.pack('>I', entry.entry_type)
            entries_data += struct.pack('>I', data_offset + len(all_data))
            entries_data += struct.pack('>I', len(entry.data))
            all_data += entry.data
        
        # 组合结果
        result += entries_data
        result += all_data
        
        return bytes(result)
    
    def get_entry(self, entry_type: int) -> Optional[AppleSingleEntry]:
        """
        获取指定类型的条目
        
        Args:
            entry_type: 条目类型
        
        Returns:
            条目对象，如果不存在则返回 None
        """
        for entry in self.entries:
            if entry.entry_type == entry_type:
                return entry
        return None
    
    def has_data_fork(self) -> bool:
        """是否有数据分支"""
        return len(self.data_fork) > 0
    
    def has_resource_fork(self) -> bool:
        """是否有资源分支"""
        return len(self.resource_fork) > 0
    
    def __str__(self) -> str:
        """字符串表示"""
        type_name = "Apple Single" if self.is_apple_single else "Apple Double"
        lines = [
            f"{type_name} File:",
            f"  Version: 0x{self.version:08X}",
            f"  Entries: {len(self.entries)}",
            f"  Data Fork: {len(self.data_fork)} bytes",
            f"  Resource Fork: {len(self.resource_fork)} bytes",
            f"  Real Name: {self.real_name}",
        ]
        return "\n".join(lines)


def open_apple_single(path: str) -> AppleSingleFile:
    """
    打开 Apple Single 文件
    
    Args:
        path: 文件路径
    
    Returns:
        AppleSingleFile 对象
    """
    with open(path, 'rb') as f:
        data = f.read()
    
    return AppleSingleFile.from_bytes(data)


def create_apple_single(data_fork: bytes = b'', resource_fork: bytes = b'',
                        finder_info: bytes = b'', real_name: str = '') -> bytes:
    """
    创建 Apple Single 文件
    
    Args:
        data_fork: 数据分支
        resource_fork: 资源分支
        finder_info: Finder 信息
        real_name: 真实名称
    
    Returns:
        文件数据
    """
    entries = []
    
    if data_fork:
        entries.append(AppleSingleEntry(
            entry_type=AppleSingleEntryType.DATA_FORK,
            offset=0,
            length=len(data_fork),
            data=data_fork
        ))
    
    if resource_fork:
        entries.append(AppleSingleEntry(
            entry_type=AppleSingleEntryType.RESOURCE_FORK,
            offset=0,
            length=len(resource_fork),
            data=resource_fork
        ))
    
    if finder_info:
        entries.append(AppleSingleEntry(
            entry_type=AppleSingleEntryType.FINDER_INFO,
            offset=0,
            length=len(finder_info),
            data=finder_info
        ))
    
    if real_name:
        name_bytes = real_name.encode('utf-8')
        entries.append(AppleSingleEntry(
            entry_type=AppleSingleEntryType.REAL_NAME,
            offset=0,
            length=len(name_bytes),
            data=name_bytes
        ))
    
    apple_file = AppleSingleFile(
        magic=APPLE_SINGLE_MAGIC,
        version=APPLE_SINGLE_VERSION,
        entries=entries,
        data_fork=data_fork,
        resource_fork=resource_fork,
        finder_info=finder_info,
        real_name=real_name
    )
    
    return apple_file.to_bytes()
