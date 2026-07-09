"""
unhfs - HFS+ 命令行提取工具

从 HFS+ 卷中提取文件和文件夹。

Usage:
    python -m src.cli.unhfs <image> [options]
    
Options:
    -o, --output <dir>      输出目录
    -p, --path <path>       卷内路径
    -r, --recursive         递归提取
    -f, --force             覆盖已存在的文件
    -v, --verbose           详细输出
    -l, --list              列出文件（不提取）
    --partition <offset>    分区偏移
"""

import os
import sys
import argparse
import struct
from typing import List, Dict, Any, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.hfs import HFSPlusVolume
from src.core.partition import parse_partitions, find_hfs_partitions


class UnhfsError(Exception):
    """unhfs 错误"""
    pass


def list_files(volume: HFSPlusVolume, path: str = '/', recursive: bool = False,
               indent: int = 0) -> List[Dict[str, Any]]:
    """
    列出文件
    
    Args:
        volume: HFS+ 卷
        path: 路径
        recursive: 是否递归
        indent: 缩进级别
    
    Returns:
        文件列表
    """
    results = []
    
    # 获取根目录内容
    if path == '/':
        parent_id = 2  # 根目录 CNID
    else:
        # 解析路径获取 CNID
        parent_id = _resolve_path(volume, path)
        if parent_id is None:
            raise UnhfsError(f"路径不存在: {path}")
    
    # 列出目录内容
    contents = volume.list_folder(parent_id)
    
    for item in contents:
        item_info = {
            'name': item['name'],
            'type': item['type'],
            'id': item['id'],
            'size': item.get('size', 0),
            'indent': indent,
        }
        
        results.append(item_info)
        
        # 递归处理子目录
        if recursive and item['type'] == 'folder':
            sub_path = f"{path.rstrip('/')}/{item['name']}"
            try:
                sub_results = list_files(volume, sub_path, recursive, indent + 1)
                results.extend(sub_results)
            except Exception:
                pass
    
    return results


def _resolve_path(volume: HFSPlusVolume, path: str) -> Optional[int]:
    """
    解析路径获取 CNID
    
    Args:
        volume: HFS+ 卷
        path: 路径
    
    Returns:
        CNID，如果路径不存在则返回 None
    """
    parts = path.strip('/').split('/')
    current_id = 2  # 根目录 CNID
    
    for part in parts:
        if not part:
            continue
        
        # 列出当前目录
        contents = volume.list_folder(current_id)
        
        # 查找匹配的项目
        found = False
        for item in contents:
            if item['name'] == part:
                current_id = item['id']
                found = True
                break
        
        if not found:
            return None
    
    return current_id


def extract_files(volume: HFSPlusVolume, output_dir: str, 
                  path: str = '/', recursive: bool = True,
                  force: bool = False, verbose: bool = False) -> int:
    """
    提取文件
    
    Args:
        volume: HFS+ 卷
        output_dir: 输出目录
        path: 卷内路径
        recursive: 是否递归
        force: 是否覆盖
        verbose: 是否详细输出
    
    Returns:
        提取的文件数
    """
    extracted_count = 0
    
    # 获取要提取的文件列表
    files = list_files(volume, path, recursive)
    
    for file_info in files:
        # 构建输出路径
        if path == '/':
            rel_path = file_info['name']
        else:
            rel_path = path.rstrip('/') + '/' + file_info['name']
        
        output_path = os.path.join(output_dir, rel_path)
        
        if file_info['type'] == 'folder':
            # 创建目录
            os.makedirs(output_path, exist_ok=True)
            if verbose:
                print(f"  目录: {rel_path}/")
        else:
            # 提取文件
            if os.path.exists(output_path) and not force:
                if verbose:
                    print(f"  跳过: {rel_path} (已存在)")
                continue
            
            try:
                # 读取文件数据
                data = volume.read_file(file_info['id'])
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 写入文件
                with open(output_path, 'wb') as f:
                    f.write(data)
                
                extracted_count += 1
                
                if verbose:
                    size_str = _format_size(len(data))
                    print(f"  提取: {rel_path} ({size_str})")
            
            except Exception as e:
                print(f"  错误: {rel_path} - {e}", file=sys.stderr)
    
    return extracted_count


def _format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def main():
    """主入口点"""
    parser = argparse.ArgumentParser(
        description='从 HFS+ 卷中提取文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s image.dmg -o output
  %(prog)s image.dmg -o output -r -v
  %(prog)s image.dmg -l
  %(prog)s image.dmg -p /Documents -o output
"""
    )
    
    parser.add_argument('image', help='HFS+ 镜像文件')
    parser.add_argument('-o', '--output', default='.', help='输出目录 (默认: 当前目录)')
    parser.add_argument('-p', '--path', default='/', help='卷内路径 (默认: /)')
    parser.add_argument('-r', '--recursive', action='store_true', help='递归提取')
    parser.add_argument('-f', '--force', action='store_true', help='覆盖已存在的文件')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('-l', '--list', action='store_true', help='列出文件（不提取）')
    parser.add_argument('--partition', type=int, default=0, help='分区偏移')
    
    args = parser.parse_args()
    
    try:
        # 打开卷
        print(f"正在打开: {args.image}")
        
        with HFSPlusVolume(args.image, volume_offset=args.partition) as vol:
            # 获取卷信息
            info = vol.get_info()
            print(f"卷类型: {info['signature']}")
            print(f"块大小: {info['block_size']:,}")
            print(f"文件数: {info['file_count']:,}")
            print(f"文件夹数: {info['folder_count']:,}")
            print()
            
            if args.list:
                # 列出文件
                files = list_files(vol, args.path, args.recursive)
                
                print(f"{'类型':<8} {'大小':>12} {'名称'}")
                print("-" * 60)
                
                for f in files:
                    type_str = "文件夹" if f['type'] == 'folder' else "文件"
                    size_str = _format_size(f['size']) if f['type'] == 'file' else ''
                    indent = "  " * f['indent']
                    print(f"{type_str:<8} {size_str:>12} {indent}{f['name']}")
                
                print(f"\n共 {len(files)} 个项目")
            
            else:
                # 提取文件
                output_dir = os.path.abspath(args.output)
                os.makedirs(output_dir, exist_ok=True)
                
                print(f"提取到: {output_dir}")
                print()
                
                count = extract_files(vol, output_dir, args.path, 
                                     args.recursive, args.force, args.verbose)
                
                print(f"\n提取完成: {count} 个文件")
    
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
