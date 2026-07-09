#!/usr/bin/env python3
"""
HFS+ 格式化示例

演示如何使用 HFSPlusFormatter 创建新的 HFS+ 文件系统。
"""

import os
import sys
import tempfile

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.hfs.formatter import HFSPlusFormatter, FormatOptions, format_volume
from src.core.hfs.reader import HFSPlusVolume


def example_basic_format():
    """基本格式化示例"""
    print("=== 基本格式化示例 ===")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "example.hfs")
        
        # 创建文件（10 MB）
        print("创建 10 MB 的文件...")
        with open(path, "wb") as f:
            f.seek(10 * 1024 * 1024 - 1)
            f.write(b'\x00')
        
        # 格式化为 HFS+
        print("格式化为 HFS+...")
        header = format_volume(path, "MyVolume", 4096)
        
        print(f"格式化完成！")
        print(f"  签名: {'HFS+' if header.is_hfs_plus else 'HFSX'}")
        print(f"  块大小: {header.block_size} 字节")
        print(f"  总块数: {header.total_blocks:,}")
        print(f"  空闲块: {header.free_blocks:,}")
        print(f"  卷大小: {header.volume_size:,} 字节 ({header.volume_size / (1024*1024):.2f} MB)")
        print(f"  空闲空间: {header.free_space:,} 字节 ({header.free_space / (1024*1024):.2f} MB)")
        print()


def example_custom_options():
    """自定义选项格式化示例"""
    print("=== 自定义选项格式化示例 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "custom.hfs")
        
        # 创建文件（50 MB）
        print("创建 50 MB 的文件...")
        with open(path, "wb") as f:
            f.seek(50 * 1024 * 1024 - 1)
            f.write(b'\x00')
        
        # 创建格式化选项
        options = FormatOptions(
            volume_name="CustomVolume",
            block_size=8192,  # 8 KB 块大小
            journal_size=0,   # 不启用日志
        )
        
        # 格式化
        print("使用自定义选项格式化...")
        formatter = HFSPlusFormatter()
        header = formatter.format(path, options.volume_name, options.block_size)
        
        print(f"格式化完成！")
        print(f"  块大小: {header.block_size} 字节")
        print(f"  总块数: {header.total_blocks:,}")
        print()


def example_read_formatted():
    """读取格式化后的卷"""
    print("=== 读取格式化后的卷 ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "readable.hfs")
        
        # 创建并格式化
        print("创建并格式化卷...")
        with open(path, "wb") as f:
            f.seek(10 * 1024 * 1024 - 1)
            f.write(b'\x00')
        
        format_volume(path, "ReadableVolume", 4096)
        
        # 读取卷
        print("读取卷信息...")
        with HFSPlusVolume(path) as vol:
            info = vol.get_info()
            print(f"卷信息:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            # 列出根目录
            print(f"\n根目录内容:")
            contents = vol.list_folder(2)  # 2 = 根目录 CNID
            if contents:
                for item in contents:
                    print(f"  [{item['type']}] {item['name']}")
            else:
                print("  (空)")
        print()


def example_different_sizes():
    """不同大小的格式化示例"""
    print("=== 不同大小的格式化示例 ===")
    
    sizes = [
        (1 * 1024 * 1024, "1 MB"),
        (10 * 1024 * 1024, "10 MB"),
        (100 * 1024 * 1024, "100 MB"),
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for size, label in sizes:
            path = os.path.join(tmpdir, f"vol_{label.replace(' ', '_')}.hfs")
            
            # 创建文件
            with open(path, "wb") as f:
                f.seek(size - 1)
                f.write(b'\x00')
            
            # 格式化
            header = format_volume(path, f"Vol{label}", 4096)
            
            print(f"{label} 卷:")
            print(f"  总块数: {header.total_blocks:,}")
            print(f"  空闲块: {header.free_blocks:,}")
            print(f"  使用率: {(1 - header.free_blocks / header.total_blocks) * 100:.1f}%")
        print()


def example_block_sizes():
    """不同块大小的格式化示例"""
    print("=== 不同块大小的格式化示例 ===")
    
    block_sizes = [512, 1024, 4096, 8192, 16384]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for block_size in block_sizes:
            path = os.path.join(tmpdir, f"vol_{block_size}.hfs")
            size = 10 * 1024 * 1024  # 10 MB
            
            # 确保大小是块大小的整数倍
            size = (size // block_size) * block_size
            
            # 创建文件
            with open(path, "wb") as f:
                f.seek(size - 1)
                f.write(b'\x00')
            
            # 格式化
            header = format_volume(path, f"Vol{block_size}", block_size)
            
            print(f"块大小 {block_size:,} 字节:")
            print(f"  总块数: {header.total_blocks:,}")
            print(f"  空闲块: {header.free_blocks:,}")
        print()


if __name__ == "__main__":
    print("HFS+ 格式化示例\n")
    
    example_basic_format()
    example_custom_options()
    example_read_formatted()
    example_different_sizes()
    example_block_sizes()
    
    print("所有示例执行完成！")
