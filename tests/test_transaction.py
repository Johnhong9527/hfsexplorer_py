#!/usr/bin/env python3
"""
APFS 事务管理和密钥包解析测试

测试事务管理、日志、崩溃恢复和密钥包解析功能。
"""

import pytest
import sys
import os
import struct
import tempfile

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestTransactionManager:
    """测试事务管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.apfs.transaction import TransactionManager, JournalManager
        assert TransactionManager is not None
        assert JournalManager is not None
    
    def test_journal_header(self):
        """测试日志头部"""
        from src.core.apfs.transaction import JournalHeader
        
        header = JournalHeader(
            magic=b'APLJ',
            version=1,
            block_size=4096,
            total_blocks=1024,
            next_xid=1,
            start_offset=0,
            end_offset=0
        )
        
        # 序列化
        data = header.to_bytes()
        assert len(data) == 512
        
        # 反序列化
        header2 = JournalHeader.from_bytes(data)
        assert header2.magic == b'APLJ'
        assert header2.version == 1
        assert header2.block_size == 4096
    
    def test_log_entry(self):
        """测试日志条目"""
        from src.core.apfs.transaction import LogEntry, LogEntryType
        
        entry = LogEntry(
            entry_type=LogEntryType.WRITE,
            xid=1,
            block_num=100,
            offset=0,
            length=4096,
            data=b'\x42' * 4096
        )
        
        # 计算校验和
        checksum = entry.calculate_checksum()
        assert checksum != 0
        
        # 序列化
        data = entry.to_bytes()
        assert len(data) > 0
        
        # 反序列化
        entry2 = LogEntry.from_bytes(data)
        assert entry2.entry_type == LogEntryType.WRITE
        assert entry2.xid == 1
        assert entry2.block_num == 100
    
    def test_transaction_info(self):
        """测试事务信息"""
        from src.core.apfs.transaction import TransactionInfo, TransactionState
        
        tx = TransactionInfo(
            xid=1,
            state=TransactionState.ACTIVE,
            start_time=1000000000
        )
        
        # 序列化
        data = tx.to_bytes()
        assert len(data) > 0
        
        # 反序列化
        tx2 = TransactionInfo.from_bytes(data)
        assert tx2.xid == 1
        assert tx2.state == TransactionState.ACTIVE
    
    def test_transaction_manager_create(self):
        """测试创建事务管理器"""
        from src.core.apfs.transaction import TransactionManager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 创建测试文件
            f.write(b'\x00' * (1024 * 1024))  # 1MB
            f.flush()
            
            manager = TransactionManager(f.name, 4096)
            manager.open()
            
            assert manager is not None
            
            manager.close()
            os.unlink(f.name)


class TestJournalManager:
    """测试日志管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.apfs.transaction import JournalManager
        assert JournalManager is not None
    
    def test_initialize(self):
        """测试初始化日志"""
        from src.core.apfs.transaction import JournalManager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 创建测试文件
            f.write(b'\x00' * (1024 * 1024))  # 1MB
            f.flush()
            
            journal = JournalManager(f.name, 4096)
            journal.open()
            journal.initialize()
            
            assert journal._header is not None
            assert journal._header.magic == b'APLJ'
            
            journal.close()
            os.unlink(f.name)
    
    def test_allocate_xid(self):
        """测试分配事务 ID"""
        from src.core.apfs.transaction import JournalManager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            journal = JournalManager(f.name, 4096)
            journal.open()
            journal.initialize()
            
            xid1 = journal.allocate_xid()
            xid2 = journal.allocate_xid()
            xid3 = journal.allocate_xid()
            
            assert xid1 == 1
            assert xid2 == 2
            assert xid3 == 3
            
            journal.close()
            os.unlink(f.name)


class TestRecoveryManager:
    """测试恢复管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.apfs.transaction import RecoveryManager
        assert RecoveryManager is not None
    
    def test_check_consistency(self):
        """测试一致性检查"""
        from src.core.apfs.transaction import RecoveryManager
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * (1024 * 1024))
            f.flush()
            
            recovery = RecoveryManager(f.name, 4096)
            result = recovery.check_consistency()
            
            assert 'is_consistent' in result
            assert 'errors' in result
            assert 'warnings' in result
            
            os.unlink(f.name)


class TestKeybagParser:
    """测试密钥包解析器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.keybag import KeybagParser, KeybagInfo
        assert KeybagParser is not None
        assert KeybagInfo is not None
    
    def test_keybag_header(self):
        """测试密钥包头部"""
        from src.core.crypto.keybag import KeybagHeader, APFS_KEYBAG_MAGIC
        
        header = KeybagHeader(
            magic=APFS_KEYBAG_MAGIC,
            version=1,
            count=2,
            salt=b'\x00' * 32,
            iterations=10000,
            uuid=b'\x00' * 16
        )
        
        # 序列化
        data = header.to_bytes()
        assert len(data) == 256
        
        # 反序列化
        header2 = KeybagHeader.from_bytes(data)
        assert header2.magic == APFS_KEYBAG_MAGIC
        assert header2.version == 1
        assert header2.count == 2
    
    def test_key_entry(self):
        """测试密钥条目"""
        from src.core.crypto.keybag import KeyEntry, KeyType, KeyTag
        
        entry = KeyEntry(
            key_class=1,
            key_type=KeyType.USER_PASSWORD,
            uuid=b'\x00' * 16,
            tag=KeyTag.VOLUME_KEY,
            key_data=b'\x00' * 32,
            wrapped_key=b'\x00' * 32
        )
        
        # 序列化
        data = entry.to_bytes()
        assert len(data) > 0
        
        # 反序列化
        entry2 = KeyEntry.from_bytes(data)
        assert entry2.key_type == KeyType.USER_PASSWORD
        assert entry2.tag == KeyTag.VOLUME_KEY
    
    def test_parse_keybag(self):
        """测试解析密钥包"""
        from src.core.crypto.keybag import KeybagParser, KeybagHeader, APFS_KEYBAG_MAGIC
        
        parser = KeybagParser()
        
        # 创建测试数据
        data = bytearray(512)
        data[0:4] = APFS_KEYBAG_MAGIC
        struct.pack_into('<I', data, 4, 1)  # version
        struct.pack_into('<I', data, 8, 0)  # count
        struct.pack_into('<I', data, 44, 10000)  # iterations
        
        result = parser.parse(bytes(data))
        assert result is not None
        assert result.header.magic == APFS_KEYBAG_MAGIC


