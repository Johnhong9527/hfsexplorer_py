"""
端到端流程测试

测试从设备识别到导出数据的完整流程。
"""

import tempfile
import os
import pytest

from src.core.hfs.formatter import format_volume
from src.core.hfs.reader import HFSPlusVolume
from src.core.hfs.writer import CatalogWriter
from src.core.hfs.btree import CatalogBTree
from src.core.hfs.structures import HFSPlusVolumeHeader
from src.core.hfs.constants import VOLUME_HEADER_OFFSET, VOLUME_HEADER_SIZE


class TestEndToEndFlow:
    """端到端流程测试"""
    
    @pytest.fixture
    def test_volume(self):
        """创建测试卷"""
        with tempfile.NamedTemporaryFile(suffix='.img', delete=False) as f:
            path = f.name
        
        # 1. 格式化创建新卷
        with open(path, 'wb') as f:
            f.seek(10 * 1024 * 1024 - 1)  # 10 MB
            f.write(b'\x00')
        
        header = format_volume(path, 'TestVolume', 4096)
        
        yield path
        
        os.unlink(path)
    
    def test_complete_flow(self, test_volume):
        """测试完整流程：创建卷 -> 写入文件 -> 读取 -> 提取"""
        path = test_volume
        
        # 2. 写入测试文件
        with open(path, 'r+b') as f:
            f.seek(VOLUME_HEADER_OFFSET)
            header_data = f.read(VOLUME_HEADER_SIZE)
            vol_header = HFSPlusVolumeHeader.from_bytes(header_data)
            
            catalog_extents = vol_header.catalog_file.extents
            catalog_start = catalog_extents[0].start_block * vol_header.block_size
            catalog = CatalogBTree(f, start_offset=catalog_start, node_size=4096)
            
            writer = CatalogWriter(catalog, vol_header, f)
            
            # 创建文件夹
            folder_id = writer.create_folder(2, 'Documents')
            assert folder_id > 0
            
            # 创建文件
            test_content = b'Hello, HFS+ World! This is a test file.'
            file_id = writer.create_file(2, 'test.txt', test_content)
            assert file_id > 0
            
            # 创建另一个文件
            writer.create_file(2, 'readme.md', b'# Test README')
        
        # 3. 读取卷信息
        with HFSPlusVolume(path) as vol:
            info = vol.get_info()
            assert info['signature'] == 'HFS+'
            assert info['folder_count'] >= 1
            
            # 4. 浏览根目录
            root_contents = vol.list_folder(2)
            assert len(root_contents) >= 2  # 至少有 Documents 和 test.txt
            
            # 验证文件存在
            file_names = [item['name'] for item in root_contents]
            assert 'test.txt' in file_names
            assert 'readme.md' in file_names
            assert 'Documents' in file_names
            
            # 5. 提取文件
            for item in root_contents:
                if item['name'] == 'test.txt' and item['type'] == 'file':
                    data = vol.read_file(item['id'])
                    assert data == test_content
                    break
        
        print("✅ 完整流程测试通过！")
    
    def test_device_to_export_flow(self, test_volume):
        """测试设备到导出流程"""
        path = test_volume
        
        # 1. 先写入测试文件
        with open(path, 'r+b') as f:
            f.seek(VOLUME_HEADER_OFFSET)
            header_data = f.read(VOLUME_HEADER_SIZE)
            vol_header = HFSPlusVolumeHeader.from_bytes(header_data)
            
            catalog_extents = vol_header.catalog_file.extents
            catalog_start = catalog_extents[0].start_block * vol_header.block_size
            catalog = CatalogBTree(f, start_offset=catalog_start, node_size=4096)
            
            writer = CatalogWriter(catalog, vol_header, f)
            writer.create_file(2, 'test.txt', b'Hello World')
            writer.create_file(2, 'readme.md', b'# Test')
        
        # 2. 模拟设备检测（直接使用文件）
        assert os.path.exists(path)
        
        # 3. 加载卷
        with HFSPlusVolume(path) as vol:
            # 4. 获取卷信息
            info = vol.get_info()
            print(f"   卷类型: {info['signature']}")
            print(f"   文件数: {info['file_count']}")
            print(f"   文件夹数: {info['folder_count']}")
            
            # 5. 浏览文件
            contents = vol.list_folder(2)
            print(f"   根目录内容: {len(contents)} 项")
            
            # 6. 导出到临时目录
            with tempfile.TemporaryDirectory() as export_dir:
                exported_count = 0
                
                for item in contents:
                    if item['type'] == 'file':
                        # 读取文件
                        data = vol.read_file(item['id'])
                        
                        # 写入到导出目录
                        output_path = os.path.join(export_dir, item['name'])
                        with open(output_path, 'wb') as f:
                            f.write(data)
                        
                        exported_count += 1
                        print(f"   导出: {item['name']} ({len(data)} bytes)")
                
                print(f"   导出文件数: {exported_count}")
                assert exported_count > 0
        
        print("✅ 设备到导出流程测试通过！")
    
    def test_search_flow(self, test_volume):
        """测试搜索流程"""
        path = test_volume
        
        # 先写入一些文件
        with open(path, 'r+b') as f:
            f.seek(VOLUME_HEADER_OFFSET)
            header_data = f.read(VOLUME_HEADER_SIZE)
            vol_header = HFSPlusVolumeHeader.from_bytes(header_data)
            
            catalog_extents = vol_header.catalog_file.extents
            catalog_start = catalog_extents[0].start_block * vol_header.block_size
            catalog = CatalogBTree(f, start_offset=catalog_start, node_size=4096)
            
            writer = CatalogWriter(catalog, vol_header, f)
            writer.create_file(2, 'document.txt', b'Document content')
            writer.create_file(2, 'image.jpg', b'Fake image')
            writer.create_file(2, 'script.py', b'print("hello")')
        
        # 搜索测试
        from src.core.hfs.search import SearchEngine, SearchMatchType, SearchFilter
        
        with HFSPlusVolume(path) as vol:
            engine = SearchEngine(vol.catalog)
            
            # 搜索 .txt 文件
            results = engine.search('.txt', match_type=SearchMatchType.ENDS_WITH)
            txt_files = [r.name for r in results]
            assert 'document.txt' in txt_files
            
            # 搜索包含 "script" 的文件
            results = engine.search('script', match_type=SearchMatchType.CONTAINS)
            script_files = [r.name for r in results]
            assert 'script.py' in script_files
        
        print("✅ 搜索流程测试通过！")
    
    def test_write_and_verify_flow(self, test_volume):
        """测试写入并验证流程"""
        path = test_volume
        
        # 写入
        with open(path, 'r+b') as f:
            f.seek(VOLUME_HEADER_OFFSET)
            header_data = f.read(VOLUME_HEADER_SIZE)
            vol_header = HFSPlusVolumeHeader.from_bytes(header_data)
            
            catalog_extents = vol_header.catalog_file.extents
            catalog_start = catalog_extents[0].start_block * vol_header.block_size
            catalog = CatalogBTree(f, start_offset=catalog_start, node_size=4096)
            
            writer = CatalogWriter(catalog, vol_header, f)
            
            # 创建多层结构
            writer.create_folder(2, 'Level1')
            writer.create_file(2, 'root.txt', b'Root file')
        
        # 验证
        with HFSPlusVolume(path) as vol:
            contents = vol.list_folder(2)
            
            # 验证文件夹存在
            folders = [item for item in contents if item['type'] == 'folder']
            assert any(f['name'] == 'Level1' for f in folders)
            
            # 验证文件存在
            files = [item for item in contents if item['type'] == 'file']
            assert any(f['name'] == 'root.txt' for f in files)
            
            # 验证文件内容
            for f in files:
                if f['name'] == 'root.txt':
                    data = vol.read_file(f['id'])
                    assert data == b'Root file'
        
        print("✅ 写入并验证流程测试通过！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
