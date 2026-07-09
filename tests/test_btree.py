"""
HFS+ B-tree 模块测试
"""

import pytest
import struct
from io import BytesIO

from src.core.hfs.btree import (
    BTNodeDescriptor,
    BTHeaderRec,
    BTreeNode,
    BTIndexRecord,
    BTLeafRecord,
    BTreeFile,
    HFSPlusCatalogKey,
    HFSPlusCatalogFolder,
    HFSPlusCatalogFile,
    CatalogRecordType,
    CatalogBTree,
)
from src.core.hfs.constants import BTreeNodeKind


class TestBTNodeDescriptor:
    """BTNodeDescriptor 测试"""
    
    def test_create_leaf_node(self):
        """测试创建叶节点描述符"""
        desc = BTNodeDescriptor(
            fLink=10,
            bLink=5,
            kind=-1,
            height=1,
            numRecords=3,
            reserved=0
        )
        assert desc.fLink == 10
        assert desc.bLink == 5
        assert desc.kind == -1
        assert desc.height == 1
        assert desc.numRecords == 3
        assert desc.node_type == BTreeNodeKind.LEAF
        assert desc.is_leaf is True
        assert desc.is_index is False
    
    def test_create_index_node(self):
        """测试创建索引节点描述符"""
        desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=0,
            height=2,
            numRecords=5,
            reserved=0
        )
        assert desc.node_type == BTreeNodeKind.INDEX
        assert desc.is_index is True
    
    def test_create_header_node(self):
        """测试创建头节点描述符"""
        desc = BTNodeDescriptor(
            fLink=0,
            bLink=0,
            kind=1,
            height=0,
            numRecords=3,
            reserved=0
        )
        assert desc.node_type == BTreeNodeKind.HEADER
        assert desc.is_header is True
    
    def test_to_bytes(self):
        """测试转换为字节"""
        desc = BTNodeDescriptor(
            fLink=10,
            bLink=5,
            kind=-1,
            height=1,
            numRecords=3,
            reserved=0
        )
        data = desc.to_bytes()
        assert len(data) == 14
        
        # 验证字节内容
        fLink, bLink, kind_raw, height, numRecords, reserved = struct.unpack_from(
            '>II Bb HH', data
        )
        assert fLink == 10
        assert bLink == 5
        assert kind_raw == 255  # -1 作为无符号字节
        assert height == 1
        assert numRecords == 3
    
    def test_from_bytes(self):
        """测试从字节解析"""
        # 构造测试数据
        data = struct.pack('>II Bb HH', 10, 5, 255, 1, 3, 0)
        
        desc = BTNodeDescriptor.from_bytes(data)
        assert desc.fLink == 10
        assert desc.bLink == 5
        assert desc.kind == -1
        assert desc.height == 1
        assert desc.numRecords == 3
        assert desc.is_leaf is True
    
    def test_from_bytes_with_offset(self):
        """测试从带偏移量的字节解析"""
        prefix = b'\x00' * 10
        data = prefix + struct.pack('>II Bb HH', 10, 5, 0, 2, 5, 0)
        
        desc = BTNodeDescriptor.from_bytes(data, offset=10)
        assert desc.fLink == 10
        assert desc.is_index is True
    
    def test_from_bytes_insufficient_data(self):
        """测试数据不足时的错误处理"""
        with pytest.raises(ValueError):
            BTNodeDescriptor.from_bytes(b'\x00' * 13)


