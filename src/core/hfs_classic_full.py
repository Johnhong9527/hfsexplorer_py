"""
HFS Classic 完整支持模块

提供 HFS (Hierarchical File System) 的完整读取功能。
HFS 是 Apple 在 1985 年推出的文件系统，是 HFS+ 的前身。
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, BinaryIO
from datetime import datetime, timezone
from enum import IntEnum, IntFlag


# =============================================================================
# HFS 常量
# =============================================================================

# 签名
HFS_SIGNATURE = 0x4244  # 'BD'
HFS_PLUS_SIGNATURE = 0x482B  # 'H+'
HFSX_SIGNATURE = 0x4858  # 'HX'

# 日期偏移 (1904-01-01 到 1970-01-01)
HFS_EPOCH_OFFSET = 2082844800

# Catalog 记录类型
class CatalogRecordType(IntEnum):
    """Catalog 记录类型"""
    FOLDER = 0x0100
    FILE = 0x0200
    FOLDER_THREAD = 0x0300
    FILE_THREAD = 0x0400


# Fork 类型
FORK_DATA = 0
FORK_RESOURCE = 1


# =============================================================================
# HFS 数据结构
# =============================================================================

@dataclass
class ExtentDescriptor:
    """Extent 描述符"""
    start_block: int  # 起始块号
    block_count: int  # 块数量
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ExtentDescriptor':
        """从字节序列解析"""
        start_block = struct.unpack_from('>H', data, offset)[0]
        block_count = struct.unpack_from('>H', data, offset + 2)[0]
        return cls(start_block=start_block, block_count=block_count)
        
    def to_bytes(self) -> bytes:
        """转换为字节序列"""
        return struct.pack('>HH', self.start_block, self.block_count)


@dataclass
class ForkData:
    """Fork 数据"""
    logical_size: int  # 逻辑大小
    clump_size: int  # Clump 大小
    total_blocks: int  # 总块数
    extents: List[ExtentDescriptor]  # Extent 列表
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'ForkData':
        """从字节序列解析"""
        logical_size = struct.unpack_from('>Q', data, offset)[0]
        clump_size = struct.unpack_from('>I', data, offset + 8)[0]
        total_blocks = struct.unpack_from('>I', data, offset + 12)[0]
        
        extents = []
        for i in range(3):  # HFS 只有 3 个内联 extent
            ext = ExtentDescriptor.from_bytes(data, offset + 16 + i * 4)
            if ext.block_count > 0:
                extents.append(ext)
                
        return cls(
            logical_size=logical_size,
            clump_size=clump_size,
            total_blocks=total_blocks,
            extents=extents
        )


@dataclass
class HFSVolumeHeader:
    """
    HFS 卷头
    
    位于第 2 扇区（偏移 1024 字节）。
    """
    signature: int
    create_date: int
    modify_date: int
    backup_date: int
    file_count: int
    folder_count: int
    block_size: int
    total_blocks: int
    free_blocks: int
    next_allocation: int
    catalog_clump_size: int
    extents_clump_size: int
    next_catalog_id: int
    write_count: int
    bitmap_start: int
    catalog_start: int
    extents_start: int
    data_fork: ForkData
    resource_fork: ForkData
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'HFSVolumeHeader':
        """从字节序列解析"""
        if len(data) < offset + 512:
            raise ValueError("数据太短")
        
        signature = struct.unpack_from('>H', data, offset)[0]
        if signature != HFS_SIGNATURE:
            raise ValueError(f"无效的签名: 0x{signature:04X}")
        
        # 基本字段
        create_date = struct.unpack_from('>I', data, offset + 4)[0]
        modify_date = struct.unpack_from('>I', data, offset + 8)[0]
        backup_date = struct.unpack_from('>I', data, offset + 12)[0]
        
        file_count = struct.unpack_from('>H', data, offset + 22)[0]
        folder_count = struct.unpack_from('>H', data, offset + 24)[0]
        
        block_size = struct.unpack_from('>I', data, offset + 28)[0]
        total_blocks = struct.unpack_from('>I', data, offset + 32)[0]
        
        free_blocks = struct.unpack_from('>I', data, offset + 36)[0]
        next_allocation = struct.unpack_from('>I', data, offset + 40)[0]
        
        catalog_clump_size = struct.unpack_from('>I', data, offset + 44)[0]
        extents_clump_size = struct.unpack_from('>I', data, offset + 48)[0]
        
        next_catalog_id = struct.unpack_from('>I', data, offset + 56)[0]
        write_count = struct.unpack_from('>I', data, offset + 60)[0]
        
        bitmap_start = struct.unpack_from('>H', data, offset + 64)[0]
        catalog_start = struct.unpack_from('>H', data, offset + 66)[0]
        extents_start = struct.unpack_from('>H', data, offset + 68)[0]
        
        # Fork 数据
        data_fork = ForkData.from_bytes(data, offset + 80)
        resource_fork = ForkData.from_bytes(data, offset + 112)
        
        return cls(
            signature=signature,
            create_date=create_date,
            modify_date=modify_date,
            backup_date=backup_date,
            file_count=file_count,
            folder_count=folder_count,
            block_size=block_size,
            total_blocks=total_blocks,
            free_blocks=free_blocks,
            next_allocation=next_allocation,
            catalog_clump_size=catalog_clump_size,
            extents_clump_size=extents_clump_size,
            next_catalog_id=next_catalog_id,
            write_count=write_count,
            bitmap_start=bitmap_start,
            catalog_start=catalog_start,
            extents_start=extents_start,
            data_fork=data_fork,
            resource_fork=resource_fork
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == HFS_SIGNATURE
    
    @property
    def volume_size(self) -> int:
        """卷大小（字节）"""
        return self.block_size * self.total_blocks
    
    @property
    def free_space(self) -> int:
        """空闲空间（字节）"""
        return self.block_size * self.free_blocks


@dataclass
class CatalogKey:
    """Catalog 键"""
    key_length: int
    parent_id: int
    name: str
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'CatalogKey':
        """从字节序列解析"""
        key_length = data[offset]
        parent_id = struct.unpack_from('>I', data, offset + 2)[0]
        name_length = data[offset + 6]
        name_bytes = data[offset + 7:offset + 7 + name_length]
        name = name_bytes.decode('mac-roman', errors='replace')
        
        return cls(
            key_length=key_length,
            parent_id=parent_id,
            name=name
        )


@dataclass
class CatalogFolder:
    """Catalog 文件夹记录"""
    record_type: int
    flags: int
    valence: int
    folder_id: int
    create_date: int
    modify_date: int
    backup_date: int
    folder_info: bytes
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'CatalogFolder':
        """从字节序列解析"""
        record_type = struct.unpack_from('>H', data, offset)[0]
        flags = struct.unpack_from('>H', data, offset + 2)[0]
        valence = struct.unpack_from('>H', data, offset + 4)[0]
        folder_id = struct.unpack_from('>I', data, offset + 6)[0]
        
        create_date = struct.unpack_from('>I', data, offset + 10)[0]
        modify_date = struct.unpack_from('>I', data, offset + 14)[0]
        backup_date = struct.unpack_from('>I', data, offset + 18)[0]
        
        folder_info = data[offset + 22:offset + 22 + 16]
        
        return cls(
            record_type=record_type,
            flags=flags,
            valence=valence,
            folder_id=folder_id,
            create_date=create_date,
            modify_date=modify_date,
            backup_date=backup_date,
            folder_info=folder_info
        )


@dataclass
class CatalogFile:
    """Catalog 文件记录"""
    record_type: int
    flags: int
    file_type: int
    file_id: int
    data_fork: ForkData
    resource_fork: ForkData
    create_date: int
    modify_date: int
    backup_date: int
    file_info: bytes
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'CatalogFile':
        """从字节序列解析"""
        record_type = struct.unpack_from('>H', data, offset)[0]
        flags = data[offset + 2]
        file_type = data[offset + 3]
        
        file_info = data[offset + 4:offset + 4 + 16]
        
        file_id = struct.unpack_from('>I', data, offset + 20)[0]
        
        data_fork = ForkData.from_bytes(data, offset + 24)
        resource_fork = ForkData.from_bytes(data, offset + 56)
        
        create_date = struct.unpack_from('>I', data, offset + 88)[0]
        modify_date = struct.unpack_from('>I', data, offset + 92)[0]
        backup_date = struct.unpack_from('>I', data, offset + 96)[0]
        
        return cls(
            record_type=record_type,
            flags=flags,
            file_type=file_type,
            file_id=file_id,
            data_fork=data_fork,
            resource_fork=resource_fork,
            create_date=create_date,
            modify_date=modify_date,
            backup_date=backup_date,
            file_info=file_info
        )


# =============================================================================
# HFS B-tree 支持
# =============================================================================

@dataclass
class BTreeHeader:
    """B-tree 头部"""
    depth: int
    root_node: int
    leaf_records: int
    first_leaf: int
    last_leaf: int
    node_size: int
    max_key_length: int
    total_nodes: int
    free_nodes: int
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTreeHeader':
        """从字节序列解析"""
        depth = struct.unpack_from('>H', data, offset)[0]
        root_node = struct.unpack_from('>I', data, offset + 2)[0]
        leaf_records = struct.unpack_from('>I', data, offset + 6)[0]
        first_leaf = struct.unpack_from('>I', data, offset + 10)[0]
        last_leaf = struct.unpack_from('>I', data, offset + 14)[0]
        node_size = struct.unpack_from('>H', data, offset + 18)[0]
        max_key_length = struct.unpack_from('>H', data, offset + 20)[0]
        total_nodes = struct.unpack_from('>I', data, offset + 22)[0]
        free_nodes = struct.unpack_from('>I', data, offset + 26)[0]
        
        return cls(
            depth=depth,
            root_node=root_node,
            leaf_records=leaf_records,
            first_leaf=first_leaf,
            last_leaf=last_leaf,
            node_size=node_size,
            max_key_length=max_key_length,
            total_nodes=total_nodes,
            free_nodes=free_nodes
        )


@dataclass
class BTNodeDescriptor:
    """B-tree 节点描述符"""
    forward: int  # 前向链接
    backward: int  # 后向链接
    type: int  # 节点类型
    height: int  # 高度
    num_records: int  # 记录数量
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'BTNodeDescriptor':
        """从字节序列解析"""
        forward = struct.unpack_from('>I', data, offset)[0]
        backward = struct.unpack_from('>I', data, offset + 4)[0]
        type_val = data[offset + 8]
        height = data[offset + 9]
        num_records = struct.unpack_from('>H', data, offset + 10)[0]
        
        return cls(
            forward=forward,
            backward=backward,
            type=type_val,
            height=height,
            num_records=num_records
        )


# =============================================================================
# HFS 读取器
# =============================================================================

class HFSClassicVolume:
    """
    HFS Classic 卷读取器
    
    负责读取 HFS 卷的内容
    """
    
    def __init__(self, file_path: str):
        """
        初始化 HFS Classic 卷读取器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        self.file: Optional[BinaryIO] = None
        self.header: Optional[HFSVolumeHeader] = None
        self.catalog_header: Optional[BTreeHeader] = None
        self.catalog_offset: int = 0
        self.extents_header: Optional[BTreeHeader] = None
        self.extents_offset: int = 0
        
    def open(self) -> None:
        """打开卷"""
        self.file = open(self.file_path, 'rb')
        self._read_header()
        self._read_catalog()
        self._read_extents()
        
    def close(self) -> None:
        """关闭卷"""
        if self.file:
            self.file.close()
            self.file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _read_header(self) -> None:
        """读取卷头"""
        if not self.file:
            raise RuntimeError("文件未打开")
            
        # HFS 卷头在偏移 1024 处
        self.file.seek(1024)
        data = self.file.read(512)
        self.header = HFSVolumeHeader.from_bytes(data)
        
    def _read_catalog(self) -> None:
        """读取 Catalog B-tree"""
        if not self.file or not self.header:
            return
            
        # Catalog 起始位置
        self.catalog_offset = self.header.catalog_start * self.header.block_size
        
        # 读取 B-tree 头部
        self.file.seek(self.catalog_offset + 14)  # 跳过节点描述符
        data = self.file.read(512)
        self.catalog_header = BTreeHeader.from_bytes(data)
        
    def _read_extents(self) -> None:
        """读取 Extents Overflow B-tree"""
        if not self.file or not self.header:
            return
            
        # Extents 起始位置
        self.extents_offset = self.header.extents_start * self.header.block_size
        
        # 读取 B-tree 头部
        self.file.seek(self.extents_offset + 14)  # 跳过节点描述符
        data = self.file.read(512)
        self.extents_header = BTreeHeader.from_bytes(data)
        
    def get_info(self) -> Dict:
        """获取卷信息"""
        if not self.header:
            return {}
            
        return {
            'signature': 'HFS',
            'block_size': self.header.block_size,
            'total_blocks': self.header.total_blocks,
            'free_blocks': self.header.free_blocks,
            'volume_size': self.header.volume_size,
            'file_count': self.header.file_count,
            'folder_count': self.header.folder_count,
        }
        
    def _read_node(self, node_number: int, header: BTreeHeader, base_offset: int) -> bytes:
        """读取 B-tree 节点"""
        if not self.file:
            raise RuntimeError("文件未打开")
            
        offset = base_offset + node_number * header.node_size
        self.file.seek(offset)
        return self.file.read(header.node_size)
        
    def _get_record_offset(self, node_data: bytes, record_number: int) -> int:
        """获取记录偏移"""
        node_size = len(node_data)
        offset_table_offset = node_size - (record_number + 1) * 2
        return struct.unpack_from('>H', node_data, offset_table_offset)[0]
        
    def list_folder(self, folder_id: int = 2) -> List[Dict]:
        """
        列出文件夹内容
        
        Args:
            folder_id: 文件夹 ID（默认 2，即根目录）
            
        Returns:
            文件/文件夹列表
        """
        if not self.catalog_header:
            return []
            
        result = []
        
        # 从根节点开始遍历
        node_number = self.catalog_header.root_node
        
        while node_number != 0:
            node_data = self._read_node(node_number, self.catalog_header, self.catalog_offset)
            node_desc = BTNodeDescriptor.from_bytes(node_data)
            
            # 遍历记录
            for i in range(node_desc.num_records):
                offset = self._get_record_offset(node_data, i)
                
                # 解析 Catalog 键
                key = CatalogKey.from_bytes(node_data, offset)
                
                # 检查是否是目标文件夹的子项
                if key.parent_id == folder_id:
                    # 记录数据在键之后
                    record_offset = offset + key.key_length + 1
                    
                    # 解析记录类型
                    record_type = struct.unpack_from('>H', node_data, record_offset)[0]
                    
                    if record_type == CatalogRecordType.FOLDER:
                        folder = CatalogFolder.from_bytes(node_data, record_offset)
                        result.append({
                            'name': key.name,
                            'id': folder.folder_id,
                            'type': 'folder',
                            'create_date': folder.create_date,
                            'mod_date': folder.modify_date,
                        })
                    elif record_type == CatalogRecordType.FILE:
                        file = CatalogFile.from_bytes(node_data, record_offset)
                        result.append({
                            'name': key.name,
                            'id': file.file_id,
                            'type': 'file',
                            'size': file.data_fork.logical_size,
                            'create_date': file.create_date,
                            'mod_date': file.modify_date,
                        })
                        
                # 如果键的父 ID 大于目标，已经超过了
                if key.parent_id > folder_id:
                    break
                    
            # 移动到下一个叶节点
            node_number = node_desc.forward
            
        return result
        
    def read_file(self, file_id: int) -> bytes:
        """
        读取文件数据
        
        Args:
            file_id: 文件 ID
            
        Returns:
            文件数据
        """
        if not self.catalog_header:
            return b''
            
        # 查找文件记录
        file_record = self._find_file_record(file_id)
        if not file_record:
            return b''
            
        # 读取数据
        return self._read_fork_data(file_record.data_fork)
        
    def _find_file_record(self, file_id: int) -> Optional[CatalogFile]:
        """查找文件记录"""
        if not self.catalog_header:
            return None
            
        # 遍历所有叶节点
        node_number = self.catalog_header.first_leaf
        
        while node_number != 0:
            node_data = self._read_node(node_number, self.catalog_header, self.catalog_offset)
            node_desc = BTNodeDescriptor.from_bytes(node_data)
            
            for i in range(node_desc.num_records):
                offset = self._get_record_offset(node_data, i)
                key = CatalogKey.from_bytes(node_data, offset)
                
                record_offset = offset + key.key_length + 1
                record_type = struct.unpack_from('>H', node_data, record_offset)[0]
                
                if record_type == CatalogRecordType.FILE:
                    file = CatalogFile.from_bytes(node_data, record_offset)
                    if file.file_id == file_id:
                        return file
                        
            node_number = node_desc.forward
            
        return None
        
    def _read_fork_data(self, fork: ForkData) -> bytes:
        """读取 Fork 数据"""
        if not self.file:
            return b''
            
        result = b''
        block_size = self.header.block_size
        
        for extent in fork.extents:
            offset = extent.start_block * block_size
            size = extent.block_count * block_size
            
            self.file.seek(offset)
            data = self.file.read(size)
            result += data
            
        # 截断到逻辑大小
        if len(result) > fork.logical_size:
            result = result[:fork.logical_size]
            
        return result
        
    def get_file_info(self, file_id: int) -> Optional[Dict]:
        """获取文件信息"""
        file_record = self._find_file_record(file_id)
        if not file_record:
            return None
            
        return {
            'id': file_record.file_id,
            'size': file_record.data_fork.logical_size,
            'create_date': file_record.create_date,
            'mod_date': file_record.modify_date,
        }


# =============================================================================
# 便捷函数
# =============================================================================

def open_hfs(path: str) -> HFSClassicVolume:
    """
    打开 HFS 卷
    
    Args:
        path: 文件路径
        
    Returns:
        HFS 卷读取器
    """
    volume = HFSClassicVolume(path)
    volume.open()
    return volume


def is_hfs_volume(path: str) -> bool:
    """
    检查是否是 HFS 卷
    
    Args:
        path: 文件路径
        
    Returns:
        是否是 HFS 卷
    """
    try:
        with open(path, 'rb') as f:
            f.seek(1024)
            signature = struct.unpack('>H', f.read(2))[0]
            return signature == HFS_SIGNATURE
    except:
        return False


# 需要导入 IntEnum
from enum import IntEnum
