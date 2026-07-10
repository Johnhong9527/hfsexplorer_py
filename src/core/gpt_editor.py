"""
GPT 分区表编辑器

支持读取、修改和写入 GPT (GUID Partition Table) 分区表。
"""

import struct
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import IntEnum


class GPTError(Exception):
    """GPT 相关错误"""
    pass


# GPT 签名
GPT_SIGNATURE = b'EFI PART'

# 分区类型 GUID
class GPTPartitionTypeGUID(IntEnum):
    """GPT 分区类型 GUID"""
    EFI_SYSTEM = 0
    HFS_PLUS = 1
    LINUX_FILESYSTEM = 2
    LINUX_SWAP = 3
    WINDOWS_BASIC_DATA = 4


# 分区类型 GUID 字符串
PARTITION_TYPE_GUIDS = {
    GPTPartitionTypeGUID.EFI_SYSTEM: "C12A7328-F81F-11D2-BA4B-00A0C93EC93B",
    GPTPartitionTypeGUID.HFS_PLUS: "48465300-0000-11AA-AA11-00306543ECAC",
    GPTPartitionTypeGUID.LINUX_FILESYSTEM: "0FC63DAF-8483-4772-8E79-3D69D8477DE4",
    GPTPartitionTypeGUID.LINUX_SWAP: "0657FD6D-A4AB-43C4-88E8-9B2B3D5E4F92",
    GPTPartitionTypeGUID.WINDOWS_BASIC_DATA: "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7",
}


@dataclass
class GPTHeader:
    """
    GPT 头
    
    Attributes:
        signature: 签名 'EFI PART'
        revision: 版本
        header_size: 头大小
        header_crc32: 头 CRC32
        reserved: 保留
        my_lba: 当前 LBA
        alternate_lba: 备份 LBA
        first_usable_lba: 第一个可用 LBA
        last_usable_lba: 最后一个可用 LBA
        disk_guid: 磁盘 GUID
        partition_entry_start_lba: 分区条目起始 LBA
        num_partition_entries: 分区条目数量
        partition_entry_size: 分区条目大小
        partition_entries_crc32: 分区条目 CRC32
    """
    signature: bytes
    revision: int
    header_size: int
    header_crc32: int
    reserved: int
    my_lba: int
    alternate_lba: int
    first_usable_lba: int
    last_usable_lba: int
    disk_guid: str
    partition_entry_start_lba: int
    num_partition_entries: int
    partition_entry_size: int
    partition_entries_crc32: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'GPTHeader':
        """从字节序列解析"""
        if len(data) < 92:
            raise GPTError("数据太短")
        
        signature = data[0:8]
        if signature != GPT_SIGNATURE:
            raise GPTError(f"无效的签名: {signature}")
        
        revision = struct.unpack_from('>I', data, 8)[0]
        header_size = struct.unpack_from('<I', data, 12)[0]
        header_crc32 = struct.unpack_from('<I', data, 16)[0]
        reserved = struct.unpack_from('<I', data, 20)[0]
        my_lba = struct.unpack_from('<Q', data, 24)[0]
        alternate_lba = struct.unpack_from('<Q', data, 32)[0]
        first_usable_lba = struct.unpack_from('<Q', data, 40)[0]
        last_usable_lba = struct.unpack_from('<Q', data, 48)[0]
        
        disk_guid = _format_guid(data[56:72])
        
        partition_entry_start_lba = struct.unpack_from('<Q', data, 72)[0]
        num_partition_entries = struct.unpack_from('<I', data, 80)[0]
        partition_entry_size = struct.unpack_from('<I', data, 84)[0]
        partition_entries_crc32 = struct.unpack_from('<I', data, 88)[0]
        
        return cls(
            signature=signature,
            revision=revision,
            header_size=header_size,
            header_crc32=header_crc32,
            reserved=reserved,
            my_lba=my_lba,
            alternate_lba=alternate_lba,
            first_usable_lba=first_usable_lba,
            last_usable_lba=last_usable_lba,
            disk_guid=disk_guid,
            partition_entry_start_lba=partition_entry_start_lba,
            num_partition_entries=num_partition_entries,
            partition_entry_size=partition_entry_size,
            partition_entries_crc32=partition_entries_crc32
        )
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = bytearray(92)
        
        result[0:8] = self.signature
        struct.pack_into('<I', result, 8, self.revision)
        struct.pack_into('<I', result, 12, self.header_size)
        struct.pack_into('<I', result, 16, self.header_crc32)
        struct.pack_into('<I', result, 20, self.reserved)
        struct.pack_into('<Q', result, 24, self.my_lba)
        struct.pack_into('<Q', result, 32, self.alternate_lba)
        struct.pack_into('<Q', result, 40, self.first_usable_lba)
        struct.pack_into('<Q', result, 48, self.last_usable_lba)
        
        # GUID
        guid_bytes = _parse_guid(self.disk_guid)
        result[56:72] = guid_bytes
        
        struct.pack_into('<Q', result, 72, self.partition_entry_start_lba)
        struct.pack_into('<I', result, 80, self.num_partition_entries)
        struct.pack_into('<I', result, 84, self.partition_entry_size)
        struct.pack_into('<I', result, 88, self.partition_entries_crc32)
        
        return bytes(result)
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == GPT_SIGNATURE
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"GPT Header:\n"
            f"  Signature: {self.signature}\n"
            f"  Revision: 0x{self.revision:08X}\n"
            f"  Header Size: {self.header_size}\n"
            f"  My LBA: {self.my_lba}\n"
            f"  Alternate LBA: {self.alternate_lba}\n"
            f"  First Usable LBA: {self.first_usable_lba}\n"
            f"  Last Usable LBA: {self.last_usable_lba}\n"
            f"  Disk GUID: {self.disk_guid}\n"
            f"  Partition Entries: {self.num_partition_entries}\n"
            f"  Entry Size: {self.partition_entry_size}"
        )


