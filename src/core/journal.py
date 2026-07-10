"""
HFS+ 日志支持

HFS+ 日志 (Journal) 用于保证文件系统的一致性。
它记录所有修改操作，以便在系统崩溃后恢复。
"""

import struct
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import IntEnum


class JournalError(Exception):
    """日志相关错误"""
    pass


# 日志签名
JOURNAL_SIGNATURE = b'RXid'

# 日志头块签名
JOURNAL_HEADER_SIGNATURE = b'JRNL'


class JournalBlockType(IntEnum):
    """日志块类型"""
    HEADER = 0      # 头块
    DATA = 1        # 数据块


@dataclass
class JournalInfoBlock:
    """
    日志信息块
    
    位于卷头指定的 journal_info_block 偏移处。
    
    Attributes:
        signature: 签名 'RXid'
        flags: 标志
        device_signature: 设备签名
        journal_offset: 日志偏移
        journal_size: 日志大小
    """
    signature: bytes
    flags: int
    device_signature: bytes
    journal_offset: int
    journal_size: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'JournalInfoBlock':
        """从字节序列解析"""
        if len(data) < 512:
            raise JournalError("数据太短")
        
        signature = data[0:4]
        if signature != JOURNAL_SIGNATURE:
            raise JournalError(f"无效的签名: {signature}")
        
        flags = struct.unpack_from('>I', data, 4)[0]
        device_signature = data[8:24]
        journal_offset = struct.unpack_from('>Q', data, 24)[0]
        journal_size = struct.unpack_from('>Q', data, 32)[0]
        
        return cls(
            signature=signature,
            flags=flags,
            device_signature=device_signature,
            journal_offset=journal_offset,
            journal_size=journal_size
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == JOURNAL_SIGNATURE
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"Journal Info Block:\n"
            f"  Signature: {self.signature}\n"
            f"  Flags: 0x{self.flags:08X}\n"
            f"  Journal Offset: {self.journal_offset:,}\n"
            f"  Journal Size: {self.journal_size:,} bytes"
        )


@dataclass
class JournalHeader:
    """
    日志头
    
    Attributes:
        signature: 签名 'JRNL'
        checksum: 校验和
        journal_size: 日志大小
        sequence_number: 序列号
        start: 日志数据起始
        end: 日志数据结束
    """
    signature: bytes
    checksum: int
    journal_size: int
    sequence_number: int
    start: int
    end: int
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'JournalHeader':
        """从字节序列解析"""
        if len(data) < 512:
            raise JournalError("数据太短")
        
        signature = data[0:4]
        if signature != JOURNAL_HEADER_SIGNATURE:
            raise JournalError(f"无效的签名: {signature}")
        
        checksum = struct.unpack_from('>I', data, 4)[0]
        journal_size = struct.unpack_from('>Q', data, 8)[0]
        sequence_number = struct.unpack_from('>Q', data, 16)[0]
        start = struct.unpack_from('>Q', data, 24)[0]
        end = struct.unpack_from('>Q', data, 32)[0]
        
        return cls(
            signature=signature,
            checksum=checksum,
            journal_size=journal_size,
            sequence_number=sequence_number,
            start=start,
            end=end
        )
    
    @property
    def is_valid(self) -> bool:
        """签名是否有效"""
        return self.signature == JOURNAL_HEADER_SIGNATURE
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"Journal Header:\n"
            f"  Signature: {self.signature}\n"
            f"  Journal Size: {self.journal_size:,}\n"
            f"  Sequence Number: {self.sequence_number}\n"
            f"  Start: {self.start:,}\n"
            f"  End: {self.end:,}"
        )


@dataclass
class JournalTransaction:
    """
    日志事务
    
    Attributes:
        sequence_number: 序列号
        blocks: 块列表 (原始数据, 修改后的数据)
    """
    sequence_number: int
    blocks: List[tuple]  # [(block_number, old_data, new_data), ...]


class Journal:
    """
    HFS+ 日志
    
    Attributes:
        info_block: 日志信息块
        header: 日志头
        stream: 文件流
    """
    
    def __init__(self, stream, journal_offset: int = 0):
        """
        初始化日志
        
        Args:
            stream: 二进制流
            journal_offset: 日志偏移
        """
        self.stream = stream
        self.journal_offset = journal_offset
        self.info_block: Optional[JournalInfoBlock] = None
        self.header: Optional[JournalHeader] = None
        
        self._parse()
    
    def _parse(self):
        """解析日志"""
        # 读取日志信息块
        self.stream.seek(self.journal_offset)
        info_data = self.stream.read(512)
        self.info_block = JournalInfoBlock.from_bytes(info_data)
        
        if not self.info_block.is_valid:
            raise JournalError("无效的日志信息块")
        
        # 读取日志头
        self.stream.seek(self.info_block.journal_offset)
        header_data = self.stream.read(512)
        self.header = JournalHeader.from_bytes(header_data)
        
        if not self.header.is_valid:
            raise JournalError("无效的日志头")
    
    @property
    def has_pending_transactions(self) -> bool:
        """是否有待处理的事务"""
        if self.header is None:
            return False
        return self.header.start != self.header.end
    
    def get_info(self) -> Dict[str, Any]:
        """获取日志信息"""
        return {
            'valid': self.info_block is not None and self.header is not None,
            'journal_offset': self.info_block.journal_offset if self.info_block else 0,
            'journal_size': self.info_block.journal_size if self.info_block else 0,
            'sequence_number': self.header.sequence_number if self.header else 0,
            'has_pending': self.has_pending_transactions,
        }
    
    def replay(self) -> List[JournalTransaction]:
        """
        重放日志
        
        Returns:
            事务列表
        """
        transactions = []
        
        if not self.has_pending_transactions:
            return transactions
        
        # 读取日志数据
        current = self.header.start
        
        while current != self.header.end:
            # 读取事务头
            self.stream.seek(self.info_block.journal_offset + current)
            tx_data = self.stream.read(512)
            
            # 解析事务
            # 这里提供一个简化的实现
            # 完整实现需要处理事务头和数据块
            
            # 移动到下一个位置
            current = (current + 512) % self.header.journal_size
        
        return transactions
    
    def clear(self):
        """清除日志"""
        if self.header is None:
            return
        
        # 更新日志头
        self.header.start = self.header.end
        
        # 写入更新后的日志头
        # 这里只是更新内存中的值
        # 实际写入需要更复杂的逻辑
    
    def __str__(self) -> str:
        """字符串表示"""
        info = self.get_info()
        return (
            f"HFS+ Journal:\n"
            f"  Valid: {info['valid']}\n"
            f"  Journal Offset: {info['journal_offset']:,}\n"
            f"  Journal Size: {info['journal_size']:,} bytes\n"
            f"  Sequence Number: {info['sequence_number']}\n"
            f"  Has Pending: {info['has_pending']}"
        )


def parse_journal(stream, journal_offset: int = 0) -> Optional[Journal]:
    """
    解析日志
    
    Args:
        stream: 二进制流
        journal_offset: 日志偏移
    
    Returns:
        Journal 对象，如果解析失败则返回 None
    """
    try:
        return Journal(stream, journal_offset)
    except JournalError:
        return None


def is_journal_valid(stream, journal_offset: int = 0) -> bool:
    """
    检查日志是否有效
    
    Args:
        stream: 二进制流
        journal_offset: 日志偏移
    
    Returns:
        日志是否有效
    """
    try:
        journal = Journal(stream, journal_offset)
        return journal.info_block.is_valid and journal.header.is_valid
    except:
        return False
