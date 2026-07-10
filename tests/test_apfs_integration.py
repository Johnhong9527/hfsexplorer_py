#!/usr/bin/env python3
"""
APFS 集成测试

测试 APFS 模块的集成功能
"""

import struct
import tempfile
import os
from pathlib import Path

import pytest

from src.core.apfs.structures import (
    NX_MAGIC, APFS_MAGIC, NXSuperblock, APFSSuperblock,
    BTNodeDescriptor, BTInfo, JKey, JInode, JDirEntry,
    OMAP, OMAPEntry, APFSHeader
)


class TestAPFSIntegration:
    """APFS 集成测试"""
    
    def create_test_image(self, size: int = 4096 * 100) -> str:
        """创建测试用的 APFS 镜像"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.img') as f:
            # 写入空白数据
            f.write(b'\x00' * size)
            return f.name
            
    def test_apfs_header_roundtrip(self):
        """测试 APFS 头部序列化和反序列化"""
        # 创建测试数据
        checksum = 123456789
        oid = 100
        xid = 200
        obj_type = 1
        subtype = 2
        
        # 创建头部
        header = APFSHeader(
            checksum=checksum,
            oid=oid,
            xid=xid,
            type=obj_type,
            subtype=subtype
        )
        
        # 序列化
        data = header.to_bytes()
        
        # 反序列化
        header2 = APFSHeader.from_bytes(data)
        
        # 验证
        assert header2.checksum == checksum
        assert header2.oid == oid
        assert header2.xid == xid
        assert header2.type == obj_type
        assert header2.subtype == subtype
        
    def test_nx_superblock_parsing(self):
        """测试容器超级块解析"""
        # 创建测试数据
        block_size = 4096
        block_count = 1000
        features = 0
        read_only_features = 0
        incompatible_features = 0
        uuid = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
        next_xid = 100
        next_oid = 200
        spaceman_oid = 300
        omap_oid = 400
        reaper_oid = 500
        test_type = 0
        max_volumes = 10
        volume_oids = [0] * 100
        volume_oids[0] = 600
        volume_oids[1] = 700
        nx_desc_count = 0
        nx_desc_blocks = 0
        nx_data_count = 0
        nx_data_blocks = 0
        nx_latest_xid = 100
        
        # 创建头部
        header = APFSHeader(
            checksum=0,
            oid=1,
            xid=100,
            type=1,  # NX_SUPERBLOCK
            subtype=0
        )
        
        # 手动构建数据
        data = bytearray(4096)
        offset = 0
        
        # 头部
        struct.pack_into('<QQQII', data, offset,
                        header.checksum, header.oid, header.xid,
                        header.type, header.subtype)
        offset += APFSHeader.STRUCT_SIZE
        
        # 魔数
        struct.pack_into('<I', data, offset, int.from_bytes(NX_MAGIC, 'little'))
        offset += 4
        
        # 其他字段
        # 计算实际的偏移量
        # 头部: 32 字节
        # 魔数: 4 字节
        # 块大小: 4 字节
        # 总块数: 8 字节
        # 特性: 8 字节
        # 只读特性: 8 字节
        # 不兼容特性: 8 字节
        # UUID: 16 字节
        # next_xid: 8 字节
        # next_oid: 8 字节
        # spaceman_oid: 8 字节
        # omap_oid: 8 字节
        # reaper_oid: 8 字节
        # test_type: 4 字节
        # max_volumes: 4 字节
        # volume_oids: 800 字节 (100 * 8)
        # nx_desc_count: 4 字节
        # nx_desc_blocks: 4 字节
        # nx_data_count: 4 字节
        # nx_data_blocks: 4 字节
        # nx_latest_xid: 8 字节
        
        # 手动写入各个字段
        struct.pack_into('<I', data, offset, block_size)
        offset += 4
        struct.pack_into('<Q', data, offset, block_count)
        offset += 8
        struct.pack_into('<Q', data, offset, features)
        offset += 8
        struct.pack_into('<Q', data, offset, read_only_features)
        offset += 8
        struct.pack_into('<Q', data, offset, incompatible_features)
        offset += 8
        struct.pack_into('<16s', data, offset, uuid)
        offset += 16
        struct.pack_into('<Q', data, offset, next_xid)
        offset += 8
        struct.pack_into('<Q', data, offset, next_oid)
        offset += 8
        struct.pack_into('<Q', data, offset, spaceman_oid)
        offset += 8
        struct.pack_into('<Q', data, offset, omap_oid)
        offset += 8
        struct.pack_into('<Q', data, offset, reaper_oid)
        offset += 8
        struct.pack_into('<I', data, offset, test_type)
        offset += 4
        struct.pack_into('<I', data, offset, max_volumes)
        offset += 4
        
        # 写入 volume_oids 数组
        for i, oid in enumerate(volume_oids):
            struct.pack_into('<Q', data, offset + i * 8, oid)
        offset += 100 * 8
        
        struct.pack_into('<I', data, offset, nx_desc_count)
        offset += 4
        struct.pack_into('<I', data, offset, nx_desc_blocks)
        offset += 4
        struct.pack_into('<I', data, offset, nx_data_count)
        offset += 4
        struct.pack_into('<I', data, offset, nx_data_blocks)
        offset += 4
        struct.pack_into('<Q', data, offset, nx_latest_xid)
        offset += 8
        
        # 解析
        superblock = NXSuperblock.from_bytes(bytes(data))
        
        # 验证
        assert superblock.magic == NX_MAGIC
        assert superblock.block_size == block_size
        assert superblock.block_count == block_count
        assert superblock.uuid == uuid
        assert superblock.next_xid == next_xid
        assert superblock.next_oid == next_oid
        assert superblock.spaceman_oid == spaceman_oid
        assert superblock.omap_oid == omap_oid
        assert superblock.max_volumes == max_volumes
        assert superblock.volume_oids[0] == volume_oids[0]
        assert superblock.volume_oids[1] == volume_oids[1]
        
    def test_apfs_superblock_parsing(self):
        """测试卷超级块解析"""
        # 创建测试数据
        fs_index = 0
        features = 0
        read_only_features = 0
        incompatible_features = 0
        uuid = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
        timestamp = 1000000000
        version = 1
        minor_version = 0
        omap_oid = 100
        root_tree_oid = 200
        extentref_tree_oid = 300
        snap_meta_tree_oid = 400
        next_obj_id = 500
        next_xid = 600
        num_snapshots = 0
        total_blocks_used = 1000
        block_size = 4096
        name = "TestVolume"
        
        # 创建头部
        header = APFSHeader(
            checksum=0,
            oid=2,
            xid=100,
            type=8,  # FS
            subtype=0
        )
        
        # 手动构建数据
        data = bytearray(4096)
        offset = 0
        
        # 头部
        struct.pack_into('<QQQII', data, offset,
                        header.checksum, header.oid, header.xid,
                        header.type, header.subtype)
        offset += APFSHeader.STRUCT_SIZE
        
        # 魔数
        struct.pack_into('<I', data, offset, int.from_bytes(APFS_MAGIC, 'little'))
        offset += 4
        
        # 其他字段
        name_bytes = name.encode('utf-8').ljust(256, b'\x00')
        struct.pack_into('<IQQQ16sQIIQQQQQQIQI256s', data, offset,
                        fs_index, features, read_only_features,
                        incompatible_features, uuid, timestamp,
                        version, minor_version, omap_oid,
                        root_tree_oid, extentref_tree_oid,
                        snap_meta_tree_oid, next_obj_id, next_xid,
                        num_snapshots, total_blocks_used, block_size,
                        name_bytes)
        
        # 解析
        superblock = APFSSuperblock.from_bytes(bytes(data))
        
        # 验证
        assert superblock.magic == APFS_MAGIC
        assert superblock.fs_index == fs_index
        assert superblock.uuid == uuid
        assert superblock.timestamp == timestamp
        assert superblock.version == version
        assert superblock.minor_version == minor_version
        assert superblock.omap_oid == omap_oid
        assert superblock.root_tree_oid == root_tree_oid
        assert superblock.next_obj_id == next_obj_id
        assert superblock.next_xid == next_xid
        assert superblock.total_blocks_used == total_blocks_used
        assert superblock.block_size == block_size
        assert superblock.name == name
        
    def test_jkey_roundtrip(self):
        """测试 JKey 序列化和反序列化"""
        obj_id = 12345
        obj_type = 1
        
        # 创建 JKey
        jkey = JKey(obj_id=obj_id, type=obj_type)
        
        # 序列化
        data = struct.pack('<QH', jkey.obj_id, jkey.type)
        
        # 反序列化
        jkey2 = JKey.from_bytes(data)
        
        # 验证
        assert jkey2.obj_id == obj_id
        assert jkey2.type == obj_type
        
    def test_jinode_roundtrip(self):
        """测试 JInode 序列化和反序列化"""
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
        mode = 0o100644
        pad1 = 0
        pad2 = 0
        bsd_flags = 0
        rdev = 0
        nsec = 0
        
        # 创建 JInode
        inode = JInode(
            parent_id=parent_id,
            private_id=private_id,
            create_time=create_time,
            mod_time=mod_time,
            change_time=change_time,
            access_time=access_time,
            internal_flags=internal_flags,
            nchildren=nchildren,
            nlink=nlink,
            uid=uid,
            gid=gid,
            mode=mode,
            pad1=pad1,
            pad2=pad2,
            bsd_flags=bsd_flags,
            rdev=rdev,
            nsec=nsec
        )
        
        # 序列化
        data = struct.pack(
            '<QQQQQQQiiIIIHHIIQ',
            inode.parent_id, inode.private_id, inode.create_time,
            inode.mod_time, inode.change_time, inode.access_time,
            inode.internal_flags, inode.nchildren, inode.nlink,
            inode.uid, inode.gid, inode.mode, inode.pad1,
            inode.pad2, inode.bsd_flags, inode.rdev, inode.nsec
        )
        
        # 反序列化
        inode2 = JInode.from_bytes(data)
        
        # 验证
        assert inode2.parent_id == parent_id
        assert inode2.private_id == private_id
        assert inode2.create_time == create_time
        assert inode2.mod_time == mod_time
        assert inode2.nchildren == nchildren
        assert inode2.nlink == nlink
        assert inode2.uid == uid
        assert inode2.gid == gid
        assert inode2.mode == mode
        
    def test_bt_node_descriptor_roundtrip(self):
        """测试 BTNodeDescriptor 序列化和反序列化"""
        node_type = 1
        flags = 0
        left_sibling = 100
        right_sibling = 200
        
        # 创建节点描述符
        node_desc = BTNodeDescriptor(
            type=node_type,
            flags=flags,
            left_sibling=left_sibling,
            right_sibling=right_sibling
        )
        
        # 序列化
        data = struct.pack('<HHQQ', 
                          node_desc.type, node_desc.flags,
                          node_desc.left_sibling, node_desc.right_sibling)
        
        # 反序列化
        node_desc2 = BTNodeDescriptor.from_bytes(data)
        
        # 验证
        assert node_desc2.type == node_type
        assert node_desc2.flags == flags
        assert node_desc2.left_sibling == left_sibling
        assert node_desc2.right_sibling == right_sibling
        
    def test_btinfo_roundtrip(self):
        """测试 BTInfo 序列化和反序列化"""
        flags = 0
        node_size = 4096
        key_size = 16
        val_size = 32
        
        # 创建 BTInfo
        btinfo = BTInfo(
            flags=flags,
            node_size=node_size,
            key_size=key_size,
            val_size=val_size
        )
        
        # 序列化
        data = struct.pack('<IIII', 
                          btinfo.flags, btinfo.node_size,
                          btinfo.key_size, btinfo.val_size)
        
        # 反序列化
        btinfo2 = BTInfo.from_bytes(data)
        
        # 验证
        assert btinfo2.flags == flags
        assert btinfo2.node_size == node_size
        assert btinfo2.key_size == key_size
        assert btinfo2.val_size == val_size
        
    def test_omap_roundtrip(self):
        """测试 OMAP 序列化和反序列化"""
        flags = 0
        snap_count = 0
        tree_type = 2
        tree_oid = 100
        latest_snap_xid = 0
        
        # 创建 OMAP
        omap = OMAP(
            flags=flags,
            snap_count=snap_count,
            tree_type=tree_type,
            tree_oid=tree_oid,
            latest_snap_xid=latest_snap_xid
        )
        
        # 序列化
        data = struct.pack('<IIIIQ', 
                          omap.flags, omap.snap_count,
                          omap.tree_type, omap.tree_oid,
                          omap.latest_snap_xid)
        
        # 反序列化
        omap2 = OMAP.from_bytes(data)
        
        # 验证
        assert omap2.flags == flags
        assert omap2.snap_count == snap_count
        assert omap2.tree_type == tree_type
        assert omap2.tree_oid == tree_oid
        assert omap2.latest_snap_xid == latest_snap_xid
        
    def test_omap_entry_roundtrip(self):
        """测试 OMAPEntry 序列化和反序列化"""
        oid = 12345
        xid = 67890
        paddr = 100
        
        # 创建 OMAPEntry
        entry = OMAPEntry(
            oid=oid,
            xid=xid,
            paddr=paddr
        )
        
        # 序列化
        data = struct.pack('<QQQ', entry.oid, entry.xid, entry.paddr)
        
        # 反序列化
        entry2 = OMAPEntry.from_bytes(data)
        
        # 验证
        assert entry2.oid == oid
        assert entry2.xid == xid
        assert entry2.paddr == paddr
        
    def test_reader_with_invalid_file(self):
        """测试读取器处理无效文件"""
        from src.core.apfs.reader import APFSReader
        
        # 创建临时文件
        temp_path = self.create_test_image()
        
        try:
            # 测试打开无效文件
            with pytest.raises(ValueError, match="不是有效的 APFS 容器"):
                with APFSReader(temp_path) as reader:
                    pass
        finally:
            os.unlink(temp_path)
            
    def test_container_without_load(self):
        """测试未加载的容器"""
        from src.core.apfs.container import APFSContainer
        from src.core.apfs.reader import APFSReader
        
        reader = APFSReader("/tmp/test.img")
        container = APFSContainer(reader)
        
        # 测试未加载时的属性
        assert container.block_size == 4096
        assert container.block_count == 0
        assert container.uuid == b'\x00' * 16
        assert container.volume_count == 0
        
    def test_volume_without_data(self):
        """测试没有数据的卷"""
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
        
        # 测试属性
        assert apfs_volume.name == "TestVolume"
        assert apfs_volume.uuid == b'\x00' * 16
        assert apfs_volume.block_size == 4096
        assert apfs_volume.total_blocks_used == 0
        assert apfs_volume.version == (1, 0)
        
        # 测试获取信息
        info = apfs_volume.get_info()
        assert info['name'] == "TestVolume"
        assert info['block_size'] == 4096
        assert info['version'] == "1.0"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
