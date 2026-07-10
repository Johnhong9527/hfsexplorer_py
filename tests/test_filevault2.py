"""
FileVault 2 解密测试

测试 CoreStorage 和 FileVault 2 加密卷的解析和解密功能。
"""

import struct
import unittest
import io
from src.core.crypto import (
    AESXTS,
    AESKeyWrap,
    PBKDF2Deriver,
    EncryptedVolumeHeader,
    CryptoError,
)
from src.core.crypto.encrypted_volume import (
    KeybagEntryType,
    KeybagEntry,
    Keybag,
    EncryptedVolume,
    EncryptedVolumeParser,
)
from src.core.corestorage import (
    CoreStorageHeader,
    CoreStorageVolumeType,
    is_corestorage,
    find_corestorage_keybag,
)


class TestCryptoAlgorithms(unittest.TestCase):
    """测试加密算法"""
    
    def test_aes_xts_encrypt_decrypt(self):
        """测试 AES-XTS 加密和解密"""
        # 生成测试密钥（32 字节 = AES-128-XTS）
        key = b'\x00' * 32
        
        # 创建 AES-XTS 实例
        xts = AESXTS(key)
        
        # 测试数据
        data = b'\x01' * 512
        sector_number = 42
        
        # 加密
        encrypted = xts.encrypt_sector(data, sector_number)
        
        # 解密
        decrypted = xts.decrypt_sector(encrypted, sector_number)
        
        # 验证
        self.assertEqual(data, decrypted)
        self.assertNotEqual(data, encrypted)
    
    def test_aes_xts_256(self):
        """测试 AES-256-XTS"""
        # 生成测试密钥（64 字节 = AES-256-XTS）
        key = b'\x01' * 64
        
        # 创建 AES-XTS 实例
        xts = AESXTS(key)
        
        # 测试数据
        data = b'\x02' * 256
        sector_number = 100
        
        # 加密
        encrypted = xts.encrypt_sector(data, sector_number)
        
        # 解密
        decrypted = xts.decrypt_sector(encrypted, sector_number)
        
        # 验证
        self.assertEqual(data, decrypted)
    
    def test_aes_key_wrap(self):
        """测试 AES Key Wrap"""
        # KEK（密钥加密密钥）
        kek = b'\x00' * 16
        
        # 要包装的密钥
        key_to_wrap = b'\x01' * 16
        
        # 包装
        wrapper = AESKeyWrap(kek)
        wrapped = wrapper.wrap(key_to_wrap)
        
        # 解包
        unwrapped = wrapper.unwrap(wrapped)
        
        # 验证
        self.assertEqual(key_to_wrap, unwrapped)
    
    def test_pbkdf2_derive(self):
        """测试 PBKDF2 密钥派生"""
        password = b'testpassword'
        salt = b'\x00' * 16
        iterations = 1000
        
        # 派生密钥
        key = PBKDF2Deriver.derive(password, salt, iterations, key_length=32, hash_algo='sha256')
        
        # 验证长度
        self.assertEqual(len(key), 32)
        
        # 验证确定性
        key2 = PBKDF2Deriver.derive(password, salt, iterations, key_length=32, hash_algo='sha256')
        self.assertEqual(key, key2)


class TestCoreStorageHeader(unittest.TestCase):
    """测试 CoreStorage 头部解析"""
    
    def test_parse_corestorage_header(self):
        """测试解析 CoreStorage 头部"""
        # 创建一个模拟的 CoreStorage 头部
        data = bytearray(512)
        
        # 设置签名 'CS' 在偏移 88
        data[88:90] = b'CS'
        
        # 设置版本
        struct.pack_into('>I', data, 90, 1)
        
        # 设置卷类型（加密）
        struct.pack_into('>I', data, 94, CoreStorageVolumeType.ENCRYPTED)
        
        # 设置 UUID（16字节）
        data[98:114] = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10'
        
        # 设置块大小
        struct.pack_into('>I', data, 114, 4096)
        
        # 设置总块数
        struct.pack_into('>Q', data, 118, 1000000)
        
        # 设置空闲块数
        struct.pack_into('>Q', data, 126, 500000)
        
        # 解析
        header = CoreStorageHeader.from_bytes(bytes(data))
        
        # 验证
        self.assertTrue(header.is_valid)
        self.assertTrue(header.is_encrypted)
        self.assertEqual(header.version, 1)
        self.assertEqual(header.block_size, 4096)
        self.assertEqual(header.total_blocks, 1000000)
        self.assertEqual(header.free_blocks, 500000)
    
    def test_is_corestorage(self):
        """测试检查是否是 CoreStorage"""
        # 创建有效的 CoreStorage 数据
        data = bytearray(512)
        data[88:90] = b'CS'
        
        stream = io.BytesIO(bytes(data))
        self.assertTrue(is_corestorage(stream))
        
        # 创建无效的数据
        data[88:90] = b'XX'
        stream = io.BytesIO(bytes(data))
        self.assertFalse(is_corestorage(stream))


