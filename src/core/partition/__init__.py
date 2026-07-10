"""
分区表解析模块

支持 Apple Partition Map (APM)、GPT 和 MBR 分区表。
"""

import struct
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum


class PartitionType(IntEnum):
    """分区表类型"""
    APM = 0     # Apple Partition Map
    GPT = 1     # GUID Partition Table
    MBR = 2     # Master Boot Record
    UNKNOWN = 3


class PartitionError(Exception):
    """分区表错误"""
    pass


@dataclass
class PartitionEntry:
    """
    分区条目
    
    Attributes:
        name: 分区名称
        type_name: 分区类型名称
        start_lba: 起始 LBA 扇区号
        size_sectors: 分区大小（扇区数）
        partition_type: 分区类型标识
        is_hfs: 是否为 HFS+ 分区
        guid: 分区 GUID (GPT)
    """
    name: str
    type_name: str
    start_lba: int
    size_sectors: int
    partition_type: str = ""
    is_hfs: bool = False
    guid: str = ""
    
    @property
    def start_offset(self) -> int:
        """起始偏移量（字节）"""
        return self.start_lba * 512
    
    @property
    def size_bytes(self) -> int:
        """分区大小（字节）"""
        return self.size_sectors * 512


# =============================================================================
# APM 分区表解析
# =============================================================================

# APM 分区类型常量
APM_TYPE_HFS_PLUS = "Apple_HFS"
APM_TYPE_HFSX = "Apple_HFSX"
APM_TYPE_FREE = "Apple_Free"
APM_TYPE_DRIVER = "Apple_Driver"
APM_TYPE_PATCHES = "Apple_Patches"
APM_TYPE_UNIX = "Apple_UNIX_SVR2"


def parse_apm(stream, sector_size: int = 512) -> List[PartitionEntry]:
    """
    解析 Apple Partition Map (APM)
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        分区条目列表
    
    Raises:
        PartitionError: 解析失败
    """
    partitions = []
    
    # APM 驱动器描述符在 LBA 0
    stream.seek(0)
    
    # 读取驱动器描述符
    dd_data = stream.read(sector_size)
    if len(dd_data) < sector_size:
        raise PartitionError("无法读取驱动器描述符")
    
    # 检查签名 (0x4552 = "ER")
    sig = struct.unpack_from('>H', dd_data, 0)[0]
    if sig != 0x4552:
        raise PartitionError(f"无效的 APM 驱动器描述符签名: 0x{sig:04X}")
    
    # 获取分区表大小
    block_size = struct.unpack_from('>I', dd_data, 8)[0]
    if block_size == 0:
        block_size = sector_size
    
    # 遍历分区映射
    map_entries = struct.unpack_from('>I', dd_data, 4)[0]
    
    for i in range(1, min(map_entries + 1, 63)):  # 最多 63 个分区
        # 读取分区条目
        stream.seek(i * sector_size)
        entry_data = stream.read(sector_size)
        
        if len(entry_data) < sector_size:
            break
        
        # 检查签名 (0x504D = "PM")
        sig = struct.unpack_from('>H', entry_data, 0)[0]
        if sig != 0x504D:
            break
        
        # 解析分区条目
        # 分区名称 (32 字节, 填充到 0)
        name_bytes = entry_data[16:48]
        name = name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')
        
        # 分区类型 (32 字节)
        type_bytes = entry_data[48:80]
        type_name = type_bytes.split(b'\x00')[0].decode('ascii', errors='replace')
        
        # 起始块和大小
        start_block = struct.unpack_from('>I', entry_data, 8)[0]
        block_count = struct.unpack_from('>I', entry_data, 12)[0]
        
        # 判断是否为 HFS+ 分区
        is_hfs = type_name in (APM_TYPE_HFS_PLUS, APM_TYPE_HFSX)
        
        partitions.append(PartitionEntry(
            name=name,
            type_name=type_name,
            start_lba=start_block,
            size_sectors=block_count,
            is_hfs=is_hfs
        ))
    
    return partitions


# =============================================================================
# GPT 分区表解析
# =============================================================================

# GPT 分区类型 GUID
GPT_GUID_EFI = "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"
GPT_GUID_HFS = "48465300-0000-11AA-AA11-00306543ECAC"
GPT_GUID_APFS = "7C3457EF-0000-11AA-AA11-00306543ECAC"
GPT_GUID_LINUX = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"
GPT_GUID_MS_BASIC = "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7"


