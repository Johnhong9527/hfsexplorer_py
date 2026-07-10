"""
HFS+ 格式化模块

提供创建新的 HFS+ 文件系统（格式化）功能。

Usage:
    from src.core.hfs.formatter import HFSPlusFormatter
    
    # 格式化文件或设备
    formatter = HFSPlusFormatter()
    formatter.format("/path/to/volume.img", volume_name="MyVolume")
    
    # 或者使用流
    with open("/path/to/volume.img", "wb") as f:
        formatter.format_stream(f, volume_size=1024*1024*100, volume_name="MyVolume")
"""

import struct
import os
import time
import uuid
from dataclasses import dataclass
from typing import BinaryIO, Optional, Tuple

from .constants import (
    SIGNATURE_HFS_PLUS,
    HFS_EPOCH_OFFSET,
    DEFAULT_BLOCK_SIZE,
    MIN_BLOCK_SIZE,
    MAX_BLOCK_SIZE,
    CatalogNodeID,
    VolumeAttributes,
    BTreeNodeKind,
    CatalogRecordType,
    VOLUME_HEADER_SIZE,
    VOLUME_HEADER_OFFSET,
    BTREE_NODE_DESCRIPTOR_SIZE,
    BTREE_HEADER_RECORD_SIZE,
    EXTENT_DESCRIPTOR_SIZE,
    EXTENT_RECORD_COUNT,
    FORK_DATA_SIZE,
    FINDER_INFO_SIZE,
)
from .structures import (
    HFSPlusVolumeHeader,
    ForkData,
    ExtentDescriptor,
    FinderInfo,
)
from .btree import (
    BTNodeDescriptor,
    BTHeaderRec,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogThread,
    compare_catalog_keys,
)
from .writer import AllocationBitmap


class FormatError(Exception):
    """格式化错误"""
    pass


@dataclass
class FormatOptions:
    """
    格式化选项
    
    Attributes:
        volume_name: 卷名称
        block_size: 分配块大小（字节），默认 4096
        max_catalog_nodes: Catalog B-tree 最大节点数
        journal_size: 日志大小（字节），0 表示不启用日志
        file_system_type: 文件系统类型 ('HFS+' 或 'HFSX')
        case_sensitive: 是否区分大小写（仅 HFSX）
    """
    volume_name: str = "Untitled"
    block_size: int = DEFAULT_BLOCK_SIZE
    max_catalog_nodes: int = 0  # 0 = 自动计算
    journal_size: int = 0  # 0 = 不启用日志
    file_system_type: str = "HFS+"
    case_sensitive: bool = False


