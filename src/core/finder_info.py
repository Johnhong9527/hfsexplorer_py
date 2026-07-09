"""
Finder Info 支持

Finder Info 是 macOS 用于存储文件元数据的结构。
它包含文件类型、创建者、图标位置等信息。
"""

import struct
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import IntFlag


class FinderFlags(IntFlag):
    """Finder 标志"""
    kIsOnDesk = 0x0001              # 在桌面上
    kColor = 0x000E                 # 颜色标签
    kIsShared = 0x0040              # 共享
    kHasNoINITs = 0x0080            # 没有 INIT
    kHasBeenInited = 0x0100         # 已初始化
    kHasCustomIcon = 0x0400         # 自定义图标
    kIsStationery = 0x0800          # 模板
    kNameLocked = 0x1000            # 名称锁定
    kHasBundle = 0x2000             # 有 Bundle
    kIsInvisible = 0x4000           # 隐藏
    kIsAlias = 0x8000               # 别名


class ExtendedFinderFlags(IntFlag):
    """扩展 Finder 标志"""
    kExtendedFlagsAreInvalid = 0x8000  # 扩展标志无效
    kExtendedFlagHasCustomBadge = 0x0100  # 自定义徽章
    kExtendedFlagHasRoutingInfo = 0x0004  # 路由信息


@dataclass
class FinderInfo:
    """
    Finder Info
    
    文件的 16 字节 Finder 信息。
    
    Attributes:
        file_type: 文件类型 (4 字符)
        file_creator: 文件创建者 (4 字符)
        finder_flags: Finder 标志
        location_x: 图标位置 X
        location_y: 图标位置 Y
        reserved: 保留字段
    """
    file_type: str = '????'
    file_creator: str = '????'
    finder_flags: int = 0
    location_x: int = 0
    location_y: int = 0
    reserved: int = 0
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'FinderInfo':
        """
        从字节序列解析
        
        Args:
            data: 数据
            offset: 偏移量
        
        Returns:
            FinderInfo 对象
        """
        if len(data) < offset + 16:
            return cls()
        
        file_type = data[offset:offset + 4].decode('ascii', errors='replace')
        file_creator = data[offset + 4:offset + 8].decode('ascii', errors='replace')
        finder_flags = struct.unpack_from('>H', data, offset + 8)[0]
        location_x = struct.unpack_from('>h', data, offset + 10)[0]
        location_y = struct.unpack_from('>h', data, offset + 12)[0]
        reserved = struct.unpack_from('>H', data, offset + 14)[0]
        
        return cls(
            file_type=file_type,
            file_creator=file_creator,
            finder_flags=finder_flags,
            location_x=location_x,
            location_y=location_y,
            reserved=reserved
        )
    
    def to_bytes(self) -> bytes:
        """
        转换为字节序列
        
        Returns:
            16 字节数据
        """
        result = self.file_type.encode('ascii')[:4].ljust(4, b'?')
        result += self.file_creator.encode('ascii')[:4].ljust(4, b'?')
        result += struct.pack('>H', self.finder_flags)
        result += struct.pack('>h', self.location_x)
        result += struct.pack('>h', self.location_y)
        result += struct.pack('>H', self.reserved)
        return result
    
    @property
    def is_on_desk(self) -> bool:
        """是否在桌面上"""
        return bool(self.finder_flags & FinderFlags.kIsOnDesk)
    
    @property
    def color_label(self) -> int:
        """颜色标签"""
        return (self.finder_flags & FinderFlags.kColor) >> 1
    
    @property
    def is_shared(self) -> bool:
        """是否共享"""
        return bool(self.finder_flags & FinderFlags.kIsShared)
    
    @property
    def has_custom_icon(self) -> bool:
        """是否有自定义图标"""
        return bool(self.finder_flags & FinderFlags.kHasCustomIcon)
    
    @property
    def is_stationery(self) -> bool:
        """是否是模板"""
        return bool(self.finder_flags & FinderFlags.kIsStationery)
    
    @property
    def name_locked(self) -> bool:
        """名称是否锁定"""
        return bool(self.finder_flags & FinderFlags.kNameLocked)
    
    @property
    def has_bundle(self) -> bool:
        """是否有 Bundle"""
        return bool(self.finder_flags & FinderFlags.kHasBundle)
    
    @property
    def is_invisible(self) -> bool:
        """是否隐藏"""
        return bool(self.finder_flags & FinderFlags.kIsInvisible)
    
    @property
    def is_alias(self) -> bool:
        """是否是别名"""
        return bool(self.finder_flags & FinderFlags.kIsAlias)
    
    @property
    def icon_position(self) -> Tuple[int, int]:
        """图标位置"""
        return (self.location_x, self.location_y)
    
    def __str__(self) -> str:
        """字符串表示"""
        lines = [
            f"Finder Info:",
            f"  Type: {self.file_type}",
            f"  Creator: {self.file_creator}",
            f"  Flags: 0x{self.finder_flags:04X}",
            f"  Location: ({self.location_x}, {self.location_y})",
        ]
        
        flags = []
        if self.is_on_desk:
            flags.append("OnDesk")
        if self.has_custom_icon:
            flags.append("CustomIcon")
        if self.is_invisible:
            flags.append("Invisible")
        if self.is_alias:
            flags.append("Alias")
        if self.has_bundle:
            flags.append("Bundle")
        if self.name_locked:
            flags.append("NameLocked")
        
        if flags:
            lines.append(f"  Flags: {', '.join(flags)}")
        
        return "\n".join(lines)