@dataclass
class GPTPartitionEntry:
    """
    GPT 分区条目
    
    Attributes:
        type_guid: 分区类型 GUID
        unique_guid: 唯一 GUID
        first_lba: 起始 LBA
        last_lba: 结束 LBA
        attributes: 属性
        name: 分区名称
    """
    type_guid: str
    unique_guid: str
    first_lba: int
    last_lba: int
    attributes: int
    name: str
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'GPTPartitionEntry':
        """从字节序列解析"""
        if len(data) < 128:
            raise GPTError("数据太短")
        
        type_guid = _format_guid(data[0:16])
        unique_guid = _format_guid(data[16:32])
        
        first_lba = struct.unpack_from('<Q', data, 32)[0]
        last_lba = struct.unpack_from('<Q', data, 40)[0]
        attributes = struct.unpack_from('<Q', data, 48)[0]
        
        # 名称 (UTF-16LE, 最长 72 字节)
        name_bytes = data[56:128]
        try:
            name = name_bytes.decode('utf-16-le').rstrip('\x00')
        except:
            name = ''
        
        return cls(
            type_guid=type_guid,
            unique_guid=unique_guid,
            first_lba=first_lba,
            last_lba=last_lba,
            attributes=attributes,
            name=name
        )
    
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        result = bytearray(128)
        
        # GUID
        result[0:16] = _parse_guid(self.type_guid)
        result[16:32] = _parse_guid(self.unique_guid)
        
        struct.pack_into('<Q', result, 32, self.first_lba)
        struct.pack_into('<Q', result, 40, self.last_lba)
        struct.pack_into('<Q', result, 48, self.attributes)
        
        # 名称
        name_bytes = self.name.encode('utf-16-le')[:72]
        result[56:56 + len(name_bytes)] = name_bytes
        
        return bytes(result)
    
    @property
    def size_sectors(self) -> int:
        """大小（扇区数）"""
        return self.last_lba - self.first_lba + 1
    
    @property
    def is_empty(self) -> bool:
        """是否为空"""
        return self.first_lba == 0 and self.last_lba == 0
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"GPT Partition Entry:\n"
            f"  Type GUID: {self.type_guid}\n"
            f"  Unique GUID: {self.unique_guid}\n"
            f"  First LBA: {self.first_lba}\n"
            f"  Last LBA: {self.last_lba}\n"
            f"  Size: {self.size_sectors} sectors\n"
            f"  Attributes: 0x{self.attributes:016X}\n"
            f"  Name: {self.name}"
        )


def _format_guid(data: bytes) -> str:
    """格式化 GUID"""
    if len(data) < 16:
        return "00000000-0000-0000-0000-000000000000"
    
    # 注意：GPT 使用混合端序
    return (
        f"{struct.unpack('<I', data[0:4])[0]:08X}-"
        f"{struct.unpack('<H', data[4:6])[0]:04X}-"
        f"{struct.unpack('<H', data[6:8])[0]:04X}-"
        f"{data[8:10].hex().upper()}-"
        f"{data[10:16].hex().upper()}"
    )


def _parse_guid(guid_str: str) -> bytes:
    """解析 GUID 字符串"""
    # 移除连字符
    guid_str = guid_str.replace('-', '')
    
    # 转换为字节
    guid_bytes = bytes.fromhex(guid_str)
    
    # 转换为混合端序
    result = bytearray(16)
    result[0:4] = struct.pack('<I', int.from_bytes(guid_bytes[0:4], 'big'))
    result[4:6] = struct.pack('<H', int.from_bytes(guid_bytes[4:6], 'big'))
    result[6:8] = struct.pack('<H', int.from_bytes(guid_bytes[6:8], 'big'))
    result[8:16] = guid_bytes[8:16]
    
    return bytes(result)


