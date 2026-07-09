"""
.DS_Store 文件解析

.DS_Store (Desktop Services Store) 是 macOS 用于存储文件夹自定义属性的文件。
它包含文件夹的显示设置，如图标位置、视图模式等。
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import IntEnum


class DSStoreError(Exception):
    """DS_Store 相关错误"""
    pass


class DSStoreEntryType(IntEnum):
    """DS_Store 条目类型"""
    BOOL = 'bool'
    LONG = 'long'
    SHOR = 'shor'
    FOLD = 'fold'
    FEXT = 'fext'
    TYPE = 'type'
    BKGD = 'bkgd'
    LSVO = 'lsvo'
    ICVO = 'icvo'
    GLVO = 'glvo'
    BWSP = 'bwsp'
    LSVN = 'lsVN'
    ICVN = 'icVN'
    GLVN = 'glVN'
    Iloc = 'Iloc'
    vstl = 'vstl'
    dils = 'dils'
    fwsw = 'fwsw'
    fwvh = 'fwvh'
    lfwt = 'lfwt'
    lsvp = 'lsvp'
    lsvP = 'lsvP'
    lsvt = 'lsvt'
    lsvu = 'lsvu'
    lsvp = 'lsvp'


@dataclass
class DSStoreEntry:
    """
    DS_Store 条目
    
    Attributes:
        filename: 文件名
        entry_type: 条目类型
        data: 数据
    """
    filename: str
    entry_type: str
    data: Any


@dataclass
class DSStoreFile:
    """
    DS_Store 文件
    
    Attributes:
        entries: 条目列表
    """
    entries: List[DSStoreEntry] = field(default_factory=list)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DSStoreFile':
        """
        从字节序列解析
        
        Args:
            data: DS_Store 数据
        
        Returns:
            DSStoreFile 对象
        """
        ds_store = cls()
        
        try:
            ds_store._parse(data)
        except Exception as e:
            raise DSStoreError(f"解析 DS_Store 失败: {e}")
        
        return ds_store
    
    def _parse(self, data: bytes):
        """
        解析 DS_Store 数据
        
        Args:
            data: 数据
        """
        # DS_Store 文件格式比较复杂，这里只做基本解析
        # 完整实现需要处理 Buddy Allocator 和 Bookkeeping 数据
        
        # 验证魔数
        if len(data) < 4:
            raise DSStoreError("数据太短")
        
        # 检查是否是有效的 DS_Store
        # DS_Store 通常以 'Bud1' 开头
        magic = data[:4]
        
        if magic == b'Bud1':
            # Buddy Allocator 格式
            self._parse_buddy_allocator(data)
        elif magic == b'\x00\x00\x00\x01':
            # 另一种格式
            self._parse_simple(data)
        else:
            # 尝试简单解析
            self._parse_simple(data)
    
    def _parse_buddy_allocator(self, data: bytes):
        """
        解析 Buddy Allocator 格式
        
        Args:
            data: 数据
        """
        # Buddy Allocator 头部
        # 0-4: 魔数 'Bud1'
        # 4-8: 未知
        # 8-12: 偏移表偏移
        # 12-16: 未知
        # 16-20: 块数量
        
        if len(data) < 20:
            return
        
        # 获取偏移表偏移
        offset_table_offset = struct.unpack_from('>I', data, 8)[0]
        
        # 解析偏移表
        if offset_table_offset + 4 <= len(data):
            num_blocks = struct.unpack_from('>I', data, offset_table_offset)[0]
            
            # 解析每个块
            current_offset = offset_table_offset + 4
            
            for i in range(min(num_blocks, 1000)):  # 限制块数量
                if current_offset + 8 > len(data):
                    break
                
                # 块偏移和大小
                block_offset = struct.unpack_from('>I', data, current_offset)[0]
                block_size = struct.unpack_from('>I', data, current_offset + 4)[0]
                
                # 解析块
                if block_offset + block_size <= len(data):
                    self._parse_block(data, block_offset, block_size)
                
                current_offset += 8
    
    def _parse_simple(self, data: bytes):
        """
        解析简单格式
        
        Args:
            data: 数据
        """
        # 简单扫描查找条目
        # 这种方法不完整，但可以提取一些信息
        
        offset = 0
        while offset < len(data) - 8:
            # 查找文件名长度
            try:
                # 尝试读取长度
                name_length = struct.unpack_from('>I', data, offset)[0]
                
                if 0 < name_length < 256:
                    # 读取文件名
                    if offset + 4 + name_length <= len(data):
                        name_bytes = data[offset + 4:offset + 4 + name_length]
                        try:
                            filename = name_bytes.decode('utf-16-be')
                        except:
                            filename = name_bytes.decode('ascii', errors='replace')
                        
                        # 查找类型标识
                        type_offset = offset + 4 + name_length
                        if type_offset + 4 <= len(data):
                            entry_type = data[type_offset:type_offset + 4]
                            
                            # 创建条目
                            entry = DSStoreEntry(
                                filename=filename,
                                entry_type=entry_type.decode('ascii', errors='replace'),
                                data=data[type_offset:type_offset + 16]
                            )
                            self.entries.append(entry)
                
                offset += 1
            except:
                offset += 1
    
    def _parse_block(self, data: bytes, offset: int, size: int):
        """
        解析数据块
        
        Args:
            data: 完整数据
            offset: 块偏移
            size: 块大小
        """
        # 块格式：
        # 0-4: 记录数量
        # 4+: 记录
        
        if size < 4:
            return
        
        num_records = struct.unpack_from('>I', data, offset)[0]
        
        current = offset + 4
        
        for i in range(num_records):
            if current + 8 > offset + size:
                break
            
            # 读取文件名长度 (Unicode, 所以要 * 2)
            name_length = struct.unpack_from('>I', data, current)[0]
            
            if name_length > 256:
                break
            
            current += 4
            
            # 读取文件名
            if current + name_length * 2 > offset + size:
                break
            
            name_bytes = data[current:current + name_length * 2]
            try:
                filename = name_bytes.decode('utf-16-be')
            except:
                filename = name_bytes.decode('ascii', errors='replace')
            
            current += name_length * 2
            
            # 读取类型
            if current + 4 > offset + size:
                break
            
            entry_type = data[current:current + 4].decode('ascii', errors='replace')
            current += 4
            
            # 读取数据长度
            if current + 4 > offset + size:
                break
            
            data_length = struct.unpack_from('>I', data, current)[0]
            current += 4
            
            # 读取数据
            if current + data_length > offset + size:
                break
            
            entry_data = data[current:current + data_length]
            current += data_length
            
            # 创建条目
            entry = DSStoreEntry(
                filename=filename,
                entry_type=entry_type,
                data=entry_data
            )
            self.entries.append(entry)
    
    def get_entries_for_file(self, filename: str) -> List[DSStoreEntry]:
        """
        获取指定文件的条目
        
        Args:
            filename: 文件名
        
        Returns:
            条目列表
        """
        return [e for e in self.entries if e.filename == filename]
    
    def get_icon_position(self, filename: str) -> Optional[tuple]:
        """
        获取图标位置
        
        Args:
            filename: 文件名
        
        Returns:
            (x, y) 元组，如果不存在则返回 None
        """
        for entry in self.entries:
            if entry.filename == filename and entry.entry_type == 'Iloc':
                if len(entry.data) >= 8:
                    x = struct.unpack_from('>I', entry.data, 0)[0]
                    y = struct.unpack_from('>I', entry.data, 4)[0]
                    return (x, y)
        return None
    
    def get_view_style(self, filename: str) -> Optional[str]:
        """
        获取视图样式
        
        Args:
            filename: 文件名
        
        Returns:
            视图样式字符串
        """
        for entry in self.entries:
            if entry.filename == filename and entry.entry_type == 'vstl':
                return entry.data.decode('ascii', errors='replace').strip('\x00')
        return None
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"DSStoreFile(entries={len(self.entries)})"


def open_ds_store(path: str) -> DSStoreFile:
    """
    打开 DS_Store 文件
    
    Args:
        path: 文件路径
    
    Returns:
        DSStoreFile 对象
    """
    with open(path, 'rb') as f:
        data = f.read()
    
    return DSStoreFile.from_bytes(data)
