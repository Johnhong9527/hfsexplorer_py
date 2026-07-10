#!/usr/bin/env python3
"""
APFS 使用示例

演示如何使用 APFS 模块读取 APFS 镜像文件
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.apfs import APFSReader, APFSContainer, APFSVolume


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python apfs_example.py <apfs_image_file>")
        print("示例: python apfs_example.py /path/to/apfs.img")
        sys.exit(1)
        
    image_path = sys.argv[1]
    
    if not Path(image_path).exists():
        print(f"错误: 文件不存在: {image_path}")
        sys.exit(1)
        
    print(f"正在打开 APFS 镜像: {image_path}")
    print("-" * 50)
    
    try:
        with APFSReader(image_path) as reader:
            # 创建容器管理器
            container = APFSContainer(reader)
            container.load()
            
            # 显示容器信息
            print("容器信息:")
            info = container.get_info()
            for key, value in info.items():
                print(f"  {key}: {value}")
                
            print("-" * 50)
            
            # 列出所有卷
            volumes = container.list_volumes()
            print(f"找到 {len(volumes)} 个卷:")
            
            for vol_info in volumes:
                print(f"  卷 {vol_info['index']}: {vol_info['name']}")
                print(f"    UUID: {vol_info['uuid']}")
                print(f"    块大小: {vol_info['block_size']}")
                print(f"    已用块数: {vol_info['total_blocks_used']}")
                
            print("-" * 50)
            
            # 读取第一个卷
            if volumes:
                volume = container.get_volume(0)
                if volume:
                    print("卷详细信息:")
                    vol_info = volume.get_info()
                    for key, value in vol_info.items():
                        print(f"  {key}: {value}")
                        
                    print("-" * 50)
                    
                    # 列出根目录
                    print("根目录内容:")
                    try:
                        entries = volume.list_directory(2)  # 根目录 OID 通常是 2
                        for entry in entries:
                            type_str = "📁" if entry['type'] == 'directory' else "📄"
                            print(f"  {type_str} {entry['name']}")
                    except Exception as e:
                        print(f"  无法读取根目录: {e}")
                        
                    print("-" * 50)
                    
                    # 搜索文件示例
                    print("搜索文件 '*.txt':")
                    try:
                        results = volume.search_files("*.txt")
                        if results:
                            for result in results[:10]:  # 只显示前 10 个
                                print(f"  📄 {result['path']}")
                        else:
                            print("  未找到匹配的文件")
                    except Exception as e:
                        print(f"  搜索失败: {e}")
                        
    except ValueError as e:
        print(f"错误: {e}")
        print("请确保文件是有效的 APFS 镜像")
        sys.exit(1)
    except Exception as e:
        print(f"未知错误: {e}")
        sys.exit(1)
        

if __name__ == '__main__':
    main()
