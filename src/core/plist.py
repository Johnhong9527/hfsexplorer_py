"""
Property List (plist) 解析

支持二进制和 XML 格式的 plist 文件。
plist 是 Apple 用于存储配置和数据的文件格式。
"""

import struct
import plistlib
from dataclasses import dataclass
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timezone, timedelta
from enum import IntEnum


class PlistError(Exception):
    """Plist 相关错误"""
    pass


class PlistType(IntEnum):
    """Plist 类型"""
    BINARY = 0
    XML = 1


def detect_plist_type(data: bytes) -> PlistType:
    """
    检测 plist 类型
    
    Args:
        data: 文件数据
    
    Returns:
        PlistType 枚举值
    """
    # 二进制 plist 以 "bplist" 开头
    if data[:6] == b'bplist':
        return PlistType.BINARY
    
    # XML plist 以 "<?xml" 或 "<!DOCTYPE" 开头
    if data[:5] == b'<?xml' or data[:9] == b'<!DOCTYPE':
        return PlistType.XML
    
    # 尝试解析
    try:
        plistlib.loads(data)
        return PlistType.XML
    except:
        pass
    
    raise PlistError("无法识别 plist 类型")


def parse_plist(data: bytes) -> Any:
    """
    解析 plist 数据
    
    Args:
        data: plist 数据
    
    Returns:
        解析后的 Python 对象
    """
    # 检测类型
    plist_type = detect_plist_type(data)
    
    if plist_type == PlistType.BINARY:
        return _parse_binary_plist(data)
    else:
        return plistlib.loads(data)


def _parse_binary_plist(data: bytes) -> Any:
    """
    解析二进制 plist
    
    Args:
        data: 二进制 plist 数据
    
    Returns:
        解析后的 Python 对象
    """
    # 使用 Python 内置的 plistlib
    try:
        return plistlib.loads(data)
    except Exception as e:
        raise PlistError(f"解析二进制 plist 失败: {e}")


def parse_plist_file(path: str) -> Any:
    """
    解析 plist 文件
    
    Args:
        path: 文件路径
    
    Returns:
        解析后的 Python 对象
    """
    with open(path, 'rb') as f:
        data = f.read()
    
    return parse_plist(data)


def create_binary_plist(obj: Any) -> bytes:
    """
    创建二进制 plist
    
    Args:
        obj: Python 对象
    
    Returns:
        二进制 plist 数据
    """
    return plistlib.dumps(obj, fmt=plistlib.FMT_BINARY)


def create_xml_plist(obj: Any) -> bytes:
    """
    创建 XML plist
    
    Args:
        obj: Python 对象
    
    Returns:
        XML plist 数据
    """
    return plistlib.dumps(obj, fmt=plistlib.FMT_XML)


# =============================================================================
# plist 路径解析
# =============================================================================

def get_plist_value(plist: Any, *keys: str) -> Any:
    """
    获取 plist 中的值
    
    Args:
        plist: plist 对象
        *keys: 键路径
    
    Returns:
        值
    """
    current = plist
    
    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        elif isinstance(current, list):
            try:
                index = int(key)
                current = current[index]
            except (ValueError, IndexError):
                return None
        else:
            return None
    
    return current


def get_plist_string(plist: Any, *keys: str, default: str = '') -> str:
    """获取字符串值"""
    value = get_plist_value(plist, *keys)
    if isinstance(value, str):
        return value
    return default


def get_plist_int(plist: Any, *keys: str, default: int = 0) -> int:
    """获取整数值"""
    value = get_plist_value(plist, *keys)
    if isinstance(value, (int, float)):
        return int(value)
    return default


def get_plist_bool(plist: Any, *keys: str, default: bool = False) -> bool:
    """获取布尔值"""
    value = get_plist_value(plist, *keys)
    if isinstance(value, bool):
        return value
    return default


def get_plist_dict(plist: Any, *keys: str) -> Dict[str, Any]:
    """获取字典值"""
    value = get_plist_value(plist, *keys)
    if isinstance(value, dict):
        return value
    return {}


def get_plist_list(plist: Any, *keys: str) -> List[Any]:
    """获取列表值"""
    value = get_plist_value(plist, *keys)
    if isinstance(value, list):
        return value
    return []


# =============================================================================
# 常见 plist 结构
# =============================================================================

def parse_info_plist(data: bytes) -> Dict[str, Any]:
    """
    解析 Info.plist
    
    Args:
        data: Info.plist 数据
    
    Returns:
        应用信息字典
    """
    plist = parse_plist(data)
    
    return {
        'name': get_plist_string(plist, 'CFBundleName'),
        'identifier': get_plist_string(plist, 'CFBundleIdentifier'),
        'version': get_plist_string(plist, 'CFBundleShortVersionString'),
        'build': get_plist_string(plist, 'CFBundleVersion'),
        'executable': get_plist_string(plist, 'CFBundleExecutable'),
        'package_type': get_plist_string(plist, 'CFBundlePackageType'),
        'signature': get_plist_string(plist, 'CFBundleSignature'),
        'info_dictionary_version': get_plist_string(plist, 'CFBundleInfoDictionaryVersion'),
        'minimum_system_version': get_plist_string(plist, 'LSMinimumSystemVersion'),
    }


def parse_dmg_plist(data: bytes) -> Dict[str, Any]:
    """
    解析 DMG plist
    
    Args:
        data: DMG plist 数据
    
    Returns:
        DMG 信息字典
    """
    plist = parse_plist(data)
    
    result = {}
    
    # 资源分支
    resource_fork = get_plist_dict(plist, 'resource-fork')
    if resource_fork:
        # 块映射表
        blkx_list = get_plist_list(resource_fork, 'blkx')
        result['partitions'] = []
        
        for blkx in blkx_list:
            partition = {
                'name': get_plist_string(blkx, 'Name'),
                'id': get_plist_int(blkx, 'ID'),
                'attributes': get_plist_int(blkx, 'Attributes'),
            }
            result['partitions'].append(partition)
        
        # 摘要信息
        plist_list = get_plist_list(resource_fork, 'plist')
        if plist_list:
            result['properties'] = plist_list[0] if plist_list else {}
    
    # 摘要
    result['udif_resource_fork_signature'] = get_plist_int(plist, 'udif-resource-fork-signature')
    
    return result


# =============================================================================
# DMG plist 专用解析
# =============================================================================

def parse_dmg_resource_fork(data: bytes) -> Dict[str, Any]:
    """
    解析 DMG 资源分支 plist
    
    Args:
        data: plist 数据
    
    Returns:
        资源分支信息
    """
    plist = parse_plist(data)
    
    resource_fork = plist.get('resource-fork', {})
    
    result = {
        'blkx': [],
        'plst': [],
    }
    
    # 解析 blkx 条目
    for blkx in resource_fork.get('blkx', []):
        entry = {
            'name': blkx.get('Name', ''),
            'id': blkx.get('ID', 0),
            'attributes': blkx.get('Attributes', 0),
            'data': blkx.get('Data', b''),
        }
        result['blkx'].append(entry)
    
    # 解析 plst 条目
    for plst in resource_fork.get('plst', []):
        result['plst'].append(plst)
    
    return result
