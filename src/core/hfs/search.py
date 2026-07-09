"""
HFS+ 搜索功能

提供文件和文件夹的搜索功能。
"""

import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from src.core.hfs import (
    CatalogBTree,
    CatalogRecordType,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    HFS_EPOCH_OFFSET,
)


class SearchMatchType(Enum):
    """搜索匹配类型"""
    EXACT = "exact"          # 精确匹配
    CONTAINS = "contains"    # 包含
    STARTS_WITH = "starts_with"  # 开头匹配
    ENDS_WITH = "ends_with"  # 结尾匹配
    REGEX = "regex"          # 正则表达式


class SearchFilter(Enum):
    """搜索过滤器"""
    ALL = "all"          # 所有
    FILES_ONLY = "files"  # 仅文件
    FOLDERS_ONLY = "folders"  # 仅文件夹


@dataclass
class SearchResult:
    """
    搜索结果
    
    Attributes:
        name: 文件/文件夹名称
        path: 路径
        item_type: 类型 (file/folder)
        size: 文件大小 (仅文件)
        create_date: 创建日期
        mod_date: 修改日期
        parent_id: 父文件夹 ID
        item_id: 项目 ID
    """
    name: str
    path: str
    item_type: str
    size: int = 0
    create_date: int = 0
    mod_date: int = 0
    parent_id: int = 0
    item_id: int = 0


class SearchEngine:
    """
    搜索引擎
    
    用于在 HFS+ 卷中搜索文件和文件夹。
    
    Usage:
        engine = SearchEngine(catalog)
        results = engine.search("*.txt")
    """
    
    def __init__(self, catalog: CatalogBTree):
        """
        初始化搜索引擎
        
        Args:
            catalog: Catalog B-tree
        """
        self.catalog = catalog
        self._results: List[SearchResult] = []
        self._is_searching = False
    
    @property
    def results(self) -> List[SearchResult]:
        """获取搜索结果"""
        return self._results.copy()
    
    @property
    def result_count(self) -> int:
        """获取搜索结果数量"""
        return len(self._results)
    
    def search(self, query: str, 
               match_type: SearchMatchType = SearchMatchType.CONTAINS,
               case_sensitive: bool = False,
               search_filter: SearchFilter = SearchFilter.ALL,
               max_results: int = 1000) -> List[SearchResult]:
        """
        搜索文件和文件夹
        
        Args:
            query: 搜索查询
            match_type: 匹配类型
            case_sensitive: 是否区分大小写
            search_filter: 搜索过滤器
            max_results: 最大结果数
        
        Returns:
            搜索结果列表
        """
        self._results.clear()
        self._is_searching = True
        
        # 编译正则表达式（如果需要）
        pattern = None
        if match_type == SearchMatchType.REGEX:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(query, flags)
            except re.error:
                return []
        
        # 遍历所有叶记录
        for node in self.catalog.list_leaf_nodes():
            if not self._is_searching:
                break
            
            for i in range(node.num_records):
                if len(self._results) >= max_results:
                    break
                
                data = node.get_record_data(i)
                
                # 解析键
                key = HFSPlusCatalogKey.from_bytes(data)
                
                # 检查是否匹配
                if self._matches_query(key.node_name, query, match_type, 
                                       case_sensitive, pattern):
                    # 获取记录类型
                    record_type = struct.unpack_from('>H', data, key.occupied_size)[0]
                    
                    # 应用过滤器
                    if search_filter == SearchFilter.FILES_ONLY and \
                       record_type != CatalogRecordType.FILE:
                        continue
                    if search_filter == SearchFilter.FOLDERS_ONLY and \
                       record_type != CatalogRecordType.FOLDER:
                        continue
                    
                    # 创建搜索结果
                    result = SearchResult(
                        name=key.node_name,
                        path="",  # TODO: 构建完整路径
                        item_type="file" if record_type == CatalogRecordType.FILE else "folder",
                        parent_id=key.parent_id,
                    )
                    
                    # 添加额外信息
                    if record_type == CatalogRecordType.FILE:
                        file = HFSPlusCatalogFile.from_bytes(data, key.occupied_size)
                        result.size = file.get_data_fork_size()
                        result.create_date = file.create_date
                        result.mod_date = file.content_mod_date
                        result.item_id = file.file_id
                    elif record_type == CatalogRecordType.FOLDER:
                        folder = HFSPlusCatalogFolder.from_bytes(data, key.occupied_size)
                        result.create_date = folder.create_date
                        result.mod_date = folder.content_mod_date
                        result.item_id = folder.folder_id
                    
                    self._results.append(result)
        
        self._is_searching = False
        return self._results.copy()
    
    def stop_search(self):
        """停止搜索"""
        self._is_searching = False
    
    def _matches_query(self, name: str, query: str, 
                       match_type: SearchMatchType,
                       case_sensitive: bool,
                       pattern: Optional[re.Pattern]) -> bool:
        """
        检查名称是否匹配查询
        
        Args:
            name: 文件/文件夹名称
            query: 搜索查询
            match_type: 匹配类型
            case_sensitive: 是否区分大小写
            pattern: 编译后的正则表达式（仅 REGEX 类型）
        
        Returns:
            是否匹配
        """
        if not case_sensitive:
            name = name.lower()
            query = query.lower()
        
        if match_type == SearchMatchType.EXACT:
            return name == query
        elif match_type == SearchMatchType.CONTAINS:
            return query in name
        elif match_type == SearchMatchType.STARTS_WITH:
            return name.startswith(query)
        elif match_type == SearchMatchType.ENDS_WITH:
            return name.endswith(query)
        elif match_type == SearchMatchType.REGEX:
            if pattern is None:
                return False
            return bool(pattern.search(name))
        
        return False


import struct


class SearchDialog:
    """
    搜索对话框
    
    提供搜索界面。
    """
    
    def __init__(self, parent=None):
        self.parent = parent
        self.engine: Optional[SearchEngine] = None
    
    def set_catalog(self, catalog: CatalogBTree):
        """设置 Catalog"""
        self.engine = SearchEngine(catalog)
    
    def search(self, query: str, **kwargs) -> List[SearchResult]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            **kwargs: 其他搜索参数
        
        Returns:
            搜索结果列表
        """
        if self.engine is None:
            return []
        
        return self.engine.search(query, **kwargs)