"""
APFS 写入功能测试

测试 APFS 写入器的完整功能，包括：
- 文件创建
- 目录创建
- 文件删除
- 重命名
- 移动
- 文件数据读写
"""

import os
import tempfile
import struct
import pytest

# 导入被测模块
from src.core.apfs.writer import (
    APFSWriter, APFSFormatter, APFSInode, APFSDirEntry, APFSFileExtent,
    APFSObjectHeader, WriteObjType, DirEntryFlags, InodeFlags,
    create_apfs_file, create_apfs_directory, delete_apfs_entry,
    rename_apfs_entry, move_apfs_entry, format_apfs
)
from src.core.apfs.btree import BTreeManager, BTHeaderRec, JKey, ObjType
from src.core.apfs.space_manager import SpaceManager


class TestAPFSWriterInit:
    """测试 APFS 写入器初始化"""
    
    def test_writer_init(self, tmp_path):
        """测试写入器初始化"""
        # 创建测试文件
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        # 初始化写入器
        writer = APFSWriter(str(test_file))
        writer.open()
        
        # 验证初始化
        assert writer._space_manager is not None
        assert writer._catalog_tree is not None
        assert writer.block_size == 4096
        
        writer.close()
        
    def test_writer_context_manager(self, tmp_path):
        """测试上下文管理器"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            assert writer._file is not None
            
        # 文件应该已关闭
        assert writer._file is None


class TestAPFSBlockAllocation:
    """测试块分配"""
    
    def test_allocate_single_block(self, tmp_path):
        """测试分配单个块"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            block_num = writer._allocate_block()
            
            assert block_num is not None
            assert block_num >= 0
            
    def test_allocate_multiple_blocks(self, tmp_path):
        """测试分配多个块"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            blocks = writer._allocate_blocks(5)
            
            assert len(blocks) == 5
            assert len(set(blocks)) == 5  # 所有块号唯一
            
    def test_free_block(self, tmp_path):
        """测试释放块"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            block_num = writer._allocate_block()
            writer._free_block(block_num)
            
            # 释放后应该可以重新分配
            new_block = writer._allocate_block()
            assert new_block is not None


class TestAPFSInodeCreation:
    """测试 Inode 创建"""
    
    def test_create_inode(self, tmp_path):
        """测试创建 Inode"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            inode_id = writer.create_inode(
                parent_id=2,
                name="test.txt",
                is_dir=False,
                mode=0o644
            )
            
            assert inode_id > 0
            
            # 验证 Inode
            inode = writer.get_inode(inode_id)
            assert inode is not None
            assert inode.parent_id == 2
            assert inode.name == "test.txt"
            assert inode.mode & 0o100000  # 普通文件
            
    def test_create_directory_inode(self, tmp_path):
        """测试创建目录 Inode"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            dir_id = writer.create_inode(
                parent_id=2,
                name="testdir",
                is_dir=True,
                mode=0o755
            )
            
            inode = writer.get_inode(dir_id)
            assert inode is not None
            assert inode.mode & 0o40000  # 目录


class TestAPFSDirectoryEntry:
    """测试目录条目"""
    
    def test_create_directory_entry(self, tmp_path):
        """测试创建目录条目"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建子目录
            child_id = writer.create_inode(
                parent_id=2,
                name="child",
                is_dir=True
            )
            
            # 创建目录条目
            writer.create_directory_entry(2, child_id, "child", is_dir=True)
            
            # 验证条目
            entry = writer.get_dir_entry(2, "child")
            assert entry is not None
            assert entry.target_id == child_id
            assert entry.name == "child"


class TestAPFSFileOperations:
    """测试文件操作"""
    
    def test_create_file(self, tmp_path):
        """测试创建文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            file_id = writer.create_file(
                parent_id=2,
                name="test.txt",
                data=b"Hello, World!"
            )
            
            assert file_id > 0
            
            # 验证文件存在
            inode = writer.get_inode(file_id)
            assert inode is not None
            assert inode.name == "test.txt"
            assert inode.uncompressed_size == 13
            
    def test_create_file_with_data(self, tmp_path):
        """测试创建带数据的文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        test_data = b"A" * 10000  # 10KB 数据
        
        with APFSWriter(str(test_file)) as writer:
            file_id = writer.create_file(
                parent_id=2,
                name="large.bin",
                data=test_data
            )
            
            # 验证文件大小
            inode = writer.get_inode(file_id)
            assert inode.uncompressed_size == 10000
            
    def test_read_file_data(self, tmp_path):
        """测试读取文件数据"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        test_data = b"Hello, APFS Writer!"
        
        with APFSWriter(str(test_file)) as writer:
            file_id = writer.create_file(
                parent_id=2,
                name="test.txt",
                data=test_data
            )
            
            # 读取数据
            read_data = writer.read_file_data(file_id)
            assert read_data == test_data
            
    def test_create_directory(self, tmp_path):
        """测试创建目录"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            dir_id = writer.create_directory(
                parent_id=2,
                name="mydir"
            )
            
            assert dir_id > 0
            
            # 验证目录
            inode = writer.get_inode(dir_id)
            assert inode is not None
            assert inode.mode & 0o40000  # 目录标志


class TestAPFSDeleteOperations:
    """测试删除操作"""
    
    def test_delete_file(self, tmp_path):
        """测试删除文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建文件
            file_id = writer.create_file(
                parent_id=2,
                name="to_delete.txt",
                data=b"delete me"
            )
            
            # 删除文件
            result = writer.delete_entry(2, "to_delete.txt")
            assert result is True
            
            # 验证文件已删除
            inode = writer.get_inode(file_id)
            assert inode is None
            
    def test_delete_empty_directory(self, tmp_path):
        """测试删除空目录"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建目录
            dir_id = writer.create_directory(parent_id=2, name="empty_dir")
            
            # 删除目录
            result = writer.delete_entry(2, "empty_dir")
            assert result is True
            
    def test_delete_nonexistent(self, tmp_path):
        """测试删除不存在的文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            result = writer.delete_entry(2, "nonexistent.txt")
            assert result is False


