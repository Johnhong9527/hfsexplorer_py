"""
HFS+ 数据结构定义

定义 HFS+ 文件系统中使用的数据结构，包括 Extent 描述符、Fork 数据、Finder Info 和卷头。
"""

import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from .constants import (
    EXTENT_DESCRIPTOR_SIZE,
    EXTENT_RECORD_COUNT,
    EXTENT_RECORD_SIZE,
    FORK_DATA_SIZE,
    FINDER_INFO_SIZE,
    VOLUME_HEADER_SIZE,
    HFS_EPOCH_OFFSET,
    SIGNATURE_HFS_PLUS,
    SIGNATURE_HFSX,
    VolumeAttributes,
    signature_to_string,
    attributes_to_string,
    hfs_date_to_timestamp,
)


@dataclass
class ExtentDescriptor:
    """
    Extent 描述符
    
    描述文件的一个连续区域。
    
    Attributes:
        start_block: 起始分配块号
        block_count: 分配块数量
    """
    start_block: int  # UInt32
    block_count: int  # UInt32
    
    @property
    def end_block(self) -> int:
        """结束块号（不包含）"""
        return self.start_block + self.block_count
    
    @property
    def is_empty(self) -> bool:
        """是否为空 extent"""
        return self.block_count == 0
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        return struct.pack('>II', self.start_block, self.block_count)
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ExtentDescriptor':
        """从字节序列解析"""
        if len(data) < offset + EXTENT_DESCRIPTOR_SIZE:
            raise ValueError(f"数据不足: 需要 {EXTENT_DESCRIPTOR_SIZE} 字节, 实际 {len(data) - offset} 字节")
        
        start_block, block_count = struct.unpack_from('>II', data, offset)
        return cls(start_block=start_block, block_count=block_count)
    
    def __str__(self) -> str:
        return f"ExtentDescriptor(start={self.start_block}, count={self.block_count})"


@dataclass
class ForkData:
    """
    Fork 数据
    
    描述文件的一个分支（数据分支或资源分支）。
    
    Attributes:
        logical_size: 逻辑大小（字节）
        clump_size: Clump 大小（字节）
        total_blocks: 总分配块数
        extents: 内联 extent 描述符列表（最多 8 个）
    """
    logical_size: int  # UInt64
    clump_size: int    # UInt32
    total_blocks: int  # UInt32
    extents: List[ExtentDescriptor] = field(default_factory=list)
    
    @property
    def is_empty(self) -> bool:
        """是否为空 fork"""
        return self.logical_size == 0 and self.total_blocks == 0
    
    @property
    def has_overflow_extents(self) -> bool:
        """是否有溢出 extent（超过 8 个）"""
        return len(self.extents) > EXTENT_RECORD_COUNT
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        # 打包基本字段
        result = struct.pack('>QII', self.logical_size, self.clump_size, self.total_blocks)
        
        # 打包 extent 记录（最多 8 个）
        for i in range(EXTENT_RECORD_COUNT):
            if i < len(self.extents):
                result += self.extents[i].to_bytes()
            else:
                result += b'\x00' * EXTENT_DESCRIPTOR_SIZE
        
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ForkData':
        """从字节序列解析"""
        if len(data) < offset + FORK_DATA_SIZE:
            raise ValueError(f"数据不足: 需要 {FORK_DATA_SIZE} 字节, 实际 {len(data) - offset} 字节")
        
        # 解析基本字段
        logical_size, clump_size, total_blocks = struct.unpack_from('>QII', data, offset)
        
        # 解析 extent 记录
        extents = []
        for i in range(EXTENT_RECORD_COUNT):
            ext_offset = offset + 16 + i * EXTENT_DESCRIPTOR_SIZE
            ext = ExtentDescriptor.from_bytes(data, ext_offset)
            if not ext.is_empty:
                extents.append(ext)
        
        return cls(
            logical_size=logical_size,
            clump_size=clump_size,
            total_blocks=total_blocks,
            extents=extents
        )
    
    def __str__(self) -> str:
        return (f"ForkData(size={self.logical_size}, clump={self.clump_size}, "
                f"blocks={self.total_blocks}, extents={len(self.extents)})")