class TestKeyDerivation:
    """测试密钥派生"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.keybag import KeyDerivation
        assert KeyDerivation is not None
    
    def test_derive_kek(self):
        """测试派生 KEK"""
        from src.core.crypto.keybag import KeyDerivation
        
        deriver = KeyDerivation()
        
        password = "test_password"
        salt = os.urandom(32)
        
        kek = deriver.derive_kek(password, salt, iterations=10000)
        
        assert len(kek) == 32
        assert kek != b'\x00' * 32
    
    def test_derive_key(self):
        """测试派生密钥"""
        from src.core.crypto.keybag import KeyDerivation
        
        deriver = KeyDerivation()
        
        password = "test_password"
        salt = os.urandom(32)
        
        key = deriver.derive_key(password, salt, iterations=10000)
        
        assert len(key) == 32
        assert key != b'\x00' * 32


class TestKeyUnwrap:
    """测试密钥解包"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.keybag import KeyUnwrap
        assert KeyUnwrap is not None
    
    def test_unwrap_key(self):
        """测试解包密钥"""
        from src.core.crypto.keybag import KeyUnwrap
        
        unwrapper = KeyUnwrap()
        
        # 创建测试数据
        wrapped_key = os.urandom(32)
        kek = os.urandom(32)
        
        # 解包
        unwrapped = unwrapper.unwrap(wrapped_key, kek)
        
        assert unwrapped is not None
        assert len(unwrapped) == 32
    
    def test_wrap_unwrap_roundtrip(self):
        """测试包装和解包往返"""
        from src.core.crypto.keybag import KeyUnwrap
        
        unwrapper = KeyUnwrap()
        
        # 创建测试数据
        key = os.urandom(32)
        kek = os.urandom(32)
        
        # 包装
        wrapped = unwrapper.wrap(key, kek)
        assert wrapped is not None
        
        # 解包
        unwrapped = unwrapper.unwrap(wrapped, kek)
        assert unwrapped is not None


class TestKeyValidator:
    """测试密钥验证"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.keybag import KeyValidator
        assert KeyValidator is not None
    
    def test_validate_kek(self):
        """测试验证 KEK"""
        from src.core.crypto.keybag import KeyValidator
        
        validator = KeyValidator()
        
        # 有效密钥
        assert validator.validate_kek(os.urandom(32)) == True
        
        # 无效密钥
        assert validator.validate_kek(b'') == False
        assert validator.validate_kek(b'\x00' * 32) == False
    
    def test_validate_volume_key(self):
        """测试验证卷密钥"""
        from src.core.crypto.keybag import KeyValidator
        
        validator = KeyValidator()
        
        # 有效密钥
        assert validator.validate_volume_key(os.urandom(32)) == True
        assert validator.validate_volume_key(os.urandom(64)) == True
        
        # 无效密钥
        assert validator.validate_volume_key(b'') == False
        assert validator.validate_volume_key(b'\x00' * 32) == False


class TestKeyManager:
    """测试密钥管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.keybag import KeyManager
        assert KeyManager is not None
    
    def test_create_manager(self):
        """测试创建管理器"""
        from src.core.crypto.keybag import KeyManager
        
        manager = KeyManager()
        assert manager is not None
        assert manager.is_unlocked() == False


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_parse_keybag(self):
        """测试解析密钥包"""
        from src.core.crypto.keybag import parse_keybag, APFS_KEYBAG_MAGIC
        
        # 创建测试数据
        data = bytearray(512)
        data[0:4] = APFS_KEYBAG_MAGIC
        struct.pack_into('<I', data, 4, 1)  # version
        struct.pack_into('<I', data, 8, 0)  # count
        
        result = parse_keybag(bytes(data))
        assert result is not None
    
    def test_derive_key(self):
        """测试派生密钥"""
        from src.core.crypto.keybag import derive_key
        
        key = derive_key("password", os.urandom(32), 10000)
        assert len(key) == 32


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