class TestKeybag(unittest.TestCase):
    """测试密钥包解析"""
    
    def _create_keybag_data(self, entries_data):
        """创建密钥包数据"""
        data = bytearray()
        
        for entry in entries_data:
            entry_type = entry['type']
            uuid = entry.get('uuid', b'\x00' * 16)
            wrapped_key = entry.get('wrapped_key', b'\x00' * 40)
            iterations = entry.get('iterations', 0)
            salt = entry.get('salt', b'\x00' * 16)
            
            if entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK:
                # KEK 条目：type(2) + length(2) + uuid(16) + iterations(8) + salt(16) + wrapped_key(40)
                entry_length = 2 + 2 + 16 + 8 + 16 + 40
                data.extend(struct.pack('>HH', entry_type, entry_length))
                data.extend(uuid)
                data.extend(struct.pack('>Q', iterations))
                data.extend(salt)
                data.extend(wrapped_key)
            elif entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK:
                # VEK 条目：type(2) + length(2) + uuid(16) + wrapped_key(40)
                entry_length = 2 + 2 + 16 + 40
                data.extend(struct.pack('>HH', entry_type, entry_length))
                data.extend(uuid)
                data.extend(wrapped_key)
        
        return bytes(data)
    
    def test_parse_kek_entry(self):
        """测试解析 KEK 条目"""
        kek_uuid = b'\x01' * 16
        kek_wrapped = b'\x02' * 40
        kek_iterations = 10000
        kek_salt = b'\x03' * 16
        
        data = self._create_keybag_data([{
            'type': KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK,
            'uuid': kek_uuid,
            'wrapped_key': kek_wrapped,
            'iterations': kek_iterations,
            'salt': kek_salt,
        }])
        
        keybag = Keybag(data)
        
        # 验证解析
        self.assertEqual(len(keybag.entries), 1)
        
        kek_entry = keybag.get_kek_entry()
        self.assertIsNotNone(kek_entry)
        self.assertEqual(kek_entry.uuid, kek_uuid)
        self.assertEqual(kek_entry.wrapped_key, kek_wrapped)
        self.assertEqual(kek_entry.iterations, kek_iterations)
        self.assertEqual(kek_entry.salt, kek_salt)
    
    def test_parse_vek_entry(self):
        """测试解析 VEK 条目"""
        vek_uuid = b'\x04' * 16
        vek_wrapped = b'\x05' * 40
        
        data = self._create_keybag_data([{
            'type': KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK,
            'uuid': vek_uuid,
            'wrapped_key': vek_wrapped,
        }])
        
        keybag = Keybag(data)
        
        # 验证解析
        self.assertEqual(len(keybag.entries), 1)
        
        vek_entry = keybag.get_vek_entry()
        self.assertIsNotNone(vek_entry)
        self.assertEqual(vek_entry.uuid, vek_uuid)
        self.assertEqual(vek_entry.wrapped_key, vek_wrapped)
    
    def test_parse_multiple_entries(self):
        """测试解析多个条目"""
        kek_uuid = b'\x01' * 16
        kek_wrapped = b'\x02' * 40
        kek_iterations = 10000
        kek_salt = b'\x03' * 16
        
        vek_uuid = b'\x04' * 16
        vek_wrapped = b'\x05' * 40
        
        data = self._create_keybag_data([
            {
                'type': KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK,
                'uuid': kek_uuid,
                'wrapped_key': kek_wrapped,
                'iterations': kek_iterations,
                'salt': kek_salt,
            },
            {
                'type': KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK,
                'uuid': vek_uuid,
                'wrapped_key': vek_wrapped,
            },
        ])
        
        keybag = Keybag(data)
        
        # 验证解析
        self.assertEqual(len(keybag.entries), 2)
        
        kek_entry = keybag.get_kek_entry()
        self.assertIsNotNone(kek_entry)
        
        vek_entry = keybag.get_vek_entry()
        self.assertIsNotNone(vek_entry)