@dataclass
class FinderInfo:
    """
    Finder 信息
    
    存储 Mac OS Finder 使用的信息。
    
    Attributes:
        blessed_system_folder: 系统文件夹 CNID
        startup_application_parent_folder: 启动应用程序父文件夹 CNID
        open_folder_list: 打开文件夹列表中的第一个文件夹
        alternate_macos_blessed_system_folder: 旧版 Mac OS 系统文件夹 CNID
        reserved: 保留字段
        alternate_macosx_blessed_system_folder: Mac OS X 系统文件夹 CNID
        volume_uuid: 卷唯一标识符
    """
    blessed_system_folder: int = 0                   # UInt32
    startup_application_parent_folder: int = 0       # UInt32
    open_folder_list: int = 0                        # UInt32
    alternate_macos_blessed_system_folder: int = 0   # UInt32
    reserved: int = 0                                # UInt32
    alternate_macosx_blessed_system_folder: int = 0  # UInt32
    volume_uuid: int = 0                             # UInt64
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        return struct.pack(
            '>IIIIIIQ',
            self.blessed_system_folder,
            self.startup_application_parent_folder,
            self.open_folder_list,
            self.alternate_macos_blessed_system_folder,
            self.reserved,
            self.alternate_macosx_blessed_system_folder,
            self.volume_uuid
        )
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'FinderInfo':
        """从字节序列解析"""
        if len(data) < offset + FINDER_INFO_SIZE:
            raise ValueError(f"数据不足: 需要 {FINDER_INFO_SIZE} 字节, 实际 {len(data) - offset} 字节")
        
        (
            blessed_system_folder,
            startup_application_parent_folder,
            open_folder_list,
            alternate_macos_blessed_system_folder,
            reserved,
            alternate_macosx_blessed_system_folder,
            volume_uuid
        ) = struct.unpack_from('>IIIIIIQ', data, offset)
        
        return cls(
            blessed_system_folder=blessed_system_folder,
            startup_application_parent_folder=startup_application_parent_folder,
            open_folder_list=open_folder_list,
            alternate_macos_blessed_system_folder=alternate_macos_blessed_system_folder,
            reserved=reserved,
            alternate_macosx_blessed_system_folder=alternate_macosx_blessed_system_folder,
            volume_uuid=volume_uuid
        )
    
    def __str__(self) -> str:
        return f"FinderInfo(uuid=0x{self.volume_uuid:016X})"