def _guid_to_string(guid_bytes: bytes) -> str:
    """将 GUID 字节转换为字符串"""
    # GUID 格式: {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
    # 字节顺序: little-endian 前 3 段, big-endian 后 2 段
    d1 = struct.unpack_from('<I', guid_bytes, 0)[0]
    d2 = struct.unpack_from('<H', guid_bytes, 4)[0]
    d3 = struct.unpack_from('<H', guid_bytes, 6)[0]
    d4 = guid_bytes[8:10].hex().upper()
    d5 = guid_bytes[10:16].hex().upper()
    
    return f"{d1:08X}-{d2:04X}-{d3:04X}-{d4}-{d5}"


def parse_gpt(stream, sector_size: int = 512) -> List[PartitionEntry]:
    """
    解析 GUID Partition Table (GPT)
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        分区条目列表
    
    Raises:
        PartitionError: 解析失败
    """
    partitions = []
    
    # GPT 头在 LBA 1
    stream.seek(sector_size)
    header_data = stream.read(sector_size)
    
    if len(header_data) < sector_size:
        raise PartitionError("无法读取 GPT 头")
    
    # 检查签名 "EFI PART"
    if header_data[0:8] != b'EFI PART':
        raise PartitionError("无效的 GPT 签名")
    
    # 解析 GPT 头
    revision = struct.unpack_from('<I', header_data, 8)[0]
    header_size = struct.unpack_from('<I', header_data, 12)[0]
    partition_entry_lba = struct.unpack_from('<Q', header_data, 72)[0]
    num_partitions = struct.unpack_from('<I', header_data, 80)[0]
    partition_entry_size = struct.unpack_from('<I', header_data, 84)[0]
    
    # 读取分区条目
    stream.seek(partition_entry_lba * sector_size)
    
    for i in range(num_partitions):
        entry_offset = i * partition_entry_size
        stream.seek(partition_entry_lba * sector_size + entry_offset)
        entry_data = stream.read(partition_entry_size)
        
        if len(entry_data) < partition_entry_size:
            break
        
        # 检查分区类型 GUID（全零表示未使用）
        type_guid = _guid_to_string(entry_data[0:16])
        if type_guid == "00000000-0000-0000-0000-000000000000":
            continue
        
        # 获取分区 GUID
        partition_guid = _guid_to_string(entry_data[16:32])
        
        # 起始和结束 LBA
        start_lba = struct.unpack_from('<Q', entry_data, 32)[0]
        end_lba = struct.unpack_from('<Q', entry_data, 40)[0]
        
        # 分区属性
        attributes = struct.unpack_from('<Q', entry_data, 48)[0]
        
        # 分区名称 (UTF-16LE, 最多 72 字节)
        name_bytes = entry_data[56:128]
        try:
            name = name_bytes.decode('utf-16-le').rstrip('\x00')
        except:
            name = ""
        
        # 判断是否为 HFS+ 分区
        is_hfs = type_guid.upper() == GPT_GUID_HFS
        
        # 分区类型名称
        type_name = ""
        if type_guid.upper() == GPT_GUID_EFI:
            type_name = "EFI System"
        elif type_guid.upper() == GPT_GUID_HFS:
            type_name = "Apple HFS+"
        elif type_guid.upper() == GPT_GUID_APFS:
            type_name = "Apple APFS"
        elif type_guid.upper() == GPT_GUID_LINUX:
            type_name = "Linux Filesystem"
        elif type_guid.upper() == GPT_GUID_MS_BASIC:
            type_name = "Microsoft Basic Data"
        
        partitions.append(PartitionEntry(
            name=name,
            type_name=type_name,
            start_lba=start_lba,
            size_sectors=end_lba - start_lba + 1,
            partition_type=type_guid,
            is_hfs=is_hfs,
            guid=partition_guid
        ))
    
    return partitions


# =============================================================================
# MBR 分区表解析
# =============================================================================

# MBR 分区类型
MBR_TYPE_FAT16 = 0x04
MBR_TYPE_FAT16_LBA = 0x0E
MBR_TYPE_NTFS = 0x07
MBR_TYPE_LINUX = 0x83
MBR_TYPE_HFS = 0xAF
MBR_TYPE_EXTENDED = 0x05
MBR_TYPE_EXTENDED_LBA = 0x0F
MBR_TYPE_GPT = 0xEE