@dataclass
class ExtendedFinderInfo:
    """
    扩展 Finder Info
    
    文件的 16 字节扩展 Finder 信息。
    
    Attributes:
        reserved1: 保留字段 1
        extended_flags: 扩展标志
        reserved2: 保留字段 2
        put_away_folder_id: Put Away 文件夹 ID
    """
    reserved1: int = 0
    extended_flags: int = 0
    reserved2: int = 0
    put_away_folder_id: int = 0
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ExtendedFinderInfo':
        """
        从字节序列解析
        
        Args:
            data: 数据
            offset: 偏移量
        
        Returns:
            ExtendedFinderInfo 对象
        """
        if len(data) < offset + 16:
            return cls()
        
        reserved1 = struct.unpack_from('>I', data, offset)[0]
        extended_flags = struct.unpack_from('>H', data, offset + 4)[0]
        reserved2 = struct.unpack_from('>H', data, offset + 6)[0]
        put_away_folder_id = struct.unpack_from('>I', data, offset + 8)[0]
        
        return cls(
            reserved1=reserved1,
            extended_flags=extended_flags,
            reserved2=reserved2,
            put_away_folder_id=put_away_folder_id
        )
    
    def to_bytes(self) -> bytes:
        """
        转换为字节序列
        
        Returns:
            16 字节数据
        """
        result = struct.pack('>I', self.reserved1)
        result += struct.pack('>H', self.extended_flags)
        result += struct.pack('>H', self.reserved2)
        result += struct.pack('>I', self.put_away_folder_id)
        result += struct.pack('>I', 0)  # 保留
        return result
    
    @property
    def has_custom_badge(self) -> bool:
        """是否有自定义徽章"""
        return bool(self.extended_flags & ExtendedFinderFlags.kExtendedFlagHasCustomBadge)
    
    @property
    def has_routing_info(self) -> bool:
        """是否有路由信息"""
        return bool(self.extended_flags & ExtendedFinderFlags.kExtendedFlagHasRoutingInfo)
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"Extended Finder Info:\n"
            f"  Flags: 0x{self.extended_flags:04X}\n"
            f"  Put Away Folder ID: {self.put_away_folder_id}"
        )


# 常见文件类型和创建者
FILE_TYPES = {
    'TEXT': '纯文本',
    'PICT': '图片',
    'JPEG': 'JPEG 图片',
    'GIFf': 'GIF 图片',
    'PNGf': 'PNG 图片',
    'TIFF': 'TIFF 图片',
    'PDF ': 'PDF 文档',
    'ZIP ': 'ZIP 压缩',
    'SITD': 'StuffIt 压缩',
    'APPL': '应用程序',
    'APPD': '应用程序目录',
    'CDEV': '控制面板',
    'INIT': '扩展',
    'FFIL': '字体文件',
    'NFNT': '字体',
    'snd ': '声音',
    'MIDI': 'MIDI',
    'MooV': 'QuickTime 影片',
    'MPEG': 'MPEG 影片',
    'WAVE': 'WAV 声音',
    'AIFF': 'AIFF 声音',
}

FILE_CREATORS = {
    'MACS': 'Finder',
    'MOSS': 'Netscape',
    'MSIE': 'Internet Explorer',
    'MOzz': 'Mozilla',
    'CHIM': 'Chimera',
    'SAFA': 'Safari',
    'ttxt': 'SimpleText',
    'R*ch': 'BBEdit',
    'CWIE': 'ClarisWorks',
    'WPC8': 'WordPerfect',
    'MSWD': 'Microsoft Word',
    'XCEL': 'Microsoft Excel',
    'PPNT': 'Microsoft PowerPoint',
    'ALD3': 'Aldus PageMaker',
    'FH50': 'FreeHand',
    'ARTS': 'Adobe Illustrator',
    '8BIM': 'Photoshop',
    'JVWR': 'Apple Video Player',
    'TVOD': 'QuickTime Player',
    'MP3 ': 'MP3 Player',
    'iTunes': 'iTunes',
}


def get_file_type_description(file_type: str) -> str:
    """获取文件类型描述"""
    return FILE_TYPES.get(file_type, file_type)


def get_file_creator_description(file_creator: str) -> str:
    """获取文件创建者描述"""
    return FILE_CREATORS.get(file_creator, file_creator)
