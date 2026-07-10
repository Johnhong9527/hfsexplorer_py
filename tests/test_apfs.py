"""
APFS 模块测试

测试 APFS 数据结构和读取器
"""

import struct
import pytest
from pathlib import Path

from src.core.apfs.structures import (
    NX_MAGIC, APFS_MAGIC, NXSuperblock, APFSSuperblock,
    BTNodeDescriptor, BTInfo, JKey, JInode, JDirEntry,
    OMAP, OMAPEntry, ObjType
)


class TestAPFSStructures:
    """测试 APFS 数据结构"""
    
    def test_nx_magic(self):
        """测试容器魔数"""
        assert NX_MAGIC == b'NXSB'
        
    def test_apfs_magic(self):
        """测试卷魔数"""
        assert APFS_MAGIC == b'APSB'
        
    def test_jkey_from_bytes(self):
        """测试 JKey 解析"""
        # 创建测试数据
        obj_id = 12345
        obj_type = 1
        data = struct.pack('<QH', obj_id, obj_type)
        
        # 解析
        jkey = JKey.from_bytes(data)
        
        assert jkey.obj_id == obj_id
        assert jkey.type == obj_type
        
    def test_jinode_from_bytes(self):
        """测试 JInode 解析"""
        # 创建测试数据
        parent_id = 1
        private_id = 100
        create_time = 1000000000
        mod_time = 2000000000
        change_time = 3000000000
        access_time = 4000000000
        internal_flags = 0
        nchildren = 5
        nlink = 1
        uid = 501
        gid = 20
        mode = 0o100644  # 普通文件
        pad1 = 0
        pad2 = 0
        bsd_flags = 0
        rdev = 0
        nsec = 0
        
        data = struct.pack(
            '<QQQQQQQiiIIIHHIIQ',
            parent_id, private_id, create_time, mod_time,
            change_time, access_time, internal_flags,
            nchildren, nlink, uid, gid, mode,
            pad1, pad2, bsd_flags, rdev, nsec
        )
        
        # 解析
        inode = JInode.from_bytes(data)
        
        assert inode.parent_id == parent_id
        assert inode.private_id == private_id
        assert inode.create_time == create_time
        assert inode.mod_time == mod_time
        assert inode.nchildren == nchildren
        assert inode.nlink == nlink
        assert inode.uid == uid
        assert inode.gid == gid
        assert inode.mode == mode
        
    def test_bt_node_descriptor_from_bytes(self):
        """测试 BTNodeDescriptor 解析"""
        # 创建测试数据
        node_type = 1
        flags = 0
        left_sibling = 100
        right_sibling = 200
        
        data = struct.pack('<HHQQ', node_type, flags, left_sibling, right_sibling)
        
        # 解析
        node_desc = BTNodeDescriptor.from_bytes(data)
        
        assert node_desc.type == node_type
        assert node_desc.flags == flags
        assert node_desc.left_sibling == left_sibling
        assert node_desc.right_sibling == right_sibling
        
    def test_btinfo_from_bytes(self):
        """测试 BTInfo 解析"""
        # 创建测试数据
        flags = 0
        node_size = 4096
        key_size = 16
        val_size = 32
        
        data = struct.pack('<IIII', flags, node_size, key_size, val_size)
        
        # 解析
        btinfo = BTInfo.from_bytes(data)
        
        assert btinfo.flags == flags
        assert btinfo.node_size == node_size
        assert btinfo.key_size == key_size
        assert btinfo.val_size == val_size
        
    def test_omap_from_bytes(self):
        """测试 OMAP 解析"""
        # 创建测试数据
        flags = 0
        snap_count = 0
        tree_type = 2
        tree_oid = 100
        latest_snap_xid = 0
        
        data = struct.pack('<IIIIQ', flags, snap_count, tree_type, tree_oid, latest_snap_xid)
        
        # 解析
        omap = OMAP.from_bytes(data)
        
        assert omap.flags == flags
        assert omap.snap_count == snap_count
        assert omap.tree_type == tree_type
        assert omap.tree_oid == tree_oid
        assert omap.latest_snap_xid == latest_snap_xid
        
    def test_omap_entry_from_bytes(self):
        """测试 OMAPEntry 解析"""
        # 创建测试数据
        oid = 12345
        xid = 67890
        paddr = 100
        
        data = struct.pack('<QQQ', oid, xid, paddr)
        
        # 解析
        entry = OMAPEntry.from_bytes(data)
        
        assert entry.oid == oid
        assert entry.xid == xid
        assert entry.paddr == paddr