@dataclass
class HFSPlusVolumeHeader:
    """
    HFS+ 卷头
    
    位于卷偏移量 1024 处，大小 512 字节。
    
    Attributes:
        signature: 签名 (0x482B = HFS+, 0x4858 = HFSX)
        version: 版本号
        attributes: 属性标志
        last_mounted_version: 最后挂载的系统版本
        journal_info_block: 日志信息块号
        create_date: 创建日期
        modify_date: 修改日期
        backup_date: 备份日期
        checked_date: 最后检查日期
        file_count: 文件数量
        folder_count: 文件夹数量
        block_size: 分配块大小（字节）
        total_blocks: 总分配块数
        free_blocks: 空闲分配块数
        next_allocation: 下一个分配搜索起始块
        rsrc_clump_size: 默认资源分支 clump 大小
        data_clump_size: 默认数据分支 clump 大小
        next_catalog_id: 下一个未使用的 Catalog Node ID
        write_count: 卷写入计数
        encodings_bitmap: 编码位图
        finder_info: Finder 信息
        allocation_file: 分配文件 fork 数据
        extents_file: Extents 溢出文件 fork 数据
        catalog_file: Catalog 文件 fork 数据
        attributes_file: 属性文件 fork 数据
        startup_file: 启动文件 fork 数据
    """
    signature: int  # UInt16
    version: int  # UInt16
    attributes: int  # UInt32
    last_mounted_version: str  # 4-byte ASCII
    journal_info_block: int  # UInt32
    create_date: int  # UInt32 (本地时间)
    modify_date: int  # UInt32 (本地时间)
    backup_date: int  # UInt32 (本地时间)
    checked_date: int  # UInt32 (本地时间)
    file_count: int  # UInt32
    folder_count: int  # UInt32
    block_size: int  # UInt32
    total_blocks: int  # UInt32
    free_blocks: int  # UInt32
    next_allocation: int  # UInt32
    rsrc_clump_size: int  # UInt32
    data_clump_size: int  # UInt32
    next_catalog_id: int  # UInt32
    write_count: int  # UInt32
    encodings_bitmap: int  # UInt64
    finder_info: FinderInfo
    allocation_file: ForkData
    extents_file: ForkData
    catalog_file: ForkData
    attributes_file: ForkData
    startup_file: ForkData
    
    @property
    def is_hfs_plus(self) -> bool:
        """是否为 HFS+ 卷"""
        return self.signature == SIGNATURE_HFS_PLUS
    
    @property
    def is_hfsx(self) -> bool:
        """是否为 HFSX 卷"""
        return self.signature == SIGNATURE_HFSX
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature in (SIGNATURE_HFS_PLUS, SIGNATURE_HFSX)
    
    @property
    def is_journaled(self) -> bool:
        """是否启用日志"""
        return bool(self.attributes & VolumeAttributes.VOLUME_JOURNALED)
    
    @property
    def is_locked(self) -> bool:
        """是否被锁定"""
        return bool(
            self.attributes & VolumeAttributes.HARDWARE_LOCK or
            self.attributes & VolumeAttributes.SOFTWARE_LOCK
        )
    
    @property
    def is_cleanly_unmounted(self) -> bool:
        """是否已干净卸载"""
        return bool(self.attributes & VolumeAttributes.VOLUME_UNMOUNTED)
    
    @property
    def volume_size(self) -> int:
        """卷大小（字节）"""
        return self.block_size * self.total_blocks
    
    @property
    def free_space(self) -> int:
        """空闲空间（字节）"""
        return self.block_size * self.free_blocks
    
    @property
    def used_space(self) -> int:
        """已用空间（字节）"""
        return self.block_size * (self.total_blocks - self.free_blocks)
    
    @property
    def create_datetime(self) -> Optional[datetime]:
        """创建日期时间"""
        if self.create_date == 0:
            return None
        timestamp = hfs_date_to_timestamp(self.create_date)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    @property
    def modify_datetime(self) -> Optional[datetime]:
        """修改日期时间"""
        if self.modify_date == 0:
            return None
        timestamp = hfs_date_to_timestamp(self.modify_date)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    @property
    def backup_datetime(self) -> Optional[datetime]:
        """备份日期时间"""
        if self.backup_date == 0:
            return None
        timestamp = hfs_date_to_timestamp(self.backup_date)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    @property
    def checked_datetime(self) -> Optional[datetime]:
        """检查日期时间"""
        if self.checked_date == 0:
            return None
        timestamp = hfs_date_to_timestamp(self.checked_date)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        # 打包基本字段 (20 个值)
        result = struct.pack(
            '>HH I I I I I I I I I I I I I I I I I Q',
            self.signature,
            self.version,
            self.attributes,
            int.from_bytes(self.last_mounted_version.encode('ascii')[:4].ljust(4, b'\x00'), 'big'),
            self.journal_info_block,
            self.create_date,
            self.modify_date,
            self.backup_date,
            self.checked_date,
            self.file_count,
            self.folder_count,
            self.block_size,
            self.total_blocks,
            self.free_blocks,
            self.next_allocation,
            self.rsrc_clump_size,
            self.data_clump_size,
            self.next_catalog_id,
            self.write_count,
            self.encodings_bitmap
        )
        
        # 打包 Finder Info
        result += self.finder_info.to_bytes()
        
        # 打包 5 个 fork 数据
        result += self.allocation_file.to_bytes()
        result += self.extents_file.to_bytes()
        result += self.catalog_file.to_bytes()
        result += self.attributes_file.to_bytes()
        result += self.startup_file.to_bytes()
        
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSPlusVolumeHeader':
        """从字节序列解析"""
        if len(data) < offset + VOLUME_HEADER_SIZE:
            raise ValueError(f"数据不足: 需要 {VOLUME_HEADER_SIZE} 字节, 实际 {len(data) - offset} 字节")
        
        # 解析基本字段 (20 个值)
        (
            signature,
            version,
            attributes,
            last_mounted_version_raw,
            journal_info_block,
            create_date,
            modify_date,
            backup_date,
            checked_date,
            file_count,
            folder_count,
            block_size,
            total_blocks,
            free_blocks,
            next_allocation,
            rsrc_clump_size,
            data_clump_size,
            next_catalog_id,
            write_count,
            encodings_bitmap
        ) = struct.unpack_from('>HH I I I I I I I I I I I I I I I I I Q', data, offset)
        
        # 解析 Finder Info (7 个值)
        finder_info = FinderInfo.from_bytes(data, offset + 80)
        
        # 转换 last_mounted_version 为字符串
        last_mounted_version = last_mounted_version_raw.to_bytes(4, 'big').decode('ascii', errors='replace').rstrip('\x00')
        
        # 解析 5 个 fork 数据
        allocation_file = ForkData.from_bytes(data, offset + 112)
        extents_file = ForkData.from_bytes(data, offset + 192)
        catalog_file = ForkData.from_bytes(data, offset + 272)
        attributes_file = ForkData.from_bytes(data, offset + 352)
        startup_file = ForkData.from_bytes(data, offset + 432)
        
        return cls(
            signature=signature,
            version=version,
            attributes=attributes,
            last_mounted_version=last_mounted_version,
            journal_info_block=journal_info_block,
            create_date=create_date,
            modify_date=modify_date,
            backup_date=backup_date,
            checked_date=checked_date,
            file_count=file_count,
            folder_count=folder_count,
            block_size=block_size,
            total_blocks=total_blocks,
            free_blocks=free_blocks,
            next_allocation=next_allocation,
            rsrc_clump_size=rsrc_clump_size,
            data_clump_size=data_clump_size,
            next_catalog_id=next_catalog_id,
            write_count=write_count,
            encodings_bitmap=encodings_bitmap,
            finder_info=finder_info,
            allocation_file=allocation_file,
            extents_file=extents_file,
            catalog_file=catalog_file,
            attributes_file=attributes_file,
            startup_file=startup_file
        )
    
    def __str__(self) -> str:
        """格式化输出"""
        lines = [
            f"HFS+ Volume Header:",
            f"  Signature: {signature_to_string(self.signature)} (0x{self.signature:04X})",
            f"  Version: {self.version}",
            f"  Attributes: 0x{self.attributes:08X} ({attributes_to_string(self.attributes)})",
            f"  Last Mounted Version: {self.last_mounted_version}",
            f"  Journal Info Block: {self.journal_info_block}",
            f"  Create Date: {self.create_datetime}",
            f"  Modify Date: {self.modify_datetime}",
            f"  Backup Date: {self.backup_datetime}",
            f"  Checked Date: {self.checked_datetime}",
            f"  File Count: {self.file_count:,}",
            f"  Folder Count: {self.folder_count:,}",
            f"  Block Size: {self.block_size:,} bytes",
            f"  Total Blocks: {self.total_blocks:,}",
            f"  Free Blocks: {self.free_blocks:,}",
            f"  Volume Size: {self.volume_size:,} bytes ({self.volume_size / (1024**3):.2f} GB)",
            f"  Free Space: {self.free_space:,} bytes ({self.free_space / (1024**3):.2f} GB)",
            f"  Used Space: {self.used_space:,} bytes ({self.used_space / (1024**3):.2f} GB)",
            f"  Next Allocation: {self.next_allocation}",
            f"  Resource Clump Size: {self.rsrc_clump_size}",
            f"  Data Clump Size: {self.data_clump_size}",
            f"  Next Catalog ID: {self.next_catalog_id}",
            f"  Write Count: {self.write_count}",
            f"  Encodings Bitmap: 0x{self.encodings_bitmap:016X}",
            f"  Finder Info: {self.finder_info}",
            f"  Allocation File: {self.allocation_file}",
            f"  Extents File: {self.extents_file}",
            f"  Catalog File: {self.catalog_file}",
            f"  Attributes File: {self.attributes_file}",
            f"  Startup File: {self.startup_file}",
        ]
        return "\n".join(lines)