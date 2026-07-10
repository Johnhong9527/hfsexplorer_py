#!/usr/bin/env python3
"""
创建测试用的 APFS 镜像

用于测试 APFS 模块的基本功能
"""

import struct
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.apfs.structures import (
    NX_MAGIC, APFS_MAGIC, NXSuperblock, APFSSuperblock,
    BTNodeDescriptor, BTInfo, JKey, JInode, JDirEntry,
    OMAP, OMAPEntry, APFSHeader
)


def create_test_image(output_path: str, size: int = 4096 * 1000) -> None:
    """
    创建测试用的 APFS 镜像
    
    Args:
        output_path: 输出文件路径
        size: 镜像大小（字节）
    """
    print(f"创建测试 APFS 镜像: {output_path}")
    print(f"镜像大小: {size} 字节 ({size // 1024} KB)")
    
    # 创建空白镜像
    data = bytearray(size)
    
    # 写入容器超级块
    write_container_superblock(data, 0)
    
    # 写入卷超级块
    write_volume_superblock(data, 4096)
    
    # 写入对象映射
    write_object_map(data, 8192)
    
    # 写入根目录 B-tree
    write_root_directory_tree(data, 12288)
    
    # 写入文件数据
    write_test_files(data, 16384)
    
    # 保存镜像
    with open(output_path, 'wb') as f:
        f.write(data)
    
    print(f"镜像创建完成: {output_path}")
    

def write_container_superblock(data: bytearray, offset: int) -> None:
    """写入容器超级块"""
    print("写入容器超级块...")
    
    # 创建头部
    header = APFSHeader(
        checksum=0,  # 校验和将在后面计算
        oid=1,
        xid=100,
        type=1,  # NX_SUPERBLOCK
        subtype=0
    )
    
    # 写入头部
    struct.pack_into('<QQQII', data, offset,
                    header.checksum, header.oid, header.xid,
                    header.type, header.subtype)
    offset += APFSHeader.STRUCT_SIZE
    
    # 写入魔数
    struct.pack_into('<I', data, offset, int.from_bytes(NX_MAGIC, 'little'))
    offset += 4
    
    # 写入其他字段
    block_size = 4096
    block_count = len(data) // block_size
    features = 0
    read_only_features = 0
    incompatible_features = 0
    uuid = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
    next_xid = 100
    next_oid = 1000
    spaceman_oid = 100
    omap_oid = 200
    reaper_oid = 0
    test_type = 0
    max_volumes = 10
    volume_oids = [0] * 100
    volume_oids[0] = 300
    nx_desc_count = 0
    nx_desc_blocks = 0
    nx_data_count = 0
    nx_data_blocks = 0
    nx_latest_xid = 100
    
    # 写入字段
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
    

def write_volume_superblock(data: bytearray, offset: int) -> None:
    """写入卷超级块"""
    print("写入卷超级块...")
    
    # 创建头部
    header = APFSHeader(
        checksum=0,
        oid=300,
        xid=100,
        type=8,  # FS
        subtype=0
    )
    
    # 写入头部
    struct.pack_into('<QQQII', data, offset,
                    header.checksum, header.oid, header.xid,
                    header.type, header.subtype)
    offset += APFSHeader.STRUCT_SIZE
    
    # 写入魔数
    struct.pack_into('<I', data, offset, int.from_bytes(APFS_MAGIC, 'little'))
    offset += 4
    
    # 写入其他字段
    fs_index = 0
    features = 0
    read_only_features = 0
    incompatible_features = 0
    uuid = b'\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x20'
    timestamp = 1000000000
    version = 1
    minor_version = 0
    omap_oid = 200
    root_tree_oid = 400
    extentref_tree_oid = 0
    snap_meta_tree_oid = 0
    next_obj_id = 1000
    next_xid = 100
    num_snapshots = 0
    total_blocks_used = 100
    block_size = 4096
    name = "TestVolume"
    
    # 写入字段
    struct.pack_into('<I', data, offset, fs_index)
    offset += 4
    struct.pack_into('<Q', data, offset, features)
    offset += 8
    struct.pack_into('<Q', data, offset, read_only_features)
    offset += 8
    struct.pack_into('<Q', data, offset, incompatible_features)
    offset += 8
    struct.pack_into('<16s', data, offset, uuid)
    offset += 16
    struct.pack_into('<Q', data, offset, timestamp)
    offset += 8
    struct.pack_into('<I', data, offset, version)
    offset += 4
    struct.pack_into('<I', data, offset, minor_version)
    offset += 4
    struct.pack_into('<Q', data, offset, omap_oid)
    offset += 8
    struct.pack_into('<Q', data, offset, root_tree_oid)
    offset += 8
    struct.pack_into('<Q', data, offset, extentref_tree_oid)
    offset += 8
    struct.pack_into('<Q', data, offset, snap_meta_tree_oid)
    offset += 8
    struct.pack_into('<Q', data, offset, next_obj_id)
    offset += 8
    struct.pack_into('<Q', data, offset, next_xid)
    offset += 8
    struct.pack_into('<I', data, offset, num_snapshots)
    offset += 4
    struct.pack_into('<Q', data, offset, total_blocks_used)
    offset += 8
    struct.pack_into('<I', data, offset, block_size)
    offset += 4
    
    # 写入卷名
    name_bytes = name.encode('utf-8').ljust(256, b'\x00')
    struct.pack_into('<256s', data, offset, name_bytes)
    offset += 256
    