class TestAPFSRenameOperations:
    """测试重命名操作"""
    
    def test_rename_file(self, tmp_path):
        """测试重命名文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建文件
            file_id = writer.create_file(
                parent_id=2,
                name="old_name.txt",
                data=b"test"
            )
            
            # 重命名
            result = writer.rename_entry(2, "old_name.txt", "new_name.txt")
            assert result is True
            
            # 验证旧名称不存在
            old_entry = writer.get_dir_entry(2, "old_name.txt")
            assert old_entry is None
            
            # 验证新名称存在
            new_entry = writer.get_dir_entry(2, "new_name.txt")
            assert new_entry is not None
            assert new_entry.target_id == file_id
            
            # 验证 Inode 名称已更新
            inode = writer.get_inode(file_id)
            assert inode.name == "new_name.txt"
            
    def test_rename_directory(self, tmp_path):
        """测试重命名目录"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建目录
            dir_id = writer.create_directory(parent_id=2, name="old_dir")
            
            # 重命名
            result = writer.rename_entry(2, "old_dir", "new_dir")
            assert result is True
            
            # 验证
            inode = writer.get_inode(dir_id)
            assert inode.name == "new_dir"


class TestAPFSMoveOperations:
    """测试移动操作"""
    
    def test_move_file(self, tmp_path):
        """测试移动文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建两个目录
            dir1_id = writer.create_directory(parent_id=2, name="dir1")
            dir2_id = writer.create_directory(parent_id=2, name="dir2")
            
            # 在 dir1 中创建文件
            file_id = writer.create_file(
                parent_id=dir1_id,
                name="movable.txt",
                data=b"move me"
            )
            
            # 移动文件到 dir2
            result = writer.move_entry(dir1_id, "movable.txt", dir2_id)
            assert result is True
            
            # 验证文件已从 dir1 移除
            old_entry = writer.get_dir_entry(dir1_id, "movable.txt")
            assert old_entry is None
            
            # 验证文件已添加到 dir2
            new_entry = writer.get_dir_entry(dir2_id, "movable.txt")
            assert new_entry is not None
            assert new_entry.target_id == file_id
            
    def test_move_and_rename(self, tmp_path):
        """测试移动并重命名"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            dir1_id = writer.create_directory(parent_id=2, name="dir1")
            dir2_id = writer.create_directory(parent_id=2, name="dir2")
            
            file_id = writer.create_file(
                parent_id=dir1_id,
                name="original.txt",
                data=b"test"
            )
            
            # 移动并重命名
            result = writer.move_entry(
                dir1_id, "original.txt",
                dir2_id, "renamed.txt"
            )
            assert result is True
            
            # 验证
            new_entry = writer.get_dir_entry(dir2_id, "renamed.txt")
            assert new_entry is not None
            assert new_entry.target_id == file_id
            
            inode = writer.get_inode(file_id)
            assert inode.name == "renamed.txt"
            assert inode.parent_id == dir2_id


