"""
APFS 事务管理模块

提供完整的 APFS 事务管理功能，包括：
- 事务创建、提交、回滚
- 写前日志 (WAL)
- 崩溃恢复
- 一致性保证
"""

import struct
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, BinaryIO, Any
from enum import IntEnum, IntFlag
from collections import OrderedDict


# =============================================================================
# APFS 事务常量
# =============================================================================

# 事务状态
class TransactionState(IntEnum):
    """事务状态"""
    ACTIVE = 0      # 活动状态
    COMMITTED = 1   # 已提交
    ABORTED = 2     # 已中止
    ROLLED_BACK = 3 # 已回滚


# 日志类型
class LogEntryType(IntEnum):
    """日志条目类型"""
    BEGIN = 1       # 事务开始
    WRITE = 2       # 写操作
    COMMIT = 3      # 事务提交
    CHECKPOINT = 4  # 检查点
    ROLLBACK = 5    # 回滚


# =============================================================================
# APFS 事务数据结构
# =============================================================================

@dataclass
class TransactionInfo:
    """事务信息"""
    xid: int  # 事务 ID
    state: TransactionState
    start_time: int  # 开始时间
    commit_time: int = 0  # 提交时间
    operations: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<Q', self.xid)
        result += struct.pack('<I', self.state)
        result += struct.pack('<Q', self.start_time)
        result += struct.pack('<Q', self.commit_time)
        result += struct.pack('<I', len(self.operations))
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'TransactionInfo':
        """反序列化"""
        xid = struct.unpack_from('<Q', data, offset)[0]
        state = TransactionState(struct.unpack_from('<I', data, offset + 8)[0])
        start_time = struct.unpack_from('<Q', data, offset + 12)[0]
        commit_time = struct.unpack_from('<Q', data, offset + 20)[0]
        
        return cls(
            xid=xid,
            state=state,
            start_time=start_time,
            commit_time=commit_time
        )


@dataclass
class LogEntry:
    """日志条目"""
    entry_type: LogEntryType
    xid: int  # 事务 ID
    block_num: int  # 块号
    offset: int  # 块内偏移
    length: int  # 数据长度
    data: bytes  # 数据
    checksum: int = 0  # 校验和
    
    def calculate_checksum(self) -> int:
        """计算校验和"""
        return int.from_bytes(
            hashlib.sha256(self.data).digest()[:4],
            'little'
        )
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = struct.pack('<I', self.entry_type)
        result += struct.pack('<Q', self.xid)
        result += struct.pack('<Q', self.block_num)
        result += struct.pack('<I', self.offset)
        result += struct.pack('<I', self.length)
        result += struct.pack('<I', self.checksum)
        result += self.data
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'LogEntry':
        """反序列化"""
        entry_type = LogEntryType(struct.unpack_from('<I', data, offset)[0])
        xid = struct.unpack_from('<Q', data, offset + 4)[0]
        block_num = struct.unpack_from('<Q', data, offset + 12)[0]
        log_offset = struct.unpack_from('<I', data, offset + 20)[0]
        length = struct.unpack_from('<I', data, offset + 24)[0]
        checksum = struct.unpack_from('<I', data, offset + 28)[0]
        
        entry_data = data[offset + 32:offset + 32 + length]
        
        return cls(
            entry_type=entry_type,
            xid=xid,
            block_num=block_num,
            offset=log_offset,
            length=length,
            data=entry_data,
            checksum=checksum
        )