class TestBTHeaderRec:
    """BTHeaderRec 测试"""
    
    def test_create(self):
        """测试创建头记录"""
        header = BTHeaderRec(
            treeDepth=2,
            rootNode=10,
            leafRecords=100,
            firstLeafNode=5,
            lastLeafNode=15,
            nodeSize=4096,
            maxKeyLength=518,
            totalNodes=50,
            freeNodes=10,
            reserved1=0,
            clumpSize=65536,
            btreeType=0,
            keyCompareType=0xCF,
            attributes=0
        )
        assert header.treeDepth == 2
        assert header.rootNode == 10
        assert header.leafRecords == 100
        assert header.nodeSize == 4096
        assert header.is_case_sensitive is False
    
    def test_attributes(self):
        """测试属性标志"""
        # 大键标志
        header = BTHeaderRec(
            treeDepth=1, rootNode=1, leafRecords=10,
            firstLeafNode=1, lastLeafNode=1, nodeSize=4096,
            maxKeyLength=518, totalNodes=10, freeNodes=0,
            reserved1=0, clumpSize=0, btreeType=0,
            keyCompareType=0xCF, attributes=0x02
        )
        assert header.big_keys is True
        assert header.variable_index_keys is False
        
        # 变长索引键标志
        header.attributes = 0x04
        assert header.variable_index_keys is True
        
        # 区分大小写
        header.keyCompareType = 0xBC
        assert header.is_case_sensitive is True
    
    def test_to_bytes(self):
        """测试转换为字节"""
        header = BTHeaderRec(
            treeDepth=2, rootNode=10, leafRecords=100,
            firstLeafNode=5, lastLeafNode=15, nodeSize=4096,
            maxKeyLength=518, totalNodes=50, freeNodes=10,
            reserved1=0, clumpSize=65536, btreeType=0,
            keyCompareType=0xCF, attributes=0
        )
        data = header.to_bytes()
        assert len(data) == 106
    
    def test_from_bytes(self):
        """测试从字节解析"""
        # 构造测试数据
        data = struct.pack(
            '>H IIII HH II H I BB I',
            2, 10, 100, 5, 15, 4096, 518, 50, 10, 0, 65536, 0, 0xCF, 0
        )
        data += b'\x00' * 64  # 保留字段
        
        header = BTHeaderRec.from_bytes(data)
        assert header.treeDepth == 2
        assert header.rootNode == 10
        assert header.leafRecords == 100
        assert header.nodeSize == 4096
        assert header.keyCompareType == 0xCF


class TestBTreeNode:
    """BTreeNode 测试"""
    
    def _create_test_node(self, node_type=BTreeNodeKind.LEAF, num_records=2):
        """创建测试节点"""
        node_size = 256
        
        # 节点描述符 (14 bytes)
        # 使用 kind 值：-1=叶(0xFF), 0=索引, 1=头, 2=位图
        kind_value = 0xFF if node_type == BTreeNodeKind.LEAF else (
            1 if node_type == BTreeNodeKind.HEADER else 0
        )
        desc_data = struct.pack(
            '>II Bb HH',
            0,  # fLink
            0,  # bLink
            kind_value,  # kind (无符号字节)
            1 if node_type == BTreeNodeKind.LEAF else 0,
            num_records,
            0
        )
        
        # 记录数据
        records_data = b''
        offsets = []
        current_offset = 14  # 跳过节点描述符
        
        for i in range(num_records):
            offsets.append(current_offset)
            # 简单的测试记录：2字节长度 + 数据
            record_data = struct.pack('>H', i) + f'record_{i}'.encode()
            records_data += record_data
            current_offset += len(record_data)
        
        # 空闲空间起始偏移
        offsets.append(current_offset)
        
        # 填充到节点大小
        padding = node_size - 14 - len(records_data) - (num_records + 1) * 2
        if padding > 0:
            records_data += b'\x00' * padding
        
        # 偏移表（从末尾反向存储）
        # 根据 from_bytes 的实现，偏移表存储在节点末尾，反向排列
        # offsets[0] 存储在 node_size - (num_records+1)*2 的位置
        # offsets[num_records] 存储在 node_size - 2 的位置
        offset_table = b''
        for i in range(num_records + 1):
            # 计算存储位置
            pos = node_size - (num_records + 1 - i) * 2
            offset_table += struct.pack('>H', offsets[i])
        
        return desc_data + records_data + offset_table
    
    def test_from_bytes(self):
        """测试从字节解析"""
        data = self._create_test_node()
        node = BTreeNode.from_bytes(data)
        
        assert node.descriptor.is_leaf is True
        assert node.num_records == 2
        assert len(node.offsets) == 3  # num_records + 1
    
    def test_get_record_data(self):
        """测试获取记录数据"""
        data = self._create_test_node()
        node = BTreeNode.from_bytes(data)
        
        # 验证记录数据
        record_0 = node.get_record_data(0)
        record_1 = node.get_record_data(1)
        
        # 记录应该包含键数据
        assert len(record_0) > 0 or node.num_records == 0
        assert len(record_1) > 0 or node.num_records < 2