class TestEncryptedVolumeParser(unittest.TestCase):
    """测试加密卷解析器"""
    
    def _create_test_volume(self, password='testpassword'):
        """创建测试用的加密卷"""
        # 生成密钥
        kek_salt = b'\x01' * 16
        kek_iterations = 1000
        
        # 从密码派生 KEK
        derived_key = PBKDF2Deriver.derive(
            password.encode('utf-8'),
            kek_salt,
            kek_iterations,
            key_length=32,
            hash_algo='sha256'
        )
        
        # 生成 KEK 和 VEK
        kek = b'\x03' * 32  # KEK
        vek = b'\x02' * 32  # VEK
        
        # 包装 KEK
        kek_wrapper = AESKeyWrap(derived_key)
        wrapped_kek = kek_wrapper.wrap(kek)
        
        # 包装 VEK
        vek_wrapper = AESKeyWrap(kek)
        wrapped_vek = vek_wrapper.wrap(vek)
        
        # 创建密钥包数据
        keybag_data = bytearray()
        
        # 添加密钥包签名 'kbag'
        keybag_data.extend(b'kbag')
        # 密钥包大小（先占位，稍后更新）
        keybag_size_offset = len(keybag_data)
        keybag_data.extend(b'\x00' * 4)  # 大小占位
        
        # KEK 条目
        kek_entry_type = KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK
        kek_entry_length = 2 + 2 + 16 + 8 + 16 + 40
        keybag_data.extend(struct.pack('>HH', kek_entry_type, kek_entry_length))
        keybag_data.extend(b'\x00' * 16)  # UUID
        keybag_data.extend(struct.pack('>Q', kek_iterations))
        keybag_data.extend(kek_salt)
        keybag_data.extend(wrapped_kek)  # 包装的 KEK
        
        # VEK 条目
        vek_entry_type = KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK
        vek_entry_length = 2 + 2 + 16 + 40
        keybag_data.extend(struct.pack('>HH', vek_entry_type, vek_entry_length))
        keybag_data.extend(b'\x00' * 16)  # UUID
        keybag_data.extend(wrapped_vek)
        
        # 更新密钥包大小
        keybag_size = len(keybag_data)
        struct.pack_into('>I', keybag_data, keybag_size_offset, keybag_size)
        
        # 创建卷数据
        volume_data = bytearray(4096)  # 简单的测试卷
        
        # 创建加密卷头
        header_data = bytearray(512)
        header_data[88:90] = b'CS'  # CoreStorage 签名
        struct.pack_into('>I', header_data, 172, 2)  # AES-XTS 加密方法
        
        # 组装完整卷
        stream = io.BytesIO()
        stream.write(bytes(header_data))
        stream.write(bytes(keybag_data))
        stream.write(bytes(volume_data))
        stream.seek(0)
        
        return stream, vek
    
    def test_parser_find_keybag(self):
        """测试解析器查找密钥包"""
        stream, vek = self._create_test_volume()
        
        parser = EncryptedVolumeParser(stream)
        
        # 验证能解析
        volume = parser.parse()
        self.assertIsNotNone(volume)
        self.assertFalse(volume.is_unlocked)
    
    def test_encrypted_volume_unlock(self):
        """测试加密卷解锁"""
        stream, vek = self._create_test_volume(password='testpassword')
        
        parser = EncryptedVolumeParser(stream)
        volume = parser.parse()
        
        # 使用密码解锁
        result = volume.unlock('testpassword')
        self.assertTrue(result)
        self.assertTrue(volume.is_unlocked)
    
    def test_encrypted_volume_wrong_password(self):
        """测试错误密码"""
        stream, vek = self._create_test_volume(password='correctpassword')
        
        parser = EncryptedVolumeParser(stream)
        volume = parser.parse()
        
        # 使用错误密码
        result = volume.unlock('wrongpassword')
        self.assertFalse(result)
        self.assertFalse(volume.is_unlocked)


if __name__ == '__main__':
    unittest.main()