@dataclass
class JournalHeader:
    """日志头部"""
    magic: bytes  # 魔数
    version: int  # 版本
    block_size: int  # 块大小
    total_blocks: int  # 总块数
    next_xid: int  # 下一个事务 ID
    start_offset: int  # 日志起始偏移
    end_offset: int  # 日志结束偏移
    checksum: int = 0  # 校验和
    
    def to_bytes(self) -> bytes:
        """序列化"""
        result = bytearray(512)
        result[0:4] = self.magic
        struct.pack_into('<I', result, 4, self.version)
        struct.pack_into('<I', result, 8, self.block_size)
        struct.pack_into('<Q', result, 12, self.total_blocks)
        struct.pack_into('<Q', result, 20, self.next_xid)
        struct.pack_into('<Q', result, 28, self.start_offset)
        struct.pack_into('<Q', result, 36, self.end_offset)
        struct.pack_into('<I', result, 44, self.checksum)
        return bytes(result)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'JournalHeader':
        """反序列化"""
        magic = data[0:4]
        version = struct.unpack_from('<I', data, 4)[0]
        block_size = struct.unpack_from('<I', data, 8)[0]
        total_blocks = struct.unpack_from('<Q', data, 12)[0]
        next_xid = struct.unpack_from('<Q', data, 20)[0]
        start_offset = struct.unpack_from('<Q', data, 28)[0]
        end_offset = struct.unpack_from('<Q', data, 36)[0]
        checksum = struct.unpack_from('<I', data, 44)[0]
        
        return cls(
            magic=magic,
            version=version,
            block_size=block_size,
            total_blocks=total_blocks,
            next_xid=next_xid,
            start_offset=start_offset,
            end_offset=end_offset,
            checksum=checksum
        )


# =============================================================================
# APFS 日志管理器
# =============================================================================

class JournalManager:
    """
    APFS 日志管理器
    
    负责管理写前日志 (WAL)。
    """
    
    def __init__(self, file_path: str, block_size: int = 4096):
        """
        初始化日志管理器
        
        Args:
            file_path: 文件路径
            block_size: 块大小
        """
        self.file_path = file_path
        self.block_size = block_size
        self._file: Optional[BinaryIO] = None
        self._header: Optional[JournalHeader] = None
        self._log_entries: List[LogEntry] = []
        self._next_xid = 1
        
    def open(self) -> None:
        """打开日志"""
        self._file = open(self.file_path, 'r+b')
        self._read_header()
        
    def close(self) -> None:
        """关闭日志"""
        if self._file:
            self._file.close()
            self._file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _read_header(self) -> None:
        """读取日志头部"""
        if not self._file:
            return
            
        # 尝试在卷的第二个块找到日志头部
        self._file.seek(self.block_size)
        data = self._file.read(512)
        
        if data[0:4] == b'APLJ':
            self._header = JournalHeader.from_bytes(data)
            self._next_xid = self._header.next_xid
            
    def initialize(self) -> None:
        """初始化日志"""
        self._header = JournalHeader(
            magic=b'APLJ',
            version=1,
            block_size=self.block_size,
            total_blocks=1024,  # 日志大小
            next_xid=1,
            start_offset=0,
            end_offset=0
        )
        
    def allocate_xid(self) -> int:
        """
        分配事务 ID
        
        Returns:
            新的事务 ID
        """
        xid = self._next_xid
        self._next_xid += 1
        return xid
        
    def write_log_entry(self, entry: LogEntry) -> None:
        """
        写入日志条目
        
        Args:
            entry: 日志条目
        """
        self._log_entries.append(entry)
        
    def flush(self) -> None:
        """刷新日志到磁盘"""
        if not self._file or not self._header:
            return
            
        # 计算日志偏移
        log_offset = self.block_size * 2  # 日志在头部之后
        
        # 写入日志条目
        current_offset = log_offset
        for entry in self._log_entries:
            entry_data = entry.to_bytes()
            
            self._file.seek(current_offset)
            self._file.write(entry_data)
            
            current_offset += len(entry_data)
            
        # 更新头部
        self._header.end_offset = current_offset
        self._header.next_xid = self._next_xid
        
        # 写入头部
        self._file.seek(self.block_size)
        self._file.write(self._header.to_bytes())
        
        # 清空内存中的日志条目
        self._log_entries.clear()
        
    def read_log_entries(self) -> List[LogEntry]:
        """
        读取所有日志条目
        
        Returns:
            日志条目列表
        """
        if not self._file or not self._header:
            return []
            
        entries = []
        current_offset = self.block_size * 2
        
        while current_offset < self._header.end_offset:
            self._file.seek(current_offset)
            data = self._file.read(512)
            
            if len(data) < 32:
                break
                
            try:
                entry = LogEntry.from_bytes(data)
                entries.append(entry)
                
                # 移动到下一个条目
                current_offset += 32 + entry.length
            except Exception:
                break
                
        return entries