def parse_mbr(stream, sector_size: int = 512) -> List[PartitionEntry]:
    """
    解析 Master Boot Record (MBR)
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        分区条目列表
    
    Raises:
        PartitionError: 解析失败
    """
    partitions = []
    
    # MBR 在 LBA 0
    stream.seek(0)
    mbr_data = stream.read(sector_size)
    
    if len(mbr_data) < sector_size:
        raise PartitionError("无法读取 MBR")
    
    # 检查签名 (0x55AA)
    if mbr_data[510:512] != b'\x55\xAA':
        raise PartitionError("无效的 MBR 签名")
    
    # 解析 4 个主分区条目
    for i in range(4):
        entry_offset = 446 + i * 16
        entry_data = mbr_data[entry_offset:entry_offset + 16]
        
        # 状态/标志 (0x80 = 活动)
        status = entry_data[0]
        
        # 分区类型
        partition_type = entry_data[4]
        
        # 如果类型为 0，表示未使用
        if partition_type == 0:
            continue
        
        # CHS 起始地址 (不常用，但需要解析)
        start_chs = entry_data[1:4]
        
        # CHS 结束地址
        end_chs = entry_data[5:8]
        
        # LBA 起始扇区
        start_lba = struct.unpack_from('<I', entry_data, 8)[0]
        
        # 分区大小（扇区数）
        size_sectors = struct.unpack_from('<I', entry_data, 12)[0]
        
        # 分区类型名称
        type_name = _get_mbr_type_name(partition_type)
        
        # 判断是否为 HFS+ 分区
        is_hfs = partition_type == MBR_TYPE_HFS
        
        partitions.append(PartitionEntry(
            name=f"Partition {i+1}",
            type_name=type_name,
            start_lba=start_lba,
            size_sectors=size_sectors,
            partition_type=f"0x{partition_type:02X}",
            is_hfs=is_hfs
        ))
    
    # 检查是否有扩展分区，解析 EBR
    extended_partitions = _parse_ebr(mbr_data, stream, sector_size)
    partitions.extend(extended_partitions)
    
    return partitions


def _parse_ebr(mbr_data: bytes, stream, sector_size: int = 512) -> List[PartitionEntry]:
    """
    解析 Extended Boot Record (EBR)
    
    EBR 链式结构用于支持超过 4 个主分区。
    
    Args:
        mbr_data: MBR 数据
        stream: 二进制流
        sector_size: 扇区大小
    
    Returns:
        扩展分区内的逻辑分区列表
    """
    partitions = []
    
    # 查找扩展分区
    extended_lba = 0
    for i in range(4):
        entry_offset = 446 + i * 16
        partition_type = mbr_data[entry_offset + 4]
        
        if partition_type in (MBR_TYPE_EXTENDED, MBR_TYPE_EXTENDED_LBA):
            extended_lba = struct.unpack_from('<I', mbr_data, entry_offset + 8)[0]
            break
    
    if extended_lba == 0:
        return partitions
    
    # 遍历 EBR 链
    current_ebr_lba = extended_lba
    logical_index = 1
    
    while current_ebr_lba != 0:
        # 读取 EBR
        stream.seek(current_ebr_lba * sector_size)
        ebr_data = stream.read(sector_size)
        
        if len(ebr_data) < sector_size:
            break
        
        # 检查签名
        if ebr_data[510:512] != b'\x55\xAA':
            break
        
        # 解析第一个条目（逻辑分区）
        entry_data = ebr_data[446:462]
        partition_type = entry_data[4]
        
        if partition_type != 0:
            start_lba = struct.unpack_from('<I', entry_data, 8)[0]
            size_sectors = struct.unpack_from('<I', entry_data, 12)[0]
            type_name = _get_mbr_type_name(partition_type)
            is_hfs = partition_type == MBR_TYPE_HFS
            
            partitions.append(PartitionEntry(
                name=f"Logical {logical_index}",
                type_name=type_name,
                start_lba=current_ebr_lba + start_lba,
                size_sectors=size_sectors,
                partition_type=f"0x{partition_type:02X}",
                is_hfs=is_hfs
            ))
            
            logical_index += 1
        
        # 解析第二个条目（下一个 EBR）
        next_entry = ebr_data[462:478]
        next_type = next_entry[4]
        
        if next_type in (MBR_TYPE_EXTENDED, MBR_TYPE_EXTENDED_LBA):
            next_lba = struct.unpack_from('<I', next_entry, 8)[0]
            current_ebr_lba = extended_lba + next_lba
        else:
            current_ebr_lba = 0
    
    return partitions


