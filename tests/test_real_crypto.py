#!/usr/bin/env python3
"""
真正的 AES-XTS 加密测试

测试使用 cryptography 库实现的 AES-XTS 加密功能。

注意：这些测试需要安装 cryptography 库。
如果未安装，测试将被跳过。
"""

import pytest
import sys
import os
import struct
import tempfile

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 检查 cryptography 是否可用
try:
    from src.core.crypto.real_crypto import CRYPTOGRAPHY_AVAILABLE
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

# 跳过装饰器
requires_cryptography = pytest.mark.skipif(
    not CRYPTOGRAPHY_AVAILABLE,
    reason="cryptography 库未安装"
)


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestAESXTSCipher:
    """测试 AES-XTS 加密器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import AESXTSCipher, CRYPTOGRAPHY_AVAILABLE
        assert AESXTSCipher is not None
        assert CRYPTOGRAPHY_AVAILABLE == True
    
    def test_encrypt_decrypt_block(self):
        """测试加密和解密数据块"""
        from src.core.crypto.real_crypto import AESXTSCipher
        import os
        
        cipher = AESXTSCipher()
        
        # 生成随机密钥（64字节用于 AES-256-XTS）
        key = os.urandom(64)
        cipher.set_key(key)
        
        # 测试数据
        data = b'Hello, World! This is a test block.' + b'\x00' * (4096 - 35)
        
        # 加密
        encrypted = cipher.encrypt_block(0, data)
        assert encrypted != data
        assert len(encrypted) == 4096
        
        # 解密
        decrypted = cipher.decrypt_block(0, encrypted)
        assert decrypted == data
    
    def test_different_blocks(self):
        """测试不同块号的加密"""
        from src.core.crypto.real_crypto import AESXTSCipher
        import os
        
        cipher = AESXTSCipher()
        key = os.urandom(64)
        cipher.set_key(key)
        
        data = b'\x42' * 4096
        
        # 不同块号应该产生不同的密文
        encrypted0 = cipher.encrypt_block(0, data)
        encrypted1 = cipher.encrypt_block(1, data)
        encrypted2 = cipher.encrypt_block(2, data)
        
        assert encrypted0 != encrypted1
        assert encrypted1 != encrypted2
        assert encrypted0 != encrypted2
        
        # 但解密后应该得到相同的数据
        assert cipher.decrypt_block(0, encrypted0) == data
        assert cipher.decrypt_block(1, encrypted1) == data
        assert cipher.decrypt_block(2, encrypted2) == data
    
    def test_large_data(self):
        """测试大数据块"""
        from src.core.crypto.real_crypto import AESXTSCipher
        import os
        
        cipher = AESXTSCipher()
        key = os.urandom(64)
        cipher.set_key(key)
        
        # 生成大数据
        data = os.urandom(4096 * 10)
        
        # 分块加密和解密
        encrypted = b''
        for i in range(10):
            block = data[i * 4096:(i + 1) * 4096]
            encrypted += cipher.encrypt_block(i, block)
        
        decrypted = b''
        for i in range(10):
            block = encrypted[i * 4096:(i + 1) * 4096]
            decrypted += cipher.decrypt_block(i, block)
        
        assert decrypted == data


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestKeyDeriver:
    """测试密钥派生器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import KeyDeriver
        assert KeyDeriver is not None
    
    def test_derive_key(self):
        """测试密钥派生"""
        from src.core.crypto.real_crypto import KeyDeriver
        
        deriver = KeyDeriver()
        
        password = "test_password"
        salt = os.urandom(32)
        
        key = deriver.derive_key(password, salt, iterations=10000)
        
        assert len(key) == 32
        assert key != b'\x00' * 32
    
    def test_same_password_same_salt(self):
        """测试相同密码和盐值产生相同密钥"""
        from src.core.crypto.real_crypto import KeyDeriver
        
        deriver = KeyDeriver()
        
        password = "test_password"
        salt = os.urandom(32)
        
        key1 = deriver.derive_key(password, salt, iterations=10000)
        key2 = deriver.derive_key(password, salt, iterations=10000)
        
        assert key1 == key2
    
    def test_different_password(self):
        """测试不同密码产生不同密钥"""
        from src.core.crypto.real_crypto import KeyDeriver
        
        deriver = KeyDeriver()
        
        salt = os.urandom(32)
        
        key1 = deriver.derive_key("password1", salt, iterations=10000)
        key2 = deriver.derive_key("password2", salt, iterations=10000)
        
        assert key1 != key2


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestKeyUnwrapper:
    """测试密钥解包器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import KeyUnwrapper
        assert KeyUnwrapper is not None
    
    def test_unwrap_key(self):
        """测试密钥解包"""
        from src.core.crypto.real_crypto import KeyUnwrapper
        
        unwrapper = KeyUnwrapper()
        
        # 创建测试数据
        wrapped_key = os.urandom(32)
        kek = os.urandom(32)
        
        # 解包
        unwrapped = unwrapper.unwrap_key(wrapped_key, kek)
        
        assert unwrapped is not None
        assert len(unwrapped) == 32


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestCryptoManager:
    """测试加密管理器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import CryptoManager
        assert CryptoManager is not None
    
    def test_encrypt_decrypt_without_key(self):
        """测试无密钥时的加密解密"""
        from src.core.crypto.real_crypto import CryptoManager
        
        manager = CryptoManager()
        
        data = b'\x42' * 4096
        
        # 无密钥时应该返回原始数据
        assert manager.encrypt_block(0, data) == data
        assert manager.decrypt_block(0, data) == data


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestAPFSEncryptedReader:
    """测试 APFS 加密卷读取器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import APFSEncryptedReader
        assert APFSEncryptedReader is not None
    
    def test_open_non_encrypted(self, tmp_path):
        """测试打开非加密卷"""
        from src.core.crypto.real_crypto import APFSEncryptedReader
        
        test_file = tmp_path / "test.img"
        test_file.write_bytes(b'\x00' * 4096)
        
        reader = APFSEncryptedReader(str(test_file))
        result = reader.open()
        
        assert result == False
        assert reader.is_encrypted() == False
        
        reader.close()


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestCoreStorageEncryptedReader:
    """测试 CoreStorage 加密卷读取器"""
    
    def test_import(self):
        """测试导入"""
        from src.core.crypto.real_crypto import CoreStorageEncryptedReader
        assert CoreStorageEncryptedReader is not None
    
    def test_open_non_encrypted(self, tmp_path):
        """测试打开非加密卷"""
        from src.core.crypto.real_crypto import CoreStorageEncryptedReader
        
        test_file = tmp_path / "test.img"
        test_file.write_bytes(b'\x00' * 4096)
        
        reader = CoreStorageEncryptedReader(str(test_file))
        result = reader.open()
        
        assert result == False
        assert reader.is_encrypted() == False
        
        reader.close()


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="cryptography 库未安装")
class TestEncryptionAvailability:
    """测试加密功能可用性"""
    
    def test_cryptography_available(self):
        """测试 cryptography 库是否可用"""
        from src.core.crypto.real_crypto import is_encryption_available
        assert is_encryption_available() == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