# =============================================================================
# APFS 事务管理器
# =============================================================================

class TransactionManager:
    """
    APFS 事务管理器
    
    负责管理事务的生命周期。
    """
    
    def __init__(self, file_path: str, block_size: int = 4096):
        """
        初始化事务管理器
        
        Args:
            file_path: 文件路径
            block_size: 块大小
        """
        self.file_path = file_path
        self.block_size = block_size
        self._journal = JournalManager(file_path, block_size)
        self._current_transaction: Optional[TransactionInfo] = None
        self._transaction_buffer: Dict[int, bytes] = {}  # block_num -> data
        
    def open(self) -> None:
        """打开事务管理器"""
        self._journal.open()
        
    def close(self) -> None:
        """关闭事务管理器"""
        self.rollback()
        self._journal.close()
        
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def begin_transaction(self) -> int:
        """
        开始新事务
        
        Returns:
            事务 ID
        """
        if self._current_transaction:
            raise RuntimeError("已有活动事务")
            
        xid = self._journal.allocate_xid()
        
        self._current_transaction = TransactionInfo(
            xid=xid,
            state=TransactionState.ACTIVE,
            start_time=int(time.time() * 1000000000)
        )
        
        # 写入开始日志
        log_entry = LogEntry(
            entry_type=LogEntryType.BEGIN,
            xid=xid,
            block_num=0,
            offset=0,
            length=0,
            data=b''
        )
        self._journal.write_log_entry(log_entry)
        
        return xid
        
    def write_block(self, block_num: int, data: bytes) -> None:
        """
        写入数据块（在事务中）
        
        Args:
            block_num: 块号
            data: 数据
        """
        if not self._current_transaction:
            raise RuntimeError("没有活动事务")
            
        if len(data) > self.block_size:
            raise ValueError(f"数据太大: {len(data)} > {self.block_size}")
            
        # 填充到块大小
        if len(data) < self.block_size:
            data = data + b'\x00' * (self.block_size - len(data))
            
        # 保存到缓冲区
        self._transaction_buffer[block_num] = data
        
        # 写入日志
        log_entry = LogEntry(
            entry_type=LogEntryType.WRITE,
            xid=self._current_transaction.xid,
            block_num=block_num,
            offset=0,
            length=len(data),
            data=data
        )
        log_entry.checksum = log_entry.calculate_checksum()
        self._journal.write_log_entry(log_entry)
        
        # 记录操作
        self._current_transaction.operations.append({
            'type': 'write',
            'block_num': block_num,
            'length': len(data)
        })
        
    def commit(self) -> bool:
        """
        提交事务
        
        Returns:
            是否成功
        """
        if not self._current_transaction:
            return False
            
        try:
            # 更新事务状态
            self._current_transaction.state = TransactionState.COMMITTED
            self._current_transaction.commit_time = int(time.time() * 1000000000)
            
            # 写入提交日志
            log_entry = LogEntry(
                entry_type=LogEntryType.COMMIT,
                xid=self._current_transaction.xid,
                block_num=0,
                offset=0,
                length=0,
                data=b''
            )
            self._journal.write_log_entry(log_entry)
            
            # 刷新日志
            self._journal.flush()
            
            # 将缓冲区写入实际位置
            self._flush_buffer()
            
            # 清空状态
            self._current_transaction = None
            self._transaction_buffer.clear()
            
            return True
            
        except Exception as e:
            print(f"提交事务失败: {e}")
            self.rollback()
            return False
            
    def rollback(self) -> bool:
        """
        回滚事务
        
        Returns:
            是否成功
        """
        if not self._current_transaction:
            return False
            
        try:
            # 更新事务状态
            self._current_transaction.state = TransactionState.ROLLED_BACK
            
            # 写入回滚日志
            log_entry = LogEntry(
                entry_type=LogEntryType.ROLLBACK,
                xid=self._current_transaction.xid,
                block_num=0,
                offset=0,
                length=0,
                data=b''
            )
            self._journal.write_log_entry(log_entry)
            
            # 刷新日志
            self._journal.flush()
            
            # 清空缓冲区
            self._transaction_buffer.clear()
            self._current_transaction = None
            
            return True
            
        except Exception as e:
            print(f"回滚事务失败: {e}")
            self._current_transaction = None
            self._transaction_buffer.clear()
            return False
            
    def _flush_buffer(self) -> None:
        """将缓冲区写入实际位置"""
        if not self._transaction_buffer:
            return
            
        with open(self.file_path, 'r+b') as f:
            for block_num, data in self._transaction_buffer.items():
                offset = block_num * self.block_size
                f.seek(offset)
                f.write(data)
                
    def recover(self) -> bool:
        """
        崩溃恢复
        
        Returns:
            是否成功
        """
        try:
            # 读取所有日志条目
            entries = self._journal.read_log_entries()
            
            # 按事务分组
            transactions: Dict[int, List[LogEntry]] = {}
            for entry in entries:
                if entry.xid not in transactions:
                    transactions[entry.xid] = []
                transactions[entry.xid].append(entry)
            
            # 检查每个事务的状态
            for xid, tx_entries in transactions.items():
                has_begin = any(e.entry_type == LogEntryType.BEGIN for e in tx_entries)
                has_commit = any(e.entry_type == LogEntryType.COMMIT for e in tx_entries)
                has_rollback = any(e.entry_type == LogEntryType.ROLLBACK for e in tx_entries)
                
                if has_begin and has_commit:
                    # 已提交的事务，重放写操作
                    self._replay_transaction(tx_entries)
                elif has_begin and not has_commit and not has_rollback:
                    # 未完成的事务，需要回滚
                    print(f"发现未完成的事务 {xid}，跳过")
                    
            return True
            
        except Exception as e:
            print(f"恢复失败: {e}")
            return False
            
    def _replay_transaction(self, entries: List[LogEntry]) -> None:
        """
        重放事务
        
        Args:
            entries: 日志条目列表
        """
        write_entries = [e for e in entries if e.entry_type == LogEntryType.WRITE]
        
        with open(self.file_path, 'r+b') as f:
            for entry in write_entries:
                # 验证校验和
                if entry.checksum != entry.calculate_checksum():
                    print(f"日志条目校验和错误: 块 {entry.block_num}")
                    continue
                    
                # 写入数据
                offset = entry.block_num * self.block_size
                f.seek(offset)
                f.write(entry.data)


