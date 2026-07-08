"""
HFS+ 文件提取器

用于从 HFS+ 卷中提取文件和文件夹。
"""

import os
import struct
from typing import Optional, List, BinaryIO
from pathlib import Path

from .btree import (
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    ExtentsBTree,
    HFSPlusExtentKey,
    HFSPlusExtentRecord,
    HFSPlusExtentDescriptor,
    BTreeFile,
)
from .constants import HFS_EPOCH_OFFSET


class ExtractionError(Exception):
    """提取错误"""
    pass


class FileExtractor:
    """
    HFS+ 文件提取器
    
    用于从 HFS+ 卷中提取文件和文件夹。
    
    Usage:
        extractor = FileExtractor(stream, catalog, extents, block_size)
        extractor.extract_file(file_id, output_path)
        extractor.extract_folder(folder_id, output_dir)
    """
    
    def __init__(self, stream: BinaryIO, 
                 catalog: CatalogBTree,
                 extents: Optional[ExtentsBTree] = None,
                 block_size: int = 4096):
        """
        初始化文件提取器
        
        Args:
            stream: 可 seek 的二进制流
            catalog: Catalog B-tree
            extents: Extents B-tree (可选)
            block_size: 分配块大小
        """
        self.stream = stream
        self.catalog = catalog
        self.extents = extents
        self.block_size = block_size
    
    def extract_file(self, file_id: int, output_path: str,
                     overwrite: bool = False) -> bool:
        """
        提取单个文件
        
        Args:
            file_id: 文件 CNID
            output_path: 输出文件路径
            overwrite: 是否覆盖现有文件
        
        Returns:
            是否成功提取
        """
        # 检查目标文件是否已存在
        if os.path.exists(output_path) and not overwrite:
            raise ExtractionError(f"文件已存在: {output_path}")
        
        # 查找文件记录
        file_record = self._find_file_record(file_id)
        if file_record is None:
            raise ExtractionError(f"文件未找到: {file_id}")
        
        # 读取文件数据
        data = self._read_file_data(file_record)
        
        # 写入目标文件
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(data)
        
        return True
    
    def extract_folder(self, folder_id: int, output_dir: str,
                       recursive: bool = True, overwrite: bool = False) -> int:
        """
        提取文件夹
        
        Args:
            folder_id: 文件夹 CNID
            output_dir: 输出目录
            recursive: 是否递归提取子文件夹
            overwrite: 是否覆盖现有文件
        
        Returns:
            提取的文件数量
        """
        extracted_count = 0
        
        # 获取文件夹内容
        contents = self.catalog.list_folder_contents(folder_id)
        
        for item in contents:
            item_path = os.path.join(output_dir, item['name'])
            
            if item['type'] == 'folder':
                # 创建文件夹
                os.makedirs(item_path, exist_ok=True)
                
                # 递归提取子文件夹
                if recursive:
                    extracted_count += self.extract_folder(
                        item['id'], item_path, recursive, overwrite
                    )
            elif item['type'] == 'file':
                # 提取文件
                try:
                    self.extract_file(item['id'], item_path, overwrite)
                    extracted_count += 1
                except ExtractionError as e:
                    print(f"警告: 无法提取文件 {item['name']}: {e}")
        
        return extracted_count
    
    def _find_file_record(self, file_id: int) -> Optional[HFSPlusCatalogFile]:
        """查找文件记录"""
        for node in self.catalog.list_leaf_nodes():
            for i in range(node.num_records):
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusCatalogKey.from_bytes(data)
                
                # 解析记录类型
                record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                
                if record_type == CatalogRecordType.FILE:
                    file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                    if file.file_id == file_id:
                        return file
        
        return None
    
    def _read_file_data(self, file_record: HFSPlusCatalogFile) -> bytes:
        """
        读取文件数据
        
        Args:
            file_record: 文件记录
        
        Returns:
            文件数据
        """
        # 获取文件大小
        file_size = file_record.data_fork_size
        
        if file_size == 0:
            return b''
        
        # 读取数据分支
        # 注意：这里简化了实现，实际需要处理 extent 溢出
        # 目前只支持读取内联数据（存储在 catalog 记录中的数据）
        
        # 读取数据
        data = b''
        
        # 遍历 extent
        # 注意：这里需要实现完整的 extent 读取逻辑
        # 目前只是一个框架
        
        return data
    
    def get_file_info(self, file_id: int) -> Optional[dict]:
        """
        获取文件信息
        
        Args:
            file_id: 文件 CNID
        
        Returns:
            文件信息字典
        """
        file_record = self._find_file_record(file_id)
        if file_record is None:
            return None
        
        return {
            'id': file_record.file_id,
            'size': file_record.data_fork_size,
            'create_date': file_record.create_date,
            'mod_date': file_record.content_mod_date,
            'owner_id': file_record.owner_id,
            'group_id': file_record.group_id,
            'mode': file_record.file_mode,
        }


class FolderExtractor:
    """
    文件夹提取器
    
    用于递归提取整个文件夹结构。
    
    Usage:
        extractor = FolderExtractor(catalog, extractor)
        extractor.extract(folder_id, output_dir)
    """
    
    def __init__(self, catalog: CatalogBTree, file_extractor: FileExtractor):
        """
        初始化文件夹提取器
        
        Args:
            catalog: Catalog B-tree
            file_extractor: 文件提取器
        """
        self.catalog = catalog
        self.file_extractor = file_extractor
    
    def extract(self, folder_id: int, output_dir: str,
                overwrite: bool = False) -> int:
        """
        提取文件夹
        
        Args:
            folder_id: 文件夹 CNID
            output_dir: 输出目录
            overwrite: 是否覆盖现有文件
        
        Returns:
            提取的文件数量
        """
        return self.file_extractor.extract_folder(
            folder_id, output_dir, recursive=True, overwrite=overwrite
        )


class ExtractionProgress:
    """
    提取进度跟踪
    
    用于跟踪文件提取进度。
    
    Usage:
        progress = ExtractionProgress(total_files)
        progress.update(1)
        print(progress.progress_text)
    """
    
    def __init__(self, total_files: int = 0):
        """
        初始化进度跟踪
        
        Args:
            total_files: 总文件数
        """
        self.total_files = total_files
        self.extracted_files = 0
        self.current_file = ""
        self.errors: List[str] = []
    
    def update(self, count: int = 1, current_file: str = ""):
        """
        更新进度
        
        Args:
            count: 提取的文件数
            current_file: 当前正在提取的文件
        """
        self.extracted_files += count
        if current_file:
            self.current_file = current_file
    
    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total_files == 0:
            return 0.0
        return (self.extracted_files / self.total_files) * 100
    
    @property
    def progress_text(self) -> str:
        """进度文本"""
        return f"{self.extracted_files}/{self.total_files} 文件"
    
    @property
    def is_complete(self) -> bool:
        """是否完成"""
        return self.extracted_files >= self.total_files