class TestBTreeFile:
    """BTreeFile 测试"""
    
    def _create_test_btree(self, num_nodes=3):
        """创建测试 B-tree"""
        node_size = 256
        
        # 头节点 (节点 0)
        header_node = self._create_header_node(node_size)
        
        # 其他节点
        other_nodes = b''
        for i in range(1, num_nodes):
            other_nodes += self._create_leaf_node(node_size, i)
        
        return header_node + other_nodes
    
    def _create_header_node(self, node_size):
        """创建头节点"""
        # 节点描述符
        desc = struct.pack('>II Bb HH', 0, 0, 1, 0, 3, 0)
        
        # 头记录
        header_rec = struct.pack(
            '>H IIII HH II H I BB I',
            2,  # treeDepth
            1,  # rootNode
            10,  # leafRecords
            1,  # firstLeafNode
            2,  # lastLeafNode
            node_size,  # nodeSize
            518,  # maxKeyLength
            3,  # totalNodes
            0,  # freeNodes
            0,  # reserved1
            0,  # clumpSize
            0,  # btreeType
            0xCF,  # keyCompareType
            0  # attributes
        )
        header_rec += b'\x00' * 64  # 保留字段
        
        # 偏移表
        offset_table = struct.pack('>HHH', 120, 14, 14 + 106)
        
        # 填充
        padding = node_size - 14 - 106 - 6
        return desc + header_rec + b'\x00' * padding + offset_table
    
    def _create_leaf_node(self, node_size, node_number):
        """创建叶节点"""
        # 节点描述符
        desc = struct.pack(
            '>II Bb HH',
            node_number + 1 if node_number < 2 else 0,  # fLink
            node_number - 1,  # bLink
            0xFF,  # kind (leaf, 无符号字节)
            1,  # height
            2,  # numRecords
            0  # reserved
        )
        
        # 记录数据
        record1 = struct.pack('>H', 4) + b'test'
        record2 = struct.pack('>H', 5) + b'hello'
        
        # 偏移表
        offset1 = 14
        offset2 = offset1 + len(record1)
        free_space = offset2 + len(record2)
        
        offset_table = struct.pack('>HHH', free_space, offset1, offset2)
        
        # 填充
        padding = node_size - 14 - len(record1) - len(record2) - 6
        return desc + record1 + record2 + b'\x00' * padding + offset_table
    
    def test_read_header(self):
        """测试读取头记录"""
        data = self._create_test_btree()
        stream = BytesIO(data)
        
        # 使用 256 字节的节点大小（与测试数据匹配）
        btree = BTreeFile(stream, node_size=256)
        header = btree.header
        
        assert header.treeDepth == 2
        assert header.rootNode == 1
        assert header.leafRecords == 10
        assert header.nodeSize == 256
    
    def test_get_node(self):
        """测试获取节点"""
        data = self._create_test_btree()
        stream = BytesIO(data)
        
        # 使用 256 字节的节点大小（与测试数据匹配）
        btree = BTreeFile(stream, node_size=256)
        node = btree.get_node(1)
        
        assert node.descriptor.is_leaf is True
        assert node.num_records == 2


class TestHFSPlusCatalogKey:
    """HFSPlusCatalogKey 测试"""
    
    def test_create(self):
        """测试创建 Catalog 键"""
        key = HFSPlusCatalogKey(
            key_length=16,  # 4 (parentID) + 2 (HFSUniStr255.length) + 8*2 (chars)
            parent_id=2,
            node_name='test.txt'
        )
        assert key.key_length == 16
        assert key.parent_id == 2
        assert key.node_name == 'test.txt'
        assert key.occupied_size == 18  # 2 + 16
    
    def test_from_bytes(self):
        """测试从字节解析
        
        按 TN1150 规范构造数据：
        - keyLength (UInt16): 包含 parentID(4) + HFSUniStr255(2 + 2*numChars)
        - parentID (UInt32): 父文件夹 CNID
        - nodeName (HFSUniStr255): UInt16 length + UInt16[] unicode
        """
        name = 'test.txt'.encode('utf-16-be')
        # keyLength = 4 (parentID) + 2 (HFSUniStr255.length) + len(name) (unicode chars)
        key_length = 4 + 2 + len(name)
        data = struct.pack('>HI', key_length, 2) + struct.pack('>H', len(name) // 2) + name
        
        key = HFSPlusCatalogKey.from_bytes(data)
        assert key.key_length == key_length
        assert key.parent_id == 2
        assert key.node_name == 'test.txt'


class TestCatalogRecordTypes:
    """Catalog 记录类型测试"""
    
    def test_record_type_constants(self):
        """测试记录类型常量"""
        assert CatalogRecordType.FOLDER == 0x0001
        assert CatalogRecordType.FILE == 0x0002
        assert CatalogRecordType.FOLDER_THREAD == 0x0003
        assert CatalogRecordType.FILE_THREAD == 0x0004


if __name__ == '__main__':
    pytest.main([__file__])