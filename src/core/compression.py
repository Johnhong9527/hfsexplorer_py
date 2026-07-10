"""
压缩镜像支持

支持 ADC (Apple Data Compression) 和 LZFSE 压缩算法。
"""

import struct
import zlib
from typing import Optional, Tuple


class CompressionError(Exception):
    """压缩相关错误"""
    pass


def decompress_adc(data: bytes, uncompressed_size: int) -> bytes:
    """
    ADC (Apple Data Compression) 解压
    
    ADC 是一种简单的压缩算法，用于压缩镜像和资源。
    
    Args:
        data: 压缩数据
        uncompressed_size: 未压缩大小
    
    Returns:
        解压后的数据
    """
    result = bytearray()
    pos = 0
    
    while pos < len(data) and len(result) < uncompressed_size:
        # 读取控制字节
        control = data[pos]
        pos += 1
        
        if control & 0x80:
            # 压缩块
            if control & 0x40:
                # 长偏移
                if pos + 2 > len(data):
                    break
                length = ((control & 0x3F) >> 2) + 4
                offset = ((control & 0x03) << 8) | data[pos]
                pos += 1
            else:
                # 短偏移
                if pos + 1 > len(data):
                    break
                length = (control >> 2) & 0x0F
                offset = (control & 0x03) << 8 | data[pos]
                pos += 1
            
            # 复制数据
            if offset > 0:
                for i in range(length):
                    if len(result) - offset >= 0:
                        result.append(result[len(result) - offset])
                    else:
                        result.append(0)
            else:
                # 特殊情况：重复上一个字节
                if result:
                    for i in range(length):
                        result.append(result[-1])
        else:
            # 字面量块
            length = control + 1
            if pos + length > len(data):
                length = len(data) - pos
            result.extend(data[pos:pos + length])
            pos += length
    
    return bytes(result[:uncompressed_size])


def decompress_zlib_block(data: bytes) -> bytes:
    """
    zlib 块解压
    
    Args:
        data: 压缩数据
    
    Returns:
        解压后的数据
    """
    try:
        return zlib.decompress(data)
    except zlib.error as e:
        raise CompressionError(f"zlib 解压失败: {e}")


def decompress_bzip2(data: bytes) -> bytes:
    """
    bzip2 解压
    
    Args:
        data: 压缩数据
    
    Returns:
        解压后的数据
    """
    try:
        import bz2
        return bz2.decompress(data)
    except Exception as e:
        raise CompressionError(f"bzip2 解压失败: {e}")


def decompress_lzvn(data: bytes, uncompressed_size: int) -> bytes:
    """
    LZVN 解压
    
    LZVN 是 Apple 开发的快速压缩算法。
    
    Args:
        data: 压缩数据
        uncompressed_size: 未压缩大小
    
    Returns:
        解压后的数据
    """
    # LZVN 解压实现
    # 这是一个简化的实现，完整实现需要更复杂的逻辑
    
    result = bytearray()
    pos = 0
    
    while pos < len(data) and len(result) < uncompressed_size:
        # 读取命令字节
        cmd = data[pos]
        pos += 1
        
        if cmd >= 0x20:
            # 压缩引用
            if cmd >= 0xC0:
                # 长引用
                if pos + 3 > len(data):
                    break
                length = (cmd >> 6) & 0x03
                offset = ((cmd & 0x3F) << 8) | data[pos]
                pos += 1
                length += 3
            elif cmd >= 0x80:
                # 中引用
                if pos + 2 > len(data):
                    break
                length = (cmd >> 4) & 0x03
                offset = ((cmd & 0x0F) << 8) | data[pos]
                pos += 1
                length += 3
            elif cmd >= 0x40:
                # 短引用
                if pos + 1 > len(data):
                    break
                length = (cmd >> 2) & 0x07
                offset = ((cmd & 0x03) << 8) | data[pos]
                pos += 1
                length += 3
            else:
                # 字面量
                length = (cmd >> 2) & 0x0F
                offset = (cmd & 0x03) << 8
                if offset == 0:
                    # 特殊情况
                    if pos + 1 > len(data):
                        break
                    offset = data[pos]
                    pos += 1
                length += 3
            
            # 复制数据
            for i in range(length):
                if len(result) - offset >= 0:
                    result.append(result[len(result) - offset])
                else:
                    result.append(0)
        else:
            # 字面量
            length = cmd + 1
            if pos + length > len(data):
                length = len(data) - pos
            result.extend(data[pos:pos + length])
            pos += length
    
    return bytes(result[:uncompressed_size])


def decompress_lzfse(data: bytes, uncompressed_size: int) -> bytes:
    """
    LZFSE 解压
    
    LZFSE (LZFSE - Lempel-Ziv Finite State Entropy) 是 Apple 开发的压缩算法。
    
    Args:
        data: 压缩数据
        uncompressed_size: 未压缩大小
    
    Returns:
        解压后的数据
    """
    # LZFSE 解压需要更复杂的实现
    # 这里提供一个框架
    raise CompressionError("LZFSE 解压暂不完整支持")


def decompress_block(data: bytes, compression_type: int, 
                    uncompressed_size: int) -> bytes:
    """
    解压数据块
    
    Args:
        data: 压缩数据
        compression_type: 压缩类型
        uncompressed_size: 未压缩大小
    
    Returns:
        解压后的数据
    """
    from src.core.dmg import DMGBlockType
    
    if compression_type == DMGBlockType.RAW:
        return data
    elif compression_type == DMGBlockType.ZERO:
        return b'\x00' * uncompressed_size
    elif compression_type == DMGBlockType.ADC_COMPRESSED:
        return decompress_adc(data, uncompressed_size)
    elif compression_type == DMGBlockType.ZLIB_COMPRESSED:
        return decompress_zlib_block(data)
    elif compression_type == DMGBlockType.BZIP2_COMPRESSED:
        return decompress_bzip2(data)
    elif compression_type == DMGBlockType.LZFSE_COMPRESSED:
        return decompress_lzfse(data, uncompressed_size)
    else:
        raise CompressionError(f"未知的压缩类型: 0x{compression_type:08X}")