def _get_mbr_type_name(type_code: int) -> str:
    """获取 MBR 分区类型名称"""
    type_names = {
        0x00: "Empty",
        0x01: "FAT12",
        0x04: "FAT16",
        0x05: "Extended",
        0x06: "FAT16B",
        0x07: "NTFS/HPFS",
        0x0B: "FAT32",
        0x0C: "FAT32 LBA",
        0x0E: "FAT16 LBA",
        0x0F: "Extended LBA",
        0x11: "Hidden FAT12",
        0x14: "Hidden FAT16",
        0x16: "Hidden FAT16B",
        0x17: "Hidden NTFS",
        0x1B: "Hidden FAT32",
        0x1C: "Hidden FAT32 LBA",
        0x1E: "Hidden FAT16 LBA",
        0x82: "Linux Swap",
        0x83: "Linux",
        0x84: "Hibernation",
        0x85: "Linux Extended",
        0x86: "NTFS Volume Set",
        0x87: "NTFS Volume Set",
        0xAF: "HFS/HFS+",
        0xEE: "GPT Protective",
        0xEF: "EFI System",
    }
    return type_names.get(type_code, f"Unknown (0x{type_code:02X})")


# =============================================================================
# 自动检测分区表类型
# =============================================================================

def detect_partition_type(stream, sector_size: int = 512) -> PartitionType:
    """
    自动检测分区表类型
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        分区表类型
    """
    # 保存当前位置
    original_pos = stream.tell()
    
    try:
        # 检查 MBR (LBA 0 签名 0x55AA)
        stream.seek(0)
        mbr_data = stream.read(sector_size)
        if len(mbr_data) >= 512 and mbr_data[510:512] == b'\x55\xAA':
            return PartitionType.MBR
        
        # 检查 GPT (LBA 1 签名 "EFI PART")
        stream.seek(sector_size)
        gpt_sig = stream.read(8)
        if len(gpt_sig) >= 8 and gpt_sig == b'EFI PART':
            return PartitionType.GPT
        
        # 检查 APM (LBA 0 签名 0x4552 "ER")
        stream.seek(0)
        apm_sig = stream.read(2)
        if len(apm_sig) >= 2 and struct.unpack_from('>H', apm_sig, 0)[0] == 0x4552:
            return PartitionType.APM
        
        return PartitionType.UNKNOWN
    finally:
        # 恢复位置
        stream.seek(original_pos)


# =============================================================================
# 统一接口
# =============================================================================

def parse_partitions(stream, sector_size: int = 512) -> Tuple[PartitionType, List[PartitionEntry]]:
    """
    自动检测并解析分区表
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        (分区表类型, 分区条目列表)
    """
    partition_type = detect_partition_type(stream, sector_size)
    
    if partition_type == PartitionType.GPT:
        partitions = parse_gpt(stream, sector_size)
    elif partition_type == PartitionType.APM:
        partitions = parse_apm(stream, sector_size)
    elif partition_type == PartitionType.MBR:
        partitions = parse_mbr(stream, sector_size)
    else:
        partitions = []
    
    return partition_type, partitions


def find_hfs_partitions(stream, sector_size: int = 512) -> List[Tuple[PartitionEntry, int]]:
    """
    查找所有 HFS+ 分区
    
    Args:
        stream: 可 seek 的二进制流
        sector_size: 扇区大小
    
    Returns:
        (分区条目, 分区偏移量) 列表
    """
    _, partitions = parse_partitions(stream, sector_size)
    
    hfs_partitions = []
    for entry in partitions:
        if entry.is_hfs:
            hfs_partitions.append((entry, entry.start_offset))
    
    return hfs_partitions


__all__ = [
    'PartitionType',
    'PartitionError',
    'PartitionEntry',
    'parse_apm',
    'parse_gpt',
    'parse_mbr',
    'parse_partitions',
    'detect_partition_type',
    'find_hfs_partitions',
]
