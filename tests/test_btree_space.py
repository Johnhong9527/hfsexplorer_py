#!/usr/bin/env python3
"""
APFS B-tree 和空间管理测试

测试完整的 B-tree 操作和空间管理功能。
"""

import pytest
import sys
import os
import struct
import tempfile

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestBTreeManager:
    """测试 B-tree 管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.apfs.btree import BTreeManager, BTNode, BTHeaderRec
        assert BTreeManager is not None
        assert BTNode is not None
        assert BTHeaderRec is not None
    
    def test_jkey(self):
        """测试 JKey"""
        from src.core.apfs.btree import JKey
        
        # 创建键
        key1 = JKey(obj_id=100, type=1, num=0)
        key2 = JKey(obj_id=200, type=1, num=0)
        key3 = JKey(obj_id=100, type=2, num=0)
        
        # 序列化
        data = key1.to_bytes()
        assert len(data) == 8
        
        # 反序列化
        key1_parsed = JKey.from_bytes(data)
        assert key1_parsed.obj_id == 100
        assert key1_parsed.type == 1
        assert key1_parsed.num == 0
        
        # 比较
        assert key1 < key2
        assert key1 < key3
        assert not (key2 < key1)
    
    def test_bt_node_descriptor(self):
        """测试节点描述符"""
        from src.core.apfs.btree import BTNodeDescriptor, NodeType
        
        desc = BTNodeDescriptor(
            next=0,
            prev=0,
            type=NodeType.LEAF,
            flags=0,
            num_keys=5
        )
        
        # 序列化
        data = desc.to_bytes()
        assert len(data) == 20
        
        # 反序列化
        desc2 = BTNodeDescriptor.from_bytes(data)
        assert desc2.type == NodeType.LEAF
        assert desc2.num_keys == 5
    
    def test_bt_node(self):
        """测试节点"""
        from src.core.apfs.btree import BTNode, BTNodeDescriptor, NodeType, JKey
        
        # 创建节点
        node = BTNode(
            descriptor=BTNodeDescriptor(
                next=0,
                prev=0,
                type=NodeType.LEAF,
                flags=0,
                num_keys=2
            ),
            keys=[JKey(1, 1, 0).to_bytes(), JKey(2, 1, 0).to_bytes()],
            values=[b'value1', b'value2']
        )
        
        assert node.is_leaf == True
        assert node.num_keys == 2
    
    def test_bt_header_rec(self):
        """测试头部记录"""
        from src.core.apfs.btree import BTHeaderRec
        
        header = BTHeaderRec(
            tree_type=0,
            tree_height=1,
            num_entries=10,
            max_key_size=256,
            max_val_size=4096,
            root_oid=100,
            first_leaf_oid=100,
            last_leaf_oid=100,
            node_size=4096,
            max_inline_val_size=3800,
            num_free_nodes=0,
            embedded_root_oid=0
        )
        
        # 序列化
        data = header.to_bytes()
        assert len(data) == 72  # 实际大小
        
        # 反序列化
        header2 = BTHeaderRec.from_bytes(data)
        assert header2.num_entries == 10
        assert header2.root_oid == 100
    
    def test_create_btree(self):
        """测试创建 B-tree"""
        from src.core.apfs.btree import create_btree
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 创建足够大的文件
            f.write(b'\x00' * (1024 * 1024))  # 1MB
            f.flush()
            
            try:
                btree = create_btree(f.name, 4096)
                
                assert btree._header is not None
                assert btree._header.num_entries == 0
                assert btree._header.tree_height == 1
                
                btree.close()
            finally:
                os.unlink(f.name)
    
    def test_insert_and_search(self):
        """测试插入和搜索"""
        from src.core.apfs.btree import create_btree, JKey
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                btree = create_btree(f.name, 4096)
                
                # 插入键值对
                key1 = JKey(100, 1, 0).to_bytes()
                key2 = JKey(200, 1, 0).to_bytes()
                key3 = JKey(300, 1, 0).to_bytes()
                
                btree.insert(key1, b'value1')
                btree.insert(key2, b'value2')
                btree.insert(key3, b'value3')
                
                # 搜索
                assert btree.search(key1) == b'value1'
                assert btree.search(key2) == b'value2'
                assert btree.search(key3) == b'value3'
                
                # 搜索不存在的键
                key4 = JKey(400, 1, 0).to_bytes()
                assert btree.search(key4) is None
                
                btree.close()
            finally:
                os.unlink(f.name)
    
    def test_insert_many(self):
        """测试大量插入"""
        from src.core.apfs.btree import create_btree, JKey
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (10 * 1024 * 1024))  # 10MB
            f.flush()
            
            try:
                btree = create_btree(f.name, 4096)
                
                # 插入 100 个键值对
                for i in range(100):
                    key = JKey(i, 1, 0).to_bytes()
                    value = f'value{i}'.encode()
                    btree.insert(key, value)
                
                # 验证所有键值对
                for i in range(100):
                    key = JKey(i, 1, 0).to_bytes()
                    expected = f'value{i}'.encode()
                    assert btree.search(key) == expected
                
                # 获取所有条目
                entries = btree.get_all_entries()
                assert len(entries) == 100
                
                btree.close()
            finally:
                os.unlink(f.name)
    
    def test_delete(self):
        """测试删除"""
        from src.core.apfs.btree import create_btree, JKey
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                btree = create_btree(f.name, 4096)
                
                # 插入
                key1 = JKey(100, 1, 0).to_bytes()
                key2 = JKey(200, 1, 0).to_bytes()
                
                btree.insert(key1, b'value1')
                btree.insert(key2, b'value2')
                
                # 删除
                assert btree.delete(key1) == True
                assert btree.search(key1) is None
                assert btree.search(key2) == b'value2'
                
                btree.close()
            finally:
                os.unlink(f.name)
    
    def test_update(self):
        """测试更新"""
        from src.core.apfs.btree import create_btree, JKey
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                btree = create_btree(f.name, 4096)
                
                # 插入
                key = JKey(100, 1, 0).to_bytes()
                btree.insert(key, b'value1')
                
                # 更新
                assert btree.update(key, b'value2') == True
                assert btree.search(key) == b'value2'
                
                btree.close()
            finally:
                os.unlink(f.name)


class TestSpaceManager:
    """测试空间管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.apfs.space_manager import SpaceManager, BitmapBlock
        assert SpaceManager is not None
        assert BitmapBlock is not None
    
    def test_bitmap_block(self):
        """测试位图块"""
        from src.core.apfs.space_manager import BitmapBlock
        
        bitmap = BitmapBlock(
            block_num=1,
            data=bytearray(4096)
        )
        
        # 测试分配
        assert bitmap.is_allocated(0) == False
        bitmap.allocate(0)
        assert bitmap.is_allocated(0) == True
        
        # 测试释放
        bitmap.free(0)
        assert bitmap.is_allocated(0) == False
        
        # 测试查找空闲块
        free_blocks = bitmap.find_free_blocks(5, 0)
        assert len(free_blocks) == 5
        assert free_blocks == [0, 1, 2, 3, 4]
    
    def test_space_manager_header(self):
        """测试空间管理器头部"""
        from src.core.apfs.space_manager import SpaceManagerHeader
        
        header = SpaceManagerHeader(
            block_size=4096,
            total_blocks=1000,
            free_blocks=900,
            bitmap_blocks=1,
            first_bitmap_block=1
        )
        
        # 序列化
        data = header.to_bytes()
        assert len(data) == 32
        
        # 反序列化
        header2 = SpaceManagerHeader.from_bytes(data)
        assert header2.block_size == 4096
        assert header2.total_blocks == 1000
        assert header2.free_blocks == 900
    
    def test_create_space_manager(self):
        """测试创建空间管理器"""
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))  # 1MB
            f.flush()
            
            try:
                manager = create_space_manager(f.name, 256, 4096)
                
                assert manager._header is not None
                assert manager._header.total_blocks == 256
                assert manager._header.free_blocks > 0
                
                manager.close()
            finally:
                os.unlink(f.name)
    
    def test_allocate_block(self):
        """测试分配块"""
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                manager = create_space_manager(f.name, 256, 4096)
                
                # 分配块
                block1 = manager.allocate_block()
                block2 = manager.allocate_block()
                block3 = manager.allocate_block()
                
                assert block1 is not None
                assert block2 is not None
                assert block3 is not None
                assert block1 != block2
                assert block2 != block3
                
                # 检查状态
                assert manager.is_allocated(block1) == True
                assert manager.is_allocated(block2) == True
                assert manager.is_allocated(block3) == True
                
                manager.close()
            finally:
                os.unlink(f.name)
    
    def test_allocate_multiple_blocks(self):
        """测试分配多个块"""
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                manager = create_space_manager(f.name, 256, 4096)
                
                # 分配多个块
                blocks = manager.allocate_blocks(10)
                
                assert len(blocks) == 10
                assert len(set(blocks)) == 10  # 所有块都不同
                
                manager.close()
            finally:
                os.unlink(f.name)
    
    def test_free_block(self):
        """测试释放块"""
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                manager = create_space_manager(f.name, 256, 4096)
                
                # 分配块
                block = manager.allocate_block()
                assert block is not None
                
                # 释放块
                free_blocks_before = manager.get_free_blocks()
                manager.free_block(block)
                free_blocks_after = manager.get_free_blocks()
                
                assert free_blocks_after == free_blocks_before + 1
                assert manager.is_allocated(block) == False
                
                manager.close()
            finally:
                os.unlink(f.name)
    
    def test_get_info(self):
        """测试获取信息"""
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            try:
                manager = create_space_manager(f.name, 256, 4096)
                
                info = manager.get_info()
                
                assert 'block_size' in info
                assert 'total_blocks' in info
                assert 'free_blocks' in info
                assert 'allocated_blocks' in info
                assert info['block_size'] == 4096
                assert info['total_blocks'] == 256
                
                manager.close()
            finally:
                os.unlink(f.name)