class TestAPFSReader:
    """测试 APFS 读取器"""
    
    def test_reader_init(self):
        """测试读取器初始化"""
        from src.core.apfs.reader import APFSReader
        
        reader = APFSReader("/tmp/test.img")
        assert reader.file_path == Path("/tmp/test.img")
        assert reader.container is None
        assert reader.block_size == 4096
        assert reader.volumes == {}
        
    def test_reader_context_manager(self):
        """测试读取器上下文管理器"""
        from src.core.apfs.reader import APFSReader
        
        # 创建临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 4096)
            temp_path = f.name
            
        try:
            # 测试上下文管理器
            with pytest.raises(ValueError):  # 不是有效的 APFS 容器
                with APFSReader(temp_path) as reader:
                    pass
        finally:
            import os
            os.unlink(temp_path)


class TestAPFSContainer:
    """测试 APFS 容器"""
    
    def test_container_init(self):
        """测试容器初始化"""
        from src.core.apfs.container import APFSContainer
        from src.core.apfs.reader import APFSReader
        
        reader = APFSReader("/tmp/test.img")
        container = APFSContainer(reader)
        
        assert container.reader == reader
        assert container.superblock is None
        assert container.volumes == {}
        
    def test_container_properties(self):
        """测试容器属性"""
        from src.core.apfs.container import APFSContainer
        from src.core.apfs.reader import APFSReader
        
        reader = APFSReader("/tmp/test.img")
        container = APFSContainer(reader)
        
        # 默认值
        assert container.block_size == 4096
        assert container.block_count == 0
        assert container.uuid == b'\x00' * 16
        assert container.volume_count == 0


class TestAPFSVolume:
    """测试 APFS 卷"""
    
    def test_volume_init(self):
        """测试卷初始化"""
        from src.core.apfs.volume import APFSVolume
        from src.core.apfs.reader import APFSReader
        from src.core.apfs.structures import APFSSuperblock
        
        reader = APFSReader("/tmp/test.img")
        
        # 创建模拟的卷超级块
        volume = APFSSuperblock(
            header=None,
            magic=APFS_MAGIC,
            fs_index=0,
            features=0,
            read_only_features=0,
            incompatible_features=0,
            uuid=b'\x00' * 16,
            timestamp=0,
            version=1,
            minor_version=0,
            omap_oid=0,
            root_tree_oid=0,
            extentref_tree_oid=0,
            snap_meta_tree_oid=0,
            next_obj_id=0,
            next_xid=0,
            num_snapshots=0,
            total_blocks_used=0,
            block_size=4096,
            name="TestVolume"
        )
        
        apfs_volume = APFSVolume(reader, volume)
        
        assert apfs_volume.name == "TestVolume"
        assert apfs_volume.uuid == b'\x00' * 16
        assert apfs_volume.block_size == 4096
        assert apfs_volume.total_blocks_used == 0
        assert apfs_volume.version == (1, 0)


class TestAPFSIntegration:
    """APFS 集成测试"""
    
    def test_struct_sizes(self):
        """测试结构体大小"""
        from src.core.apfs.structures import (
            APFSHeader, NXSuperblock, APFSSuperblock,
            BTNodeDescriptor, BTInfo, JKey, JInode,
            OMAP, OMAPEntry
        )
        
        # 验证结构体大小
        assert APFSHeader.STRUCT_SIZE == 32  # 8+8+8+4+4
        assert JKey.STRUCT_SIZE == 10  # 8+2
        assert BTNodeDescriptor.STRUCT_SIZE == 20  # 2+2+8+8
        assert BTInfo.STRUCT_SIZE == 16  # 4+4+4+4
        assert OMAPEntry.STRUCT_SIZE == 24  # 8+8+8
        
    def test_enum_values(self):
        """测试枚举值"""
        from src.core.apfs.structures import ObjType, ObjFlags, BTNodeFlags
        
        # 对象类型
        assert ObjType.NX_SUPERBLOCK == 0x0001
        assert ObjType.B_TREE == 0x0002
        assert ObjType.FS == 0x0008
        
        # 对象标志
        assert ObjFlags.VIRTUAL == 0x0000
        assert ObjFlags.EPHEMERAL == 0x8000
        assert ObjFlags.PHYSICAL == 0x4000
        
        # B-tree 节点标志
        assert BTNodeFlags.NODE_FIXED_KV_SIZE == 0x0001
        assert BTNodeFlags.NODE_LEAF == 0x0001
        assert BTNodeFlags.NODE_INDEX == 0x0002


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