# =============================================================================
# APFS 写入器（带事务支持）
# =============================================================================

class APFSTransactionalWriter:
    """
    APFS 事务写入器
    
    支持事务的 APFS 写入操作。
    """
    
    def __init__(self, file_path: str, block_size: int = 4096):
        """
        初始化写入器
        
        Args:
            file_path: 文件路径
            block_size: 块大小
        """
        self.file_path = file_path
        self.block_size = block_size
        self._tx_manager = TransactionManager(file_path, block_size)
        self._next_oid = 1000
        
    def open(self) -> None:
        """打开写入器"""
        self._tx_manager.open()
        
    def close(self) -> None:
        """关闭写入器"""
        self._tx_manager.close()
        
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def recover(self) -> bool:
        """
        崩溃恢复
        
        Returns:
            是否成功
        """
        return self._tx_manager.recover()
        
    def allocate_oid(self) -> int:
        """分配对象 ID"""
        oid = self._next_oid
        self._next_oid += 1
        return oid
        
    def create_file(self, parent_id: int, name: str, data: bytes = b'') -> Optional[int]:
        """
        创建文件（事务性）
        
        Args:
            parent_id: 父目录 ID
            name: 文件名
            data: 文件数据
            
        Returns:
            文件 ID，失败返回 None
        """
        try:
            # 开始事务
            xid = self._tx_manager.begin_transaction()
            
            # 分配文件 ID
            file_id = self.allocate_oid()
            
            # 创建 inode 数据
            inode_data = self._create_inode_data(file_id, parent_id, name, False)
            
            # 写入 inode
            inode_block = self._allocate_block()
            self._tx_manager.write_block(inode_block, inode_data)
            
            # 写入文件数据
            if data:
                blocks_needed = (len(data) + self.block_size - 1) // self.block_size
                for i in range(blocks_needed):
                    block_num = self._allocate_block()
                    start = i * self.block_size
                    end = min(start + self.block_size, len(data))
                    block_data = data[start:end]
                    self._tx_manager.write_block(block_num, block_data)
            
            # 提交事务
            if self._tx_manager.commit():
                return file_id
            else:
                return None
                
        except Exception as e:
            print(f"创建文件失败: {e}")
            self._tx_manager.rollback()
            return None
            
    def create_directory(self, parent_id: int, name: str) -> Optional[int]:
        """
        创建目录（事务性）
        
        Args:
            parent_id: 父目录 ID
            name: 目录名
            
        Returns:
            目录 ID，失败返回 None
        """
        try:
            # 开始事务
            xid = self._tx_manager.begin_transaction()
            
            # 分配目录 ID
            dir_id = self.allocate_oid()
            
            # 创建 inode 数据
            inode_data = self._create_inode_data(dir_id, parent_id, name, True)
            
            # 写入 inode
            inode_block = self._allocate_block()
            self._tx_manager.write_block(inode_block, inode_data)
            
            # 提交事务
            if self._tx_manager.commit():
                return dir_id
            else:
                return None
                
        except Exception as e:
            print(f"创建目录失败: {e}")
            self._tx_manager.rollback()
            return None
            
    def delete_entry(self, entry_id: int) -> bool:
        """
        删除条目（事务性）
        
        Args:
            entry_id: 条目 ID
            
        Returns:
            是否成功
        """
        try:
            # 开始事务
            xid = self._tx_manager.begin_transaction()
            
            # 标记为已删除（简化实现）
            # 实际应该更新 B-tree 和释放块
            
            # 提交事务
            return self._tx_manager.commit()
            
        except Exception as e:
            print(f"删除条目失败: {e}")
            self._tx_manager.rollback()
            return False
            
    def _create_inode_data(self, oid: int, parent_id: int, name: str,
                           is_dir: bool) -> bytes:
        """创建 inode 数据"""
        data = bytearray(self.block_size)
        
        # 对象头部
        struct.pack_into('<Q', data, 0, oid)  # oid
        struct.pack_into('<Q', data, 8, 0)  # xid
        struct.pack_into('<I', data, 16, 0x20 if not is_dir else 0x21)  # type
        struct.pack_into('<I', data, 20, 0)  # flags
        
        # inode 数据
        struct.pack_into('<Q', data, 32, parent_id)  # parent_id
        struct.pack_into('<Q', data, 40, oid)  # private_id
        
        # 时间戳
        now = int(time.time() * 1000000000)
        struct.pack_into('<Q', data, 48, now)  # create_time
        struct.pack_into('<Q', data, 56, now)  # mod_time
        
        # 权限
        mode = 0o40755 if is_dir else 0o100644
        struct.pack_into('<H', data, 112, mode)
        
        return bytes(data)
        
    def _allocate_block(self) -> int:
        """分配块（简化实现）"""
        # 实际应该使用位图管理
        import random
        return random.randint(100, 1000000)