def write_object_map(data: bytearray, offset: int) -> None:
    """写入对象映射"""
    print("写入对象映射...")
    
    # 创建头部
    header = APFSHeader(
        checksum=0,
        oid=200,
        xid=100,
        type=6,  # OMAP
        subtype=0
    )
    
    # 写入头部
    struct.pack_into('<QQQII', data, offset,
                    header.checksum, header.oid, header.xid,
                    header.type, header.subtype)
    offset += APFSHeader.STRUCT_SIZE
    
    # 写入 OMAP 字段
    flags = 0
    snap_count = 0
    tree_type = 2
    tree_oid = 400  # 指向根目录树
    latest_snap_xid = 0
    
    struct.pack_into('<IIIIQ', data, offset,
                    flags, snap_count, tree_type, tree_oid, latest_snap_xid)
    offset += 20
    

def write_root_directory_tree(data: bytearray, offset: int) -> None:
    """写入根目录 B-tree"""
    print("写入根目录 B-tree...")
    
    # 创建节点描述符
    node_desc = BTNodeDescriptor(
        type=1,  # 叶节点
        flags=0,
        left_sibling=0,
        right_sibling=0
    )
    
    # 写入节点描述符
    struct.pack_into('<HHQQ', data, offset,
                    node_desc.type, node_desc.flags,
                    node_desc.left_sibling, node_desc.right_sibling)
    offset += BTNodeDescriptor.STRUCT_SIZE
    
    # 写入 B-tree 信息
    btinfo = BTInfo(
        flags=0,
        node_size=4096,
        key_size=0,  # 变长
        val_size=0   # 变长
    )
    
    struct.pack_into('<IIII', data, offset,
                    btinfo.flags, btinfo.node_size,
                    btinfo.key_size, btinfo.val_size)
    offset += BTInfo.STRUCT_SIZE
    
    # 写入根目录条目
    # 条目 1: "." (当前目录)
    write_directory_entry(data, offset, 2, ".", True)
    offset += 100
    
    # 条目 2: ".." (父目录)
    write_directory_entry(data, offset, 2, "..", True)
    offset += 100
    
    # 条目 3: "test.txt" (测试文件)
    write_directory_entry(data, offset, 100, "test.txt", False)
    offset += 100
    
    # 条目 4: "subdir" (子目录)
    write_directory_entry(data, offset, 200, "subdir", True)
    offset += 100
    

def write_directory_entry(data: bytearray, offset: int, 
                         target_id: int, name: str, is_dir: bool) -> None:
    """写入目录条目"""
    # 写入目标 ID
    struct.pack_into('<Q', data, offset, target_id)
    offset += 8
    
    # 写入添加日期
    struct.pack_into('<Q', data, offset, 1000000000)
    offset += 8
    
    # 写入标志
    flags = 0x10 if is_dir else 0x20  # 目录或文件标志
    struct.pack_into('<H', data, offset, flags)
    offset += 2
    
    # 写入文件名
    name_bytes = name.encode('utf-8') + b'\x00'
    struct.pack_into(f'<{len(name_bytes)}s', data, offset, name_bytes)
    offset += len(name_bytes)
    

def write_test_files(data: bytearray, offset: int) -> None:
    """写入测试文件数据"""
    print("写入测试文件数据...")
    
    # 写入 test.txt 文件内容
    test_content = b"Hello, APFS! This is a test file.\n"
    struct.pack_into(f'<{len(test_content)}s', data, offset, test_content)
    offset += len(test_content)
    
    # 写入 inode 信息
    write_inode(data, offset, 100, "test.txt", False)
    offset += 1000
    
    # 写入子目录 inode
    write_inode(data, offset, 200, "subdir", True)
    offset += 1000
    

def write_inode(data: bytearray, offset: int, 
                inode_id: int, name: str, is_dir: bool) -> None:
    """写入 inode 信息"""
    # 创建 JKey
    jkey = JKey(obj_id=inode_id, type=1)  # inode 类型
    
    # 写入 JKey
    struct.pack_into('<QH', data, offset, jkey.obj_id, jkey.type)
    offset += JKey.STRUCT_SIZE
    
    # 写入 inode 数据
    parent_id = 2 if inode_id != 2 else 2  # 根目录的父目录是自己
    private_id = inode_id
    create_time = 1000000000
    mod_time = 1000000000
    change_time = 1000000000
    access_time = 1000000000
    internal_flags = 0
    nchildren = 2 if is_dir else 0
    nlink = 1 if not is_dir else 2
    uid = 501
    gid = 20
    mode = 0o40755 if is_dir else 0o100644  # 目录或文件权限
    pad1 = 0
    pad2 = 0
    bsd_flags = 0
    rdev = 0
    nsec = 0
    
    struct.pack_into('<QQQQQQQiiIIIHHIIQ', data, offset,
                    parent_id, private_id, create_time, mod_time,
                    change_time, access_time, internal_flags,
                    nchildren, nlink, uid, gid, mode,
                    pad1, pad2, bsd_flags, rdev, nsec)
    offset += 88  # JInode 大小
    

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python create_test_apfs.py <output_path> [size]")
        print("示例: python create_test_apfs.py test.apfs 4096000")
        sys.exit(1)
        
    output_path = sys.argv[1]
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 4096 * 1000
    
    create_test_image(output_path, size)
    

if __name__ == '__main__':
    main()
