"""
HFS+ 搜索功能测试

测试文件和文件夹的搜索功能。
"""

import tempfile
import os
import pytest

from src.core.hfs.formatter import format_volume
from src.core.hfs.writer import CatalogWriter
from src.core.hfs.btree import CatalogBTree
from src.core.hfs.search import SearchEngine, SearchMatchType, SearchFilter
from src.core.hfs.structures import HFSPlusVolumeHeader
from src.core.hfs.constants import VOLUME_HEADER_OFFSET, VOLUME_HEADER_SIZE


@pytest.fixture
def test_volume():
    """创建测试卷"""
    with tempfile.NamedTemporaryFile(suffix='.hfs', delete=False) as f:
        path = f.name
    
    # 格式化
    with open(path, 'wb') as f:
        f.seek(10 * 1024 * 1024 - 1)
        f.write(b'\x00')
    
    format_volume(path, 'Test', 4096)
    
    # 写入测试数据
    f = open(path, 'r+b')
    f.seek(VOLUME_HEADER_OFFSET)
    header_data = f.read(VOLUME_HEADER_SIZE)
    vol_header = HFSPlusVolumeHeader.from_bytes(header_data)
    
    catalog_extents = vol_header.catalog_file.extents
    catalog_start = catalog_extents[0].start_block * vol_header.block_size
    catalog = CatalogBTree(f, start_offset=catalog_start, node_size=4096)
    
    writer = CatalogWriter(catalog, vol_header, f)
    
    # 创建文件夹
    writer.create_folder(2, 'Documents')
    writer.create_folder(2, 'Pictures')
    writer.create_folder(2, 'Music')
    writer.create_folder(2, 'test_folder')
    
    # 创建文件
    writer.create_file(2, 'readme.txt', b'Hello World')
    writer.create_file(2, 'test.py', b'print("test")')
    writer.create_file(2, 'image.jpg', b'fake image data')
    writer.create_file(2, 'data.csv', b'a,b,c')
    writer.create_file(2, 'README.TXT', b'Upper case')
    
    yield path, catalog, f
    
    f.close()
    os.unlink(path)