class TestAPFSCopyOperations:
    """测试复制操作"""
    
    def test_copy_file(self, tmp_path):
        """测试复制文件"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            dir1_id = writer.create_directory(parent_id=2, name="dir1")
            dir2_id = writer.create_directory(parent_id=2, name="dir2")
            
            # 创建源文件
            src_id = writer.create_file(
                parent_id=dir1_id,
                name="source.txt",
                data=b"copy me"
            )
            
            # 复制文件
            new_id = writer.copy_entry(dir1_id, "source.txt", dir2_id)
            
            assert new_id is not None
            assert new_id != src_id
            
            # 验证两个文件都存在
            src_inode = writer.get_inode(src_id)
            new_inode = writer.get_inode(new_id)
            
            assert src_inode is not None
            assert new_inode is not None
            
            # 验证数据相同
            src_data = writer.read_file_data(src_id)
            new_data = writer.read_file_data(new_id)
            assert src_data == new_data


class TestAPFSListDirectory:
    """测试目录列表"""
    
    def test_list_empty_directory(self, tmp_path):
        """测试列出空目录"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            entries = writer.list_directory(2)
            # 可能包含系统创建的特殊目录
            # 具体数量取决于实现
            
    def test_list_directory_with_files(self, tmp_path):
        """测试列出包含文件的目录"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            # 创建一些文件和目录
            writer.create_file(parent_id=2, name="file1.txt", data=b"1")
            writer.create_file(parent_id=2, name="file2.txt", data=b"2")
            writer.create_directory(parent_id=2, name="subdir")
            
            # 列出目录
            entries = writer.list_directory(2)
            
            # 验证
            names = [e['name'] for e in entries]
            assert "file1.txt" in names
            assert "file2.txt" in names
            assert "subdir" in names


class TestAPFSFormatter:
    """测试 APFS 格式化器"""
    
    def test_format_new_volume(self, tmp_path):
        """测试格式化新卷"""
        test_file = tmp_path / "new.apfs"
        
        result = format_apfs(
            str(test_file),
            volume_name="TestVolume",
            block_size=4096
        )
        
        assert result['volume_name'] == "TestVolume"
        assert result['block_size'] == 4096
        assert result['total_blocks'] > 0
        
        # 验证文件已创建
        assert test_file.exists()
        assert test_file.stat().st_size > 0


class TestAPFSWriterInfo:
    """测试写入器信息"""
    
    def test_get_info(self, tmp_path):
        """测试获取信息"""
        test_file = tmp_path / "test.apfs"
        test_file.write_bytes(b'\x00' * (4096 * 100))
        
        with APFSWriter(str(test_file)) as writer:
            info = writer.get_info()
            
            assert 'block_size' in info
            assert 'next_oid' in info
            assert 'next_xid' in info
            assert 'space' in info
            assert 'catalog' in info


class TestAPFSDataStructures:
    """测试数据结构"""
    
    def test_inode_roundtrip(self):
        """测试 Inode 序列化/反序列化"""
        inode = APFSInode(
            header=APFSObjectHeader(
                oid=100,
                xid=1,
                type=WriteObjType.INODE,
                flags=0,
                subtype=0,
                size=APFSInode.SIZE
            ),
            parent_id=2,
            private_id=100,
            create_time=1000000000,
            mod_time=1000000000,
            change_time=1000000000,
            access_time=1000000000,
            internal_flags=0,
            nchildren_or_nlink=1,
            default_protection_class=0,
            write_gen_counter=0,
            bsd_flags=0,
            owner=0,
            group=0,
            mode=0o100644,
            uncompressed_size=1024,
            name="test.txt"
        )
        
        data = inode.to_bytes()
        restored = APFSInode.from_bytes(data)
        
        assert restored.header.oid == 100
        assert restored.parent_id == 2
        assert restored.mode == 0o100644
        
    def test_dir_entry_roundtrip(self):
        """测试目录条目序列化/反序列化"""
        entry = APFSDirEntry(
            header=APFSObjectHeader(
                oid=200,
                xid=1,
                type=WriteObjType.DIR_REC,
                flags=0,
                subtype=0,
                size=APFSDirEntry.SIZE
            ),
            target_id=100,
            date_added=1000000000,
            flags=0,
            name="myfile.txt"
        )
        
        data = entry.to_bytes()
        restored = APFSDirEntry.from_bytes(data)
        
        assert restored.target_id == 100
        assert restored.name == "myfile.txt"
        
    def test_file_extent_roundtrip(self):
        """测试文件扩展序列化/反序列化"""
        extent = APFSFileExtent(
            header=APFSObjectHeader(
                oid=300,
                xid=1,
                type=WriteObjType.FILE_EXTENT,
                flags=0,
                subtype=0,
                size=APFSFileExtent.SIZE
            ),
            private_id=100,
            logical_addr=0,
            length=4096,
            phys_block_num=50,
            crypto_id=0
        )
        
        data = extent.to_bytes()
        restored = APFSFileExtent.from_bytes(data)
        
        assert restored.private_id == 100
        assert restored.phys_block_num == 50
        assert restored.length == 4096


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
