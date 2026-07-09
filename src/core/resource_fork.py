"""
Resource Fork 支持

Resource Fork 是经典 Mac OS 文件系统中的一种特殊分支。
它包含应用程序资源，如图标、菜单、对话框等。

资源 fork 结构：
- Header (16 bytes)
  - Resource data offset (4 bytes)
  - Resource map offset (4 bytes)
  - Resource data length (4 bytes)
  - Resource map length (4 bytes)
- Resource Data
- Resource Map
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import IntEnum


class ResourceForkError(Exception):
    """Resource Fork 相关错误"""
    pass


@dataclass
class ResourceEntry:
    """
    资源条目
    
    Attributes:
        resource_type: 资源类型 (4 字符)
        resource_id: 资源 ID
        name: 资源名称
        data: 资源数据
        attributes: 属性
    """
    resource_type: str
    resource_id: int
    name: str
    data: bytes
    attributes: int = 0
    
    @property
    def type_code(self) -> int:
        """获取类型代码"""
        return struct.unpack('>I', self.resource_type.encode('ascii')[:4].ljust(4, b' '))[0]
    
    @property
    def is_compressed(self) -> bool:
        """是否压缩"""
        return bool(self.attributes & 0x01)
    
    @property
    def is_purgeable(self) -> bool:
        """是否可清除"""
        return bool(self.attributes & 0x20)
    
    @property
    def is_locked(self) -> bool:
        """是否锁定"""
        return bool(self.attributes & 0x10)


@dataclass
class ResourceMap:
    """
    资源映射
    
    Attributes:
        types: 类型列表
        entries: 资源条目字典 (类型 -> 条目列表)
    """
    types: List[str] = field(default_factory=list)
    entries: Dict[str, List[ResourceEntry]] = field(default_factory=dict)
    
    def get_resource(self, resource_type: str, resource_id: int) -> Optional[ResourceEntry]:
        """
        获取资源
        
        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
        
        Returns:
            资源条目，如果不存在则返回 None
        """
        if resource_type in self.entries:
            for entry in self.entries[resource_type]:
                if entry.resource_id == resource_id:
                    return entry
        return None
    
    def get_resources_by_type(self, resource_type: str) -> List[ResourceEntry]:
        """
        获取指定类型的所有资源
        
        Args:
            resource_type: 资源类型
        
        Returns:
            资源条目列表
        """
        return self.entries.get(resource_type, [])
    
    def get_all_types(self) -> List[str]:
        """获取所有资源类型"""
        return self.types.copy()


@dataclass
class ResourceFork:
    """
    Resource Fork
    
    Attributes:
        data_offset: 资源数据偏移
        map_offset: 资源映射偏移
        data_length: 资源数据长度
        map_length: 资源映射长度
        resource_map: 资源映射
    """
    data_offset: int
    map_offset: int
    data_length: int
    map_length: int
    resource_map: ResourceMap
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'ResourceFork':
        """
        从字节序列解析
        
        Args:
            data: Resource Fork 数据
        
        Returns:
            ResourceFork 对象
        """
        if len(data) < 16:
            raise ResourceForkError("数据太短，无法解析 Resource Fork")
        
        # 解析头部
        data_offset = struct.unpack_from('>I', data, 0)[0]
        map_offset = struct.unpack_from('>I', data, 4)[0]
        data_length = struct.unpack_from('>I', data, 8)[0]
        map_length = struct.unpack_from('>I', data, 12)[0]
        
        # 验证
        if map_offset + map_length > len(data):
            raise ResourceForkError("Resource Map 超出数据范围")
        
        # 解析资源映射
        resource_map = cls._parse_resource_map(data, map_offset, data_offset)
        
        return cls(
            data_offset=data_offset,
            map_offset=map_offset,
            data_length=data_length,
            map_length=map_length,
            resource_map=resource_map
        )
    
    @staticmethod
    def _parse_resource_map(data: bytes, map_offset: int, 
                            data_offset: int) -> ResourceMap:
        """
        解析资源映射
        
        Args:
            data: 完整数据
            map_offset: 映射偏移
            data_offset: 数据偏移
        
        Returns:
            ResourceMap 对象
        """
        resource_map = ResourceMap()
        
        # 映射头部 (22 bytes)
        # 0-4: 保留
        # 4-8: 属性
        # 8-10: 类型列表偏移 (相对于映射开始)
        # 10-12: 名称列表偏移 (相对于映射开始)
        # 12-14: 类型数量 - 1
        
        if map_offset + 22 > len(data):
            return resource_map
        
        # 类型数量 (实际数量 = type_count + 1)
        type_count = struct.unpack_from('>H', data, map_offset + 12)[0] + 1
        
        # 类型列表偏移
        type_list_offset = map_offset + struct.unpack_from('>H', data, map_offset + 8)[0]
        
        # 名称列表偏移
        name_list_offset = map_offset + struct.unpack_from('>H', data, map_offset + 10)[0]
        
        # 解析类型列表
        current_offset = type_list_offset
        
        for i in range(type_count):
            if current_offset + 8 > len(data):
                break
            
            # 类型 (4 bytes)
            resource_type = data[current_offset:current_offset + 4].decode('ascii', errors='replace')
            
            # 资源数量 - 1 (2 bytes)
            num_resources = struct.unpack_from('>H', data, current_offset + 4)[0] + 1
            
            # 资源列表偏移 (相对于类型列表开始) (2 bytes)
            resource_list_offset = type_list_offset + struct.unpack_from('>H', data, current_offset + 6)[0]
            
            resource_map.types.append(resource_type)
            resource_map.entries[resource_type] = []
            
            # 解析资源列表
            res_offset = resource_list_offset
            
            for j in range(num_resources):
                if res_offset + 12 > len(data):
                    break
                
                # 资源 ID (2 bytes)
                resource_id = struct.unpack_from('>h', data, res_offset)[0]
                
                # 名称偏移 (2 bytes)
                name_offset = struct.unpack_from('>H', data, res_offset + 2)[0]
                
                # 属性 (1 byte)
                attributes = data[res_offset + 4]
                
                # 数据偏移 (3 bytes)
                data_offset_entry = struct.unpack_from('>I', data[res_offset + 5:res_offset + 9])[0] & 0x00FFFFFF
                
                # 保留 (4 bytes)
                reserved = struct.unpack_from('>I', data, res_offset + 8)[0]
                
                # 读取资源名称
                name = ''
                if name_offset != 0xFFFF:
                    abs_name_offset = name_list_offset + name_offset
                    if abs_name_offset < len(data):
                        name_length = data[abs_name_offset]
                        if abs_name_offset + 1 + name_length <= len(data):
                            name = data[abs_name_offset + 1:abs_name_offset + 1 + name_length].decode('ascii', errors='replace')
                
                # 读取资源数据
                abs_data_offset = data_offset + data_offset_entry
                if abs_data_offset + 4 <= len(data):
                    resource_data_length = struct.unpack_from('>I', data, abs_data_offset)[0]
                    if abs_data_offset + 4 + resource_data_length <= len(data):
                        resource_data = data[abs_data_offset + 4:abs_data_offset + 4 + resource_data_length]
                    else:
                        resource_data = b''
                else:
                    resource_data = b''
                
                # 创建资源条目
                entry = ResourceEntry(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    name=name,
                    data=resource_data,
                    attributes=attributes
                )
                
                resource_map.entries[resource_type].append(entry)
                
                res_offset += 12
            
            current_offset += 8
        
        return resource_map
    
    def get_resource(self, resource_type: str, resource_id: int) -> Optional[ResourceEntry]:
        """
        获取资源
        
        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
        
        Returns:
            资源条目
        """
        return self.resource_map.get_resource(resource_type, resource_id)
    
    def get_resources_by_type(self, resource_type: str) -> List[ResourceEntry]:
        """
        获取指定类型的所有资源
        
        Args:
            resource_type: 资源类型
        
        Returns:
            资源条目列表
        """
        return self.resource_map.get_resources_by_type(resource_type)
    
    def get_all_types(self) -> List[str]:
        """获取所有资源类型"""
        return self.resource_map.get_all_types()
    
    def __str__(self) -> str:
        """字符串表示"""
        lines = [
            f"Resource Fork:",
            f"  Data Offset: {self.data_offset}",
            f"  Map Offset: {self.map_offset}",
            f"  Data Length: {self.data_length}",
            f"  Map Length: {self.map_length}",
            f"  Resource Types: {len(self.resource_map.types)}",
        ]
        
        for resource_type in self.resource_map.types:
            entries = self.resource_map.entries[resource_type]
            lines.append(f"    {resource_type}: {len(entries)} resources")
        
        return "\n".join(lines)


def open_resource_fork(data: bytes) -> ResourceFork:
    """
    打开 Resource Fork
    
    Args:
        data: Resource Fork 数据
    
    Returns:
        ResourceFork 对象
    """
    return ResourceFork.from_bytes(data)


# 常见资源类型
RESOURCE_TYPES = {
    'ICON': '图标',
    'ICN#': '图标列表',
    'icl4': '4 位图标',
    'icl8': '8 位图标',
    'ics#': '小图标列表',
    'ics4': '4 位小图标',
    'ics8': '8 位小图标',
    'MENU': '菜单',
    'DLOG': '对话框',
    'DITL': '对话框项目列表',
    'ALRT': '警告',
    'WIND': '窗口',
    'CNTL': '控件',
    'STR#': '字符串列表',
    'STR ': '字符串',
    'TEXT': '文本',
    'PICT': '图片',
    'snd ': '声音',
    'CODE': '代码',
    'cdev': '控制面板',
    'FREF': '文件引用',
    'BNDL': '捆绑',
    'SIZE': '大小',
    'vers': '版本',
    'RECT': '矩形',
    'PAT ': '图案',
    'CURS': '光标',
    'crsr': '彩色光标',
}