class HFSPlusFormatter:
    """
    HFS+ 格式化器
    
    用于创建新的 HFS+ 文件系统。
    
    Usage:
        formatter = HFSPlusFormatter()
        formatter.format("/path/to/volume.img", volume_name="MyVolume")
    """
    
    # 系统保留区域（卷头、位图等）占用的块数
    SYSTEM_BLOCKS_RESERVED = 16
    
    # 最小卷大小（1 MB）
    MIN_VOLUME_SIZE = 1024 * 1024
    
    # B-tree 默认节点大小
    DEFAULT_NODE_SIZE = 4096
    
    # B-tree 默认 Clump 大小
    DEFAULT_CATALOG_CLUMP_SIZE = 4 * 1024 * 1024  # 4 MB
    DEFAULT_EXTENTS_CLUMP_SIZE = 4 * 1024 * 1024  # 4 MB
    
    def format(self, path: str, volume_name: str = "Untitled",
               block_size: int = DEFAULT_BLOCK_SIZE) -> HFSPlusVolumeHeader:
        """
        格式化文件或设备为 HFS+
        
        Args:
            path: 文件路径或设备路径
            volume_name: 卷名称
            block_size: 分配块大小（字节）
        
        Returns:
            创建的卷头
        
        Raises:
            FormatError: 格式化失败
        """
        options = FormatOptions(
            volume_name=volume_name,
            block_size=block_size
        )
        
        # 获取卷大小
        if os.path.exists(path):
            # 已存在的文件，使用文件大小
            volume_size = os.path.getsize(path)
        else:
            # 新文件，创建默认大小的卷（100 MB）
            volume_size = 100 * 1024 * 1024
        
        # 预分配空间
        with open(path, "w+b") as f:
            f.seek(volume_size - 1)
            f.write(b'\x00')
            f.flush()
            
            # 重新打开文件进行读写
        
        with open(path, "r+b") as f:
            return self.format_stream(f, volume_size, options)
    
    def format_stream(self, stream: BinaryIO, volume_size: int,
                      options: Optional[FormatOptions] = None) -> HFSPlusVolumeHeader:
        """
        格式化流为 HFS+
        
        Args:
            stream: 可写的二进制流
            volume_size: 卷大小（字节）
            options: 格式化选项
        
        Returns:
            创建的卷头
        
        Raises:
            FormatError: 格式化失败
        """
        if options is None:
            options = FormatOptions()
        
        # 验证参数
        self._validate_parameters(volume_size, options)
        
        # 计算卷布局
        layout = self._calculate_layout(volume_size, options)
        
        # 创建卷头
        header = self._create_volume_header(volume_size, options, layout)
        
        # 写入卷头
        self._write_volume_header(stream, header)
        
        # 初始化分配位图
        self._initialize_allocation_bitmap(stream, header, layout)
        
        # 创建 Catalog B-tree
        self._create_catalog_btree(stream, header, layout)
        
        # 创建 Extents Overflow B-tree
        self._create_extents_btree(stream, header, layout)
        
        # 写入备份卷头
        self._write_backup_volume_header(stream, header)
        
        # 刷新流
        stream.flush()
        
        return header
    
    def _validate_parameters(self, volume_size: int, options: FormatOptions):
        """验证格式化参数"""
        # 检查卷大小
        if volume_size < self.MIN_VOLUME_SIZE:
            raise FormatError(
                f"卷大小太小: {volume_size} 字节，"
                f"最小需要 {self.MIN_VOLUME_SIZE} 字节"
            )
        
        # 检查块大小
        if options.block_size < MIN_BLOCK_SIZE or options.block_size > MAX_BLOCK_SIZE:
            raise FormatError(
                f"块大小无效: {options.block_size}，"
                f"必须在 {MIN_BLOCK_SIZE} 和 {MAX_BLOCK_SIZE} 之间"
            )
        
        # 检查块大小是否为 2 的幂
        if options.block_size & (options.block_size - 1) != 0:
            raise FormatError(f"块大小必须是 2 的幂: {options.block_size}")
        
        # 检查卷大小是否能被块大小整除
        if volume_size % options.block_size != 0:
            raise FormatError(
                f"卷大小 {volume_size} 必须能被块大小 {options.block_size} 整除"
            )
        
        # 检查卷名称长度
        if len(options.volume_name) > 255:
            raise FormatError(
                f"卷名称太长: {len(options.volume_name)} 字符，最大 255"
            )
    
    def _calculate_layout(self, volume_size: int, 
                          options: FormatOptions) -> dict:
        """
        计算卷布局
        
        Returns:
            包含布局信息的字典
        """
        block_size = options.block_size
        total_blocks = volume_size // block_size
        
        # 计算分配位图大小
        # 每个块可以管理 block_size * 8 个块
        blocks_per_bitmap_block = block_size * 8
        bitmap_blocks = (total_blocks + blocks_per_bitmap_block - 1) // blocks_per_bitmap_block
        
        # Catalog B-tree 布局
        node_size = self.DEFAULT_NODE_SIZE
        
        # 计算 Catalog 需要的块数
        # 头节点 + 1 个空叶节点 + 位图节点
        catalog_nodes = 3
        if options.max_catalog_nodes > 0:
            catalog_nodes = max(catalog_nodes, options.max_catalog_nodes)
        
        catalog_blocks = (catalog_nodes * node_size + block_size - 1) // block_size
        
        # Extents B-tree 布局（初始为空，只需要头节点）
        extents_nodes = 3  # 头节点 + 1 个空叶节点 + 位图节点
        extents_blocks = (extents_nodes * node_size + block_size - 1) // block_size
        
        # 系统区域块数
        # 块 0: 保留
        # 块 1-2: 卷头（偏移 1024，在块 0 中，但需要 2 个块的空间）
        # 块 3-3+bitmap_blocks-1: 分配位图
        # 块 X: Catalog B-tree
        # 块 Y: Extents B-tree
        system_start = 3
        bitmap_start = system_start
        catalog_start = bitmap_start + bitmap_blocks
        extents_start = catalog_start + catalog_blocks
        
        # 计算系统区域总块数
        system_blocks = extents_start + extents_blocks
        
        # 确保系统区域不超过总块数的 10%
        if system_blocks > total_blocks * 0.1:
            raise FormatError(
                f"卷太小，无法容纳系统区域: 需要 {system_blocks} 块，"
                f"总共只有 {total_blocks} 块"
            )
        
        return {
            'total_blocks': total_blocks,
            'block_size': block_size,
            'volume_size': volume_size,
            'bitmap_start': bitmap_start,
            'bitmap_blocks': bitmap_blocks,
            'catalog_start': catalog_start,
            'catalog_blocks': catalog_blocks,
            'catalog_node_size': node_size,
            'extents_start': extents_start,
            'extents_blocks': extents_blocks,
            'extents_node_size': node_size,
            'system_blocks': system_blocks,
        }
    
    def _create_volume_header(self, volume_size: int, options: FormatOptions,
                              layout: dict) -> HFSPlusVolumeHeader:
        """创建卷头"""
        # 获取当前 HFS 日期
        current_hfs_date = int(time.time()) + HFS_EPOCH_OFFSET
        
        # 生成卷 UUID
        volume_uuid = uuid.uuid4().int >> 64  # 取前 64 位
        
        # 确定签名
        if options.file_system_type == "HFSX":
            signature = 0x4858  # HFSX
            version = 5
        else:
            signature = SIGNATURE_HFS_PLUS
            version = 4
        
        # 确定属性
        attributes = VolumeAttributes.VOLUME_UNMOUNTED
        if options.journal_size > 0:
            attributes |= VolumeAttributes.VOLUME_JOURNALED
        
        # 创建 Finder Info
        finder_info = FinderInfo(
            volume_uuid=volume_uuid
        )
        
        # 创建 Catalog 文件 fork 数据
        catalog_file = ForkData(
            logical_size=layout['catalog_blocks'] * layout['block_size'],
            clump_size=self.DEFAULT_CATALOG_CLUMP_SIZE,
            total_blocks=layout['catalog_blocks'],
            extents=[ExtentDescriptor(
                start_block=layout['catalog_start'],
                block_count=layout['catalog_blocks']
            )]
        )
        
        # 创建 Extents 文件 fork 数据
        extents_file = ForkData(
            logical_size=layout['extents_blocks'] * layout['block_size'],
            clump_size=self.DEFAULT_EXTENTS_CLUMP_SIZE,
            total_blocks=layout['extents_blocks'],
            extents=[ExtentDescriptor(
                start_block=layout['extents_start'],
                block_count=layout['extents_blocks']
            )]
        )
        
        # 创建卷头
        header = HFSPlusVolumeHeader(
            signature=signature,
            version=version,
            attributes=attributes,
            last_mounted_version='10.0',  # 模拟 macOS 10.x
            journal_info_block=0,
            create_date=current_hfs_date,
            modify_date=current_hfs_date,
            backup_date=0,
            checked_date=current_hfs_date,
            file_count=0,
            folder_count=1,  # 根目录
            block_size=layout['block_size'],
            total_blocks=layout['total_blocks'],
            free_blocks=layout['total_blocks'] - layout['system_blocks'],
            next_allocation=layout['system_blocks'],
            rsrc_clump_size=self.DEFAULT_CATALOG_CLUMP_SIZE,
            data_clump_size=self.DEFAULT_CATALOG_CLUMP_SIZE,
            next_catalog_id=CatalogNodeID.FIRST_USER,
            write_count=1,
            encodings_bitmap=0x1,  # MacRoman
            finder_info=finder_info,
            allocation_file=ForkData(
                logical_size=0,
                clump_size=0,
                total_blocks=0,
                extents=[]
            ),
            extents_file=extents_file,
            catalog_file=catalog_file,
            attributes_file=ForkData(
                logical_size=0,
                clump_size=0,
                total_blocks=0,
                extents=[]
            ),
            startup_file=ForkData(
                logical_size=0,
                clump_size=0,
                total_blocks=0,
                extents=[]
            )
        )
        
        return header
    
    def _write_volume_header(self, stream: BinaryIO, header: HFSPlusVolumeHeader):
        """写入卷头到偏移 1024"""
        stream.seek(VOLUME_HEADER_OFFSET)
        stream.write(header.to_bytes())
    
    def _write_backup_volume_header(self, stream: BinaryIO, header: HFSPlusVolumeHeader):
        """写入备份卷头到卷末尾"""
        # 备份卷头位于卷的最后一个块
        backup_offset = header.volume_size - VOLUME_HEADER_SIZE
        stream.seek(backup_offset)
        stream.write(header.to_bytes())
    
    def _initialize_allocation_bitmap(self, stream: BinaryIO, 
                                       header: HFSPlusVolumeHeader,
                                       layout: dict):
        """初始化分配位图"""
        block_size = layout['block_size']
        total_blocks = layout['total_blocks']
        
        # 创建位图数据
        bitmap_size = layout['bitmap_blocks'] * block_size
        bitmap_data = bytearray(bitmap_size)
        bitmap = AllocationBitmap(bytes(bitmap_data), block_size)
        
        # 标记系统区域为已使用
        # 块 0: 保留
        bitmap.allocate_block(0)
        
        # 块 1-2: 卷头区域
        bitmap.allocate_block(1)
        bitmap.allocate_block(2)
        
        # 分配位图块
        for i in range(layout['bitmap_blocks']):
            bitmap.allocate_block(layout['bitmap_start'] + i)
        
        # Catalog B-tree 块
        for i in range(layout['catalog_blocks']):
            bitmap.allocate_block(layout['catalog_start'] + i)
        
        # Extents B-tree 块
        for i in range(layout['extents_blocks']):
            bitmap.allocate_block(layout['extents_start'] + i)
        
        # 写入位图
        stream.seek(layout['bitmap_start'] * block_size)
        stream.write(bitmap.to_bytes())
    
    def _create_catalog_btree(self, stream: BinaryIO,
                               header: HFSPlusVolumeHeader,
                               layout: dict):
        """创建 Catalog B-tree"""
        block_size = layout['block_size']
        node_size = layout['catalog_node_size']
        start_offset = layout['catalog_start'] * block_size
        
        # 创建头节点（节点 0）
        self._create_btree_header_node(
            stream, start_offset, node_size,
            is_catalog=True
        )
        
        # 创建空的叶节点（节点 1）
        self._create_empty_leaf_node(stream, start_offset + node_size, node_size)
        
        # 创建位图节点（节点 2）
        self._create_bitmap_node(stream, start_offset + 2 * node_size, node_size)
        
        # 创建根目录
        self._create_root_directory(stream, start_offset, node_size, header)
    
    def _create_extents_btree(self, stream: BinaryIO,
                               header: HFSPlusVolumeHeader,
                               layout: dict):
        """创建 Extents Overflow B-tree"""
        block_size = layout['block_size']
        node_size = layout['extents_node_size']
        start_offset = layout['extents_start'] * block_size
        
        # 创建头节点（节点 0）
        self._create_btree_header_node(
            stream, start_offset, node_size,
            is_catalog=False
        )
        
        # 创建空的叶节点（节点 1）
        self._create_empty_leaf_node(stream, start_offset + node_size, node_size)
        
        # 创建位图节点（节点 2）
        self._create_bitmap_node(stream, start_offset + 2 * node_size, node_size)
    
    def _create_btree_header_node(self, stream: BinaryIO, offset: int,
                                   node_size: int, is_catalog: bool = True):
        """创建 B-tree 头节点"""
        # 创建节点描述符
        descriptor = BTNodeDescriptor(
            fLink=0,  # 没有下一个头节点
            bLink=0,  # 没有上一个头节点
            kind=BTreeNodeKind.HEADER,
            height=0,
            numRecords=3,  # 头记录 + 用户数据记录 + 保留记录
            reserved=0
        )
        
        # 创建头记录
        if is_catalog:
            max_key_length = 516  # Catalog key 最大长度
            key_compare_type = 0xCF  # HFS+ 贪心 Unicode 比较
        else:
            max_key_length = 16  # Extent key 最大长度
            key_compare_type = 0xBC  # 二进制比较
        
        header_rec = BTHeaderRec(
            treeDepth=1,  # 初始只有叶节点
            rootNode=1,   # 根节点是叶节点 1
            leafRecords=0,  # 初始没有记录
            firstLeafNode=1,
            lastLeafNode=1,
            nodeSize=node_size,
            maxKeyLength=max_key_length,
            totalNodes=3,  # 头节点 + 叶节点 + 位图节点
            freeNodes=0,
            reserved1=0,
            clumpSize=self.DEFAULT_CATALOG_CLUMP_SIZE if is_catalog else self.DEFAULT_EXTENTS_CLUMP_SIZE,
            btreeType=0,  # HFS+ B-tree
            keyCompareType=key_compare_type,
            attributes=0
        )
        
        # 构建节点数据
        data = bytearray(node_size)
        
        # 写入节点描述符
        data[0:BTREE_NODE_DESCRIPTOR_SIZE] = descriptor.to_bytes()
        
        # 写入头记录
        data[BTREE_NODE_DESCRIPTOR_SIZE:BTREE_NODE_DESCRIPTOR_SIZE + BTREE_HEADER_RECORD_SIZE] = header_rec.to_bytes()
        
        # 写入偏移表（从末尾反向）
        # 按照 HFS+ 规范，偏移表存储在节点末尾：
        # offsets[0] 在 node_size - (numRecords+1)*2
        # offsets[numRecords] 在 node_size - 2
        offsets = [
            BTREE_NODE_DESCRIPTOR_SIZE,  # 记录 0（头记录）的偏移
            BTREE_NODE_DESCRIPTOR_SIZE + BTREE_HEADER_RECORD_SIZE,  # 记录 1（用户数据）的偏移
            BTREE_NODE_DESCRIPTOR_SIZE + BTREE_HEADER_RECORD_SIZE + 128,  # 记录 2（保留）的偏移
            node_size - 8  # 空闲空间开始
        ]
        
        num_offsets = len(offsets)
        for i, offset_val in enumerate(offsets):
            pos = node_size - (num_offsets - i) * 2
            struct.pack_into('>H', data, pos, offset_val)
        
        # 写入到流
        stream.seek(offset)
        stream.write(bytes(data))
    
    def _create_empty_leaf_node(self, stream: BinaryIO, offset: int, node_size: int):
        """创建空的叶节点"""
        # 创建节点描述符
        descriptor = BTNodeDescriptor(
            fLink=0,  # 没有下一个叶节点
            bLink=0,  # 没有上一个叶节点
            kind=BTreeNodeKind.LEAF,
            height=1,
            numRecords=0,  # 空节点
            reserved=0
        )
        
        # 构建节点数据
        data = bytearray(node_size)
        
        # 写入节点描述符
        data[0:BTREE_NODE_DESCRIPTOR_SIZE] = descriptor.to_bytes()
        
        # 写入偏移表（只有结束标记）
        struct.pack_into('>H', data, node_size - 2, BTREE_NODE_DESCRIPTOR_SIZE)
        
        # 写入到流
        stream.seek(offset)
        stream.write(bytes(data))
    
    def _create_bitmap_node(self, stream: BinaryIO, offset: int, node_size: int):
        """创建位图节点"""
        # 创建节点描述符
        descriptor = BTNodeDescriptor(
            fLink=0,  # 没有下一个位图节点
            bLink=0,  # 没有上一个位图节点
            kind=BTreeNodeKind.MAP,
            height=0,
            numRecords=1,
            reserved=0
        )
        
        # 构建节点数据
        data = bytearray(node_size)
        
        # 写入节点描述符
        data[0:BTREE_NODE_DESCRIPTOR_SIZE] = descriptor.to_bytes()
        
        # 位图数据紧跟在描述符后面
        # 初始位图：前 3 个节点已使用（头节点、叶节点、位图节点）
        bitmap_offset = BTREE_NODE_DESCRIPTOR_SIZE
        data[bitmap_offset] = 0xE0  # 1110 0000 - 前 3 位已使用
        
        # 写入偏移表
        record_end = bitmap_offset + 1
        struct.pack_into('>H', data, node_size - 2, record_end)
        struct.pack_into('>H', data, node_size - 4, bitmap_offset)
        
        # 写入到流
        stream.seek(offset)
        stream.write(bytes(data))
    
    def _create_root_directory(self, stream: BinaryIO, btree_offset: int,
                                node_size: int, header: HFSPlusVolumeHeader):
        """创建根目录"""
        # 根目录的 CNID 是 2
        root_id = CatalogNodeID.ROOT_FOLDER
        root_parent_id = CatalogNodeID.ROOT_PARENT
        
        # 获取当前 HFS 日期
        current_hfs_date = int(time.time()) + HFS_EPOCH_OFFSET
        
        # 创建根目录的 Catalog 键
        # key_length = parentID(4) + nameLength(2) + name(0) = 6
        root_key = HFSPlusCatalogKey(
            key_length=6,
            parent_id=root_parent_id,
            node_name=""  # 根目录名称为空
        )
        
        # 创建根目录记录
        # 构造 BSD 权限 (16 字节)
        permissions = struct.pack('>II', 0, 0)  # ownerID, groupID
        permissions += struct.pack('>BB', 0, 0)  # adminFlags, ownerFlags
        permissions += struct.pack('>H', 0o40755)  # fileMode (目录)
        permissions += struct.pack('>I', 0)  # special
        
        # 创建文件夹记录
        folder_record = HFSPlusCatalogFolder(
            record_type=CatalogRecordType.FOLDER,
            flags=0,
            valence=0,  # 初始为空文件夹
            folder_id=root_id,
            create_date=current_hfs_date,
            content_mod_date=current_hfs_date,
            attribute_mod_date=current_hfs_date,
            access_date=current_hfs_date,
            backup_date=0,
            permissions=permissions,
            userInfo=b'\x00' * 8,
            finderInfo=b'\x00' * 8,
            text_encoding=0,
            reserved=0
        )
        
        # 创建线程记录的键
        # 线程记录的键是 (parentID=自己的CNID, name="")
        thread_key = HFSPlusCatalogKey(
            key_length=6,
            parent_id=root_id,
            node_name=""
        )
        
        # 创建线程记录
        thread_record = HFSPlusCatalogThread(
            record_type=CatalogRecordType.FOLDER_THREAD,
            reserved=0,
            parent_id=root_parent_id,
            node_name=""
        )
        
        # 读取叶节点（节点 1）
        leaf_offset = btree_offset + node_size
        stream.seek(leaf_offset)
        leaf_data = bytearray(stream.read(node_size))
        
        # 解析节点描述符
        descriptor = BTNodeDescriptor.from_bytes(bytes(leaf_data))
        
        # 计算记录位置
        record_offset = BTREE_NODE_DESCRIPTOR_SIZE
        
        # 写入文件夹记录
        # 记录格式: key + record_type + record_data
        # 注意: folder_record.to_bytes() 已经包含 record_type 字段
        key_bytes = root_key.to_bytes()
        folder_record_bytes = folder_record.to_bytes()
        
        leaf_data[record_offset:record_offset + len(key_bytes)] = key_bytes
        record_offset += len(key_bytes)
        leaf_data[record_offset:record_offset + len(folder_record_bytes)] = folder_record_bytes
        record_offset += len(folder_record_bytes)
        
        # 写入线程记录
        # 记录格式: key + record_type + record_data
        # 注意: thread_record.to_bytes() 已经包含 record_type 字段
        thread_key_bytes = thread_key.to_bytes()
        thread_record_bytes = thread_record.to_bytes()
        
        leaf_data[record_offset:record_offset + len(thread_key_bytes)] = thread_key_bytes
        record_offset += len(thread_key_bytes)
        leaf_data[record_offset:record_offset + len(thread_record_bytes)] = thread_record_bytes
        record_offset += len(thread_record_bytes)
        
        # 更新节点描述符
        descriptor.numRecords = 2
        descriptor.fLink = 0
        descriptor.bLink = 0
        leaf_data[0:BTREE_NODE_DESCRIPTOR_SIZE] = descriptor.to_bytes()
        
        # 更新偏移表
        # offset[0] = 记录0的开始位置
        # offset[1] = 记录1的开始位置
        # offset[2] = 空闲空间的开始位置（记录结束位置）
        folder_record_end = BTREE_NODE_DESCRIPTOR_SIZE + len(key_bytes) + len(folder_record_bytes)
        offsets = [
            BTREE_NODE_DESCRIPTOR_SIZE,  # 记录0开始
            folder_record_end,           # 记录1开始
            record_offset                # 空闲空间开始
        ]
        
        num_offsets = len(offsets)
        for i, offset_val in enumerate(offsets):
            pos = node_size - (num_offsets - i) * 2
            struct.pack_into('>H', leaf_data, pos, offset_val)
        
        # 写入更新后的叶节点
        stream.seek(leaf_offset)
        stream.write(bytes(leaf_data))
        
        # 更新头节点的叶记录数
        header_offset = btree_offset
        stream.seek(header_offset)
        header_data = bytearray(stream.read(node_size))
        
        # 解析头记录
        header_rec_offset = BTREE_NODE_DESCRIPTOR_SIZE
        header_rec = BTHeaderRec.from_bytes(bytes(header_data), header_rec_offset)
        header_rec.leafRecords = 2  # 文件夹记录 + 线程记录
        header_data[header_rec_offset:header_rec_offset + BTREE_HEADER_RECORD_SIZE] = header_rec.to_bytes()
        
        # 写入更新后的头节点
        stream.seek(header_offset)
        stream.write(bytes(header_data))


def format_volume(path: str, volume_name: str = "Untitled",
                  block_size: int = DEFAULT_BLOCK_SIZE) -> HFSPlusVolumeHeader:
    """
    格式化文件或设备为 HFS+（便捷函数）
    
    Args:
        path: 文件路径或设备路径
        volume_name: 卷名称
        block_size: 分配块大小（字节）
    
    Returns:
        创建的卷头
    
    Raises:
        FormatError: 格式化失败
    
    Example:
        >>> from src.core.hfs.formatter import format_volume
        >>> header = format_volume("/path/to/volume.img", "MyVolume")
        >>> print(header)
    """
    formatter = HFSPlusFormatter()
    return formatter.format(path, volume_name, block_size)