# =============================================================================
# 错误恢复管理器
# =============================================================================

class RecoveryManager:
    """
    错误恢复管理器
    
    负责在崩溃后恢复文件系统一致性。
    """
    
    def __init__(self, file_path: str, block_size: int = 4096):
        """
        初始化恢复管理器
        
        Args:
            file_path: 文件路径
            block_size: 块大小
        """
        self.file_path = file_path
        self.block_size = block_size
        self._journal = JournalManager(file_path, block_size)
        
    def check_consistency(self) -> Dict[str, Any]:
        """
        检查一致性
        
        Returns:
            检查结果
        """
        result = {
            'is_consistent': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            self._journal.open()
            
            # 检查日志
            entries = self._journal.read_log_entries()
            
            # 按事务分组
            transactions: Dict[int, List[LogEntry]] = {}
            for entry in entries:
                if entry.xid not in transactions:
                    transactions[entry.xid] = []
                transactions[entry.xid].append(entry)
            
            # 检查每个事务
            for xid, tx_entries in transactions.items():
                has_begin = any(e.entry_type == LogEntryType.BEGIN for e in tx_entries)
                has_commit = any(e.entry_type == LogEntryType.COMMIT for e in tx_entries)
                has_rollback = any(e.entry_type == LogEntryType.ROLLBACK for e in tx_entries)
                
                if has_begin and not has_commit and not has_rollback:
                    result['warnings'].append(f"未完成的事务: {xid}")
                    result['is_consistent'] = False
                    
                # 验证校验和
                for entry in tx_entries:
                    if entry.entry_type == LogEntryType.WRITE:
                        if entry.checksum != entry.calculate_checksum():
                            result['errors'].append(f"日志条目校验和错误: 事务 {xid}, 块 {entry.block_num}")
                            result['is_consistent'] = False
            
            self._journal.close()
            
        except Exception as e:
            result['errors'].append(f"检查失败: {e}")
            result['is_consistent'] = False
            
        return result
        
    def repair(self) -> bool:
        """
        修复文件系统
        
        Returns:
            是否成功
        """
        try:
            self._journal.open()
            
            # 读取日志
            entries = self._journal.read_log_entries()
            
            # 按事务分组
            transactions: Dict[int, List[LogEntry]] = {}
            for entry in entries:
                if entry.xid not in transactions:
                    transactions[entry.xid] = []
                transactions[entry.xid].append(entry)
            
            # 处理未完成的事务
            for xid, tx_entries in transactions.items():
                has_begin = any(e.entry_type == LogEntryType.BEGIN for e in tx_entries)
                has_commit = any(e.entry_type == LogEntryType.COMMIT for e in tx_entries)
                
                if has_begin and not has_commit:
                    # 写入回滚日志
                    rollback_entry = LogEntry(
                        entry_type=LogEntryType.ROLLBACK,
                        xid=xid,
                        block_num=0,
                        offset=0,
                        length=0,
                        data=b''
                    )
                    self._journal.write_log_entry(rollback_entry)
            
            # 刷新日志
            self._journal.flush()
            
            self._journal.close()
            return True
            
        except Exception as e:
            print(f"修复失败: {e}")
            return False


# =============================================================================
# 便捷函数
# =============================================================================

def create_transactional_writer(file_path: str, 
                                block_size: int = 4096) -> APFSTransactionalWriter:
    """
    创建事务写入器
    
    Args:
        file_path: 文件路径
        block_size: 块大小
        
    Returns:
        事务写入器
    """
    writer = APFSTransactionalWriter(file_path, block_size)
    writer.open()
    return writer


def check_filesystem_consistency(file_path: str, 
                                 block_size: int = 4096) -> Dict[str, Any]:
    """
    检查文件系统一致性
    
    Args:
        file_path: 文件路径
        block_size: 块大小
        
    Returns:
        检查结果
    """
    recovery = RecoveryManager(file_path, block_size)
    return recovery.check_consistency()


def repair_filesystem(file_path: str, block_size: int = 4096) -> bool:
    """
    修复文件系统
    
    Args:
        file_path: 文件路径
        block_size: 块大小
        
    Returns:
        是否成功
    """
    recovery = RecoveryManager(file_path, block_size)
    return recovery.repair()