class GPTEditor:
    """
    GPT 编辑器
    
    用于读取、修改和写入 GPT 分区表。
    
    Usage:
        editor = GPTEditor("disk.img")
        editor.read()
        editor.add_partition("HFS+", 1024*1024*100)
        editor.write()
    """
    
    def __init__(self, path: str):
        """
        初始化 GPT 编辑器
        
        Args:
            path: 文件路径
        """
        self.path = path
        self.header: Optional[GPTHeader] = None
        self.partitions: List[GPTPartitionEntry] = []
        self._sector_size = 512
    
    def read(self):
        """读取 GPT 分区表"""
        with open(self.path, 'rb') as f:
            # 读取 GPT 头 (LBA 1)
            f.seek(self._sector_size)
            header_data = f.read(self._sector_size)
            self.header = GPTHeader.from_bytes(header_data)
            
            if not self.header.is_valid:
                raise GPTError("无效的 GPT 头")
            
            # 读取分区条目
            f.seek(self.header.partition_entry_start_lba * self._sector_size)
            
            for i in range(self.header.num_partition_entries):
                entry_data = f.read(self.header.partition_entry_size)
                entry = GPTPartitionEntry.from_bytes(entry_data)
                
                if not entry.is_empty:
                    self.partitions.append(entry)
    
    def write(self):
        """写入 GPT 分区表"""
        if self.header is None:
            raise GPTError("未读取 GPT 头")
        
        with open(self.path, 'r+b') as f:
            # 写入分区条目
            f.seek(self.header.partition_entry_start_lba * self._sector_size)
            
            for entry in self.partitions:
                f.write(entry.to_bytes())
            
            # 填充空条目
            empty_entry = GPTPartitionEntry(
                type_guid="00000000-0000-0000-0000-000000000000",
                unique_guid="00000000-0000-0000-0000-000000000000",
                first_lba=0,
                last_lba=0,
                attributes=0,
                name=""
            )
            
            for i in range(len(self.partitions), self.header.num_partition_entries):
                f.write(empty_entry.to_bytes())
    
    def add_partition(self, name: str, size_lba: int, 
                     type_guid: str = None) -> GPTPartitionEntry:
        """
        添加分区
        
        Args:
            name: 分区名称
            size_lba: 大小（LBA 数量）
            type_guid: 类型 GUID
        
        Returns:
            新分区条目
        """
        if self.header is None:
            raise GPTError("未读取 GPT 头")
        
        # 计算起始 LBA
        if self.partitions:
            last_lba = max(p.last_lba for p in self.partitions)
        else:
            last_lba = self.header.first_usable_lba - 1
        
        first_lba = last_lba + 1
        last_lba = first_lba + size_lba - 1
        
        # 检查是否超出范围
        if last_lba > self.header.last_usable_lba:
            raise GPTError("分区超出可用范围")
        
        # 生成 GUID
        if type_guid is None:
            type_guid = PARTITION_TYPE_GUIDS.get(
                GPTPartitionTypeGUID.HFS_PLUS,
                "48465300-0000-11AA-AA11-00306543ECAC"
            )
        
        unique_guid = str(uuid.uuid4()).upper()
        
        # 创建分区条目
        entry = GPTPartitionEntry(
            type_guid=type_guid,
            unique_guid=unique_guid,
            first_lba=first_lba,
            last_lba=last_lba,
            attributes=0,
            name=name
        )
        
        self.partitions.append(entry)
        
        return entry
    
    def remove_partition(self, index: int):
        """
        删除分区
        
        Args:
            index: 分区索引
        """
        if 0 <= index < len(self.partitions):
            self.partitions.pop(index)
    
    def get_partition(self, index: int) -> GPTPartitionEntry:
        """
        获取分区
        
        Args:
            index: 分区索引
        
        Returns:
            分区条目
        """
        if 0 <= index < len(self.partitions):
            return self.partitions[index]
        raise GPTError(f"分区索引超出范围: {index}")
    
    def get_info(self) -> Dict[str, Any]:
        """获取 GPT 信息"""
        if self.header is None:
            return {}
        
        return {
            'disk_guid': self.header.disk_guid,
            'num_partitions': len(self.partitions),
            'first_usable_lba': self.header.first_usable_lba,
            'last_usable_lba': self.header.last_usable_lba,
            'partitions': [
                {
                    'name': p.name,
                    'type_guid': p.type_guid,
                    'size': p.size_sectors * self._sector_size,
                }
                for p in self.partitions
            ]
        }