class TestBTreeWithSpaceManager:
    """测试 B-tree 和空间管理器集成"""
    
    def test_integration(self):
        """测试集成"""
        from src.core.apfs.btree import create_btree, JKey
        from src.core.apfs.space_manager import create_space_manager
        
        with tempfile.NamedTemporaryFile(delete=False) as btree_file:
            btree_file.write(b'\x00' * (10 * 1024 * 1024))  # 10MB
            btree_file.flush()
            
            with tempfile.NamedTemporaryFile(delete=False) as space_file:
                space_file.write(b'\x00' * (1024 * 1024))  # 1MB
                space_file.flush()
                
                try:
                    # 创建 B-tree
                    btree = create_btree(btree_file.name, 4096)
                    
                    # 创建空间管理器
                    space_mgr = create_space_manager(space_file.name, 256, 4096)
                    
                    # 插入一些数据
                    for i in range(50):
                        # 分配块
                        block = space_mgr.allocate_block()
                        assert block is not None
                        
                        # 插入到 B-tree
                        key = JKey(i, 1, 0).to_bytes()
                        value = f'block_{block}'.encode()
                        btree.insert(key, value)
                    
                    # 验证
                    for i in range(50):
                        key = JKey(i, 1, 0).to_bytes()
                        assert btree.search(key) is not None
                    
                    # 获取信息
                    btree_info = btree.get_info()
                    space_info = space_mgr.get_info()
                    
                    assert btree_info['num_entries'] == 50
                    assert space_info['allocated_blocks'] > 0
                    
                    btree.close()
                    space_mgr.close()
                    
                finally:
                    os.unlink(btree_file.name)
                    os.unlink(space_file.name)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