class TestSearchEngine:
    """搜索引擎测试"""
    
    def test_search_contains(self, test_volume):
        """测试包含匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索包含 "test" 的项目
        results = engine.search('test', match_type=SearchMatchType.CONTAINS)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' in names
    
    def test_search_exact(self, test_volume):
        """测试精确匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 精确搜索 "readme.txt"（区分大小写）
        results = engine.search('readme.txt', match_type=SearchMatchType.EXACT,
                              case_sensitive=True)
        
        assert len(results) == 1
        assert results[0].name == 'readme.txt'
        assert results[0].item_type == 'file'
    
    def test_search_starts_with(self, test_volume):
        """测试开头匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索以 "test" 开头的项目
        results = engine.search('test', match_type=SearchMatchType.STARTS_WITH)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' in names
        assert 'readme.txt' not in names
    
    def test_search_ends_with(self, test_volume):
        """测试结尾匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索以 ".txt" 结尾的项目
        results = engine.search('.txt', match_type=SearchMatchType.ENDS_WITH)
        names = [r.name for r in results]
        
        assert 'readme.txt' in names
        assert 'README.TXT' in names
        assert 'test.py' not in names
    
    def test_search_regex(self, test_volume):
        """测试正则表达式匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索 .txt 或 .py 文件
        results = engine.search(r'\.(txt|py)$', match_type=SearchMatchType.REGEX)
        names = [r.name for r in results]
        
        assert 'readme.txt' in names
        assert 'README.TXT' in names
        assert 'test.py' in names
        assert 'image.jpg' not in names
    
    def test_search_case_sensitive(self, test_volume):
        """测试区分大小写"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 区分大小写搜索 "readme"
        results = engine.search('readme', match_type=SearchMatchType.CONTAINS,
                               case_sensitive=True)
        names = [r.name for r in results]
        
        assert 'readme.txt' in names
        assert 'README.TXT' not in names
    
    def test_search_case_insensitive(self, test_volume):
        """测试不区分大小写"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 不区分大小写搜索 "readme"
        results = engine.search('readme', match_type=SearchMatchType.CONTAINS,
                               case_sensitive=False)
        names = [r.name for r in results]
        
        assert 'readme.txt' in names
        assert 'README.TXT' in names
    
    def test_search_files_only(self, test_volume):
        """测试仅搜索文件"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索文件
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               search_filter=SearchFilter.FILES_ONLY)
        
        for r in results:
            assert r.item_type == 'file'
    
    def test_search_folders_only(self, test_volume):
        """测试仅搜索文件夹"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索文件夹
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               search_filter=SearchFilter.FOLDERS_ONLY)
        
        for r in results:
            assert r.item_type == 'folder'
    
    def test_search_max_results(self, test_volume):
        """测试最大结果数"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 限制结果数
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               max_results=3)
        
        assert len(results) <= 3
    
    def test_search_result_fields(self, test_volume):
        """测试搜索结果字段"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索文件（区分大小写）
        results = engine.search('readme.txt', match_type=SearchMatchType.EXACT,
                              case_sensitive=True)
        
        assert len(results) == 1
        result = results[0]
        
        assert result.name == 'readme.txt'
        assert result.item_type == 'file'
        assert result.size == 11  # len(b'Hello World')
        assert result.item_id > 0
        assert result.parent_id == 2  # 根目录
    
    def test_search_empty_query(self, test_volume):
        """测试空查询"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 空查询应该匹配所有
        results = engine.search('', match_type=SearchMatchType.CONTAINS)
        
        assert len(results) > 0
    
    def test_search_no_results(self, test_volume):
        """测试无结果"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 搜索不存在的文件
        results = engine.search('nonexistent.xyz', match_type=SearchMatchType.EXACT)
        
        assert len(results) == 0
    
    def test_stop_search(self, test_volume):
        """测试停止搜索"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        # 启动搜索后立即停止
        engine._is_searching = True
        engine.stop_search()
        
        assert engine._is_searching is False


class TestSearchMatchType:
    """搜索匹配类型测试"""
    
    def test_exact_match(self, test_volume):
        """测试精确匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('test.py', match_type=SearchMatchType.EXACT)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' not in names
    
    def test_contains_match(self, test_volume):
        """测试包含匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('test', match_type=SearchMatchType.CONTAINS)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' in names
    
    def test_starts_with_match(self, test_volume):
        """测试开头匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('test', match_type=SearchMatchType.STARTS_WITH)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' in names
        assert 'readme.txt' not in names
    
    def test_ends_with_match(self, test_volume):
        """测试结尾匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('.txt', match_type=SearchMatchType.ENDS_WITH)
        names = [r.name for r in results]
        
        assert 'readme.txt' in names
        assert 'README.TXT' in names
        assert 'test.py' not in names
    
    def test_regex_match(self, test_volume):
        """测试正则表达式匹配"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search(r'^test', match_type=SearchMatchType.REGEX)
        names = [r.name for r in results]
        
        assert 'test.py' in names
        assert 'test_folder' in names
        assert 'readme.txt' not in names


class TestSearchFilter:
    """搜索过滤器测试"""
    
    def test_filter_all(self, test_volume):
        """测试所有类型"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               search_filter=SearchFilter.ALL)
        
        has_files = any(r.item_type == 'file' for r in results)
        has_folders = any(r.item_type == 'folder' for r in results)
        
        assert has_files
        assert has_folders
    
    def test_filter_files_only(self, test_volume):
        """测试仅文件"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               search_filter=SearchFilter.FILES_ONLY)
        
        assert all(r.item_type == 'file' for r in results)
    
    def test_filter_folders_only(self, test_volume):
        """测试仅文件夹"""
        path, catalog, f = test_volume
        engine = SearchEngine(catalog)
        
        results = engine.search('', match_type=SearchMatchType.CONTAINS,
                               search_filter=SearchFilter.FOLDERS_ONLY)
        
        assert all(r.item_type == 'folder' for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
