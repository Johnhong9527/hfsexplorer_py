"""
HFS+ 加密基础库

提供 AES-XTS、PBKDF2、AES Key Wrap 等加密算法实现。
用于支持 FileVault 2 加密卷的解密。
"""

import hashlib
import hmac
import struct
from typing import Optional, Tuple

# 尝试导入 pycryptodome
try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Random import get_random_bytes
    HAS_PYCRYPTODOME = True
except ImportError:
    HAS_PYCRYPTODOME = False

# 尝试导入 cryptography
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


class CryptoError(Exception):
    """加密错误"""
    pass


class AESXTS:
    """
    AES-XTS 模式实现
    
    用于 FileVault 2 加密卷的块级加密。
    """
    
    def __init__(self, key: bytes):
        """
        初始化 AES-XTS
        
        Args:
            key: 密钥（32 字节用于 AES-128-XTS，64 字节用于 AES-256-XTS）
        """
        if len(key) not in (32, 64):
            raise CryptoError(f"无效的密钥长度: {len(key)} 字节")
        
        self.key = key
        self.key_len = len(key) // 2
        
        if HAS_PYCRYPTODOME:
            self._cipher1 = AES.new(key[:self.key_len], AES.MODE_ECB)
            self._cipher2 = AES.new(key[self.key_len:], AES.MODE_ECB)
        elif HAS_CRYPTOGRAPHY:
            self._cipher1 = Cipher(
                algorithms.AES(key[:self.key_len]),
                modes.ECB(),
                backend=default_backend()
            )
            self._cipher2 = Cipher(
                algorithms.AES(key[self.key_len:]),
                modes.ECB(),
                backend=default_backend()
            )
        else:
            raise CryptoError("需要安装 pycryptodome 或 cryptography 库")
    
    def decrypt_sector(self, data: bytes, sector_number: int) -> bytes:
        """
        解密一个扇区
        
        Args:
            data: 加密的扇区数据
            sector_number: 扇区号
        
        Returns:
            解密后的数据
        """
        if len(data) % 16 != 0:
            raise CryptoError("数据长度必须是 16 的倍数")
        
        # 生成 tweak
        tweak = self._generate_tweak(sector_number)
        
        # 解密
        result = b''
        for i in range(0, len(data), 16):
            block = data[i:i+16]
            
            # XOR with tweak
            xored = self._xor(block, tweak)
            
            # Decrypt
            if HAS_PYCRYPTODOME:
                decrypted = self._cipher1.decrypt(xored)
            else:
                decryptor = self._cipher1.decryptor()
                decrypted = decryptor.update(xored) + decryptor.finalize()
            
            # XOR with tweak again
            result += self._xor(decrypted, tweak)
            
            # Update tweak
            tweak = self._multiply_gf(tweak)
        
        return result
    
    def encrypt_sector(self, data: bytes, sector_number: int) -> bytes:
        """
        加密一个扇区
        
        Args:
            data: 明文扇区数据
            sector_number: 扇区号
        
        Returns:
            加密后的数据
        """
        if len(data) % 16 != 0:
            raise CryptoError("数据长度必须是 16 的倍数")
        
        # 生成 tweak
        tweak = self._generate_tweak(sector_number)
        
        # 加密
        result = b''
        for i in range(0, len(data), 16):
            block = data[i:i+16]
            
            # XOR with tweak
            xored = self._xor(block, tweak)
            
            # Encrypt
            if HAS_PYCRYPTODOME:
                encrypted = self._cipher1.encrypt(xored)
            else:
                encryptor = self._cipher1.encryptor()
                encrypted = encryptor.update(xored) + encryptor.finalize()
            
            # XOR with tweak again
            result += self._xor(encrypted, tweak)
            
            # Update tweak
            tweak = self._multiply_gf(tweak)
        
        return result
    
    def _generate_tweak(self, sector_number: int) -> bytes:
        """生成 tweak"""
        # 将扇区号转换为 16 字节 little-endian
        tweak_data = struct.pack('<Q', sector_number) + b'\x00' * 8
        
        # 使用第二个密钥加密 tweak
        if HAS_PYCRYPTODOME:
            return self._cipher2.encrypt(tweak_data)
        else:
            encryptor = self._cipher2.encryptor()
            return encryptor.update(tweak_data) + encryptor.finalize()
    
    def _xor(self, a: bytes, b: bytes) -> bytes:
        """XOR 两个字节串"""
        return bytes(x ^ y for x, y in zip(a, b))
    
    def _multiply_gf(self, tweak: bytes) -> bytes:
        """在 GF(2^128) 上乘以 alpha"""
        result = bytearray(16)
        carry = 0
        
        for i in range(16):
            x = tweak[i]
            result[i] = ((x << 1) | carry) & 0xFF
            carry = (x >> 7) & 1
        
        if carry:
            result[0] ^= 0x87
        
        return bytes(result)


class AESKeyWrap:
    """
    AES Key Wrap 实现 (RFC 3394)
    
    用于解包 FileVault 2 的密钥。
    """
    
    def __init__(self, key: bytes):
        """
        初始化 AES Key Wrap
        
        Args:
            key: 密钥加密密钥 (KEK)
        """
        if len(key) not in (16, 24, 32):
            raise CryptoError(f"无效的密钥长度: {len(key)} 字节")
        
        self.key = key
        
        if HAS_PYCRYPTODOME:
            self._cipher = AES.new(key, AES.MODE_ECB)
        elif HAS_CRYPTOGRAPHY:
            self._cipher = Cipher(
                algorithms.AES(key),
                modes.ECB(),
                backend=default_backend()
            )
        else:
            raise CryptoError("需要安装 pycryptodome 或 cryptography 库")
    
    def unwrap(self, wrapped_key: bytes) -> bytes:
        """
        解包密钥
        
        Args:
            wrapped_key: 包装的密钥
        
        Returns:
            解包后的密钥
        """
        if len(wrapped_key) < 16 or len(wrapped_key) % 8 != 0:
            raise CryptoError("无效的包装密钥长度")
        
        n = (len(wrapped_key) // 8) - 1
        
        # 初始化
        A = wrapped_key[:8]
        R = [wrapped_key[i*8:(i+1)*8] for i in range(1, n+1)]
        
        # 解包
        for j in range(5, -1, -1):
            for i in range(n, 0, -1):
                # 计算 B = AES(A ^ t) | R[i]
                t = n * j + i
                t_bytes = struct.pack('>Q', t)
                
                # XOR A with t
                a_xor_t = self._xor_8bytes(A, t_bytes)
                
                # Decrypt
                if HAS_PYCRYPTODOME:
                    B = self._cipher.decrypt(a_xor_t + R[i-1])
                else:
                    decryptor = self._cipher.decryptor()
                    B = decryptor.update(a_xor_t + R[i-1]) + decryptor.finalize()
                
                A = B[:8]
                R[i-1] = B[8:]
        
        # 验证 A
        if A != b'\xa6\xa6\xa6\xa6\xa6\xa6\xa6\xa6':
            raise CryptoError("密钥解包失败：校验和不匹配")
        
        # 拼接结果
        result = b''
        for r in R:
            result += r
        
        return result
    
    def wrap(self, key: bytes) -> bytes:
        """
        包装密钥
        
        Args:
            key: 要包装的密钥
        
        Returns:
            包装后的密钥
        """
        if len(key) % 8 != 0:
            raise CryptoError("密钥长度必须是 8 的倍数")
        
        n = len(key) // 8
        
        # 初始化
        A = b'\xa6\xa6\xa6\xa6\xa6\xa6\xa6\xa6'
        R = [key[i*8:(i+1)*8] for i in range(n)]
        
        # 包装
        for j in range(6):
            for i in range(1, n+1):
                # 计算 B = AES(A | R[i]) ^ t
                t = n * j + i
                t_bytes = struct.pack('>Q', t)
                
                # Encrypt
                if HAS_PYCRYPTODOME:
                    B = self._cipher.encrypt(A + R[i-1])
                else:
                    encryptor = self._cipher.encryptor()
                    B = encryptor.update(A + R[i-1]) + encryptor.finalize()
                
                # XOR with t
                A = self._xor_8bytes(B[:8], t_bytes)
                R[i-1] = B[8:]
        
        # 拼接结果
        result = A
        for r in R:
            result += r
        
        return result
    
    def _xor_8bytes(self, a: bytes, b: bytes) -> bytes:
        """XOR 两个 8 字节串"""
        return bytes(x ^ y for x, y in zip(a, b))


class PBKDF2Deriver:
    """
    PBKDF2 密钥派生
    
    用于从密码派生密钥。
    """
    
    @staticmethod
    def derive(password: bytes, salt: bytes, iterations: int,
               key_length: int = 32, hash_algo: str = 'sha256') -> bytes:
        """
        派生密钥
        
        Args:
            password: 密码
            salt: 盐值
            iterations: 迭代次数
            key_length: 输出密钥长度
            hash_algo: 哈希算法 ('sha1', 'sha256', 'sha512')
        
        Returns:
            派生的密钥
        """
        if HAS_PYCRYPTODOME:
            if hash_algo == 'sha1':
                return PBKDF2(password, salt, dkLen=key_length, count=iterations,
                             prf=lambda p, s: hmac.new(p, s, hashlib.sha1).digest())
            elif hash_algo == 'sha256':
                return PBKDF2(password, salt, dkLen=key_length, count=iterations,
                             prf=lambda p, s: hmac.new(p, s, hashlib.sha256).digest())
            elif hash_algo == 'sha512':
                return PBKDF2(password, salt, dkLen=key_length, count=iterations,
                             prf=lambda p, s: hmac.new(p, s, hashlib.sha512).digest())
            else:
                raise CryptoError(f"不支持的哈希算法: {hash_algo}")
        elif HAS_CRYPTOGRAPHY:
            if hash_algo == 'sha1':
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA1(),
                    length=key_length,
                    salt=salt,
                    iterations=iterations,
                    backend=default_backend()
                )
            elif hash_algo == 'sha256':
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=key_length,
                    salt=salt,
                    iterations=iterations,
                    backend=default_backend()
                )
            elif hash_algo == 'sha512':
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA512(),
                    length=key_length,
                    salt=salt,
                    iterations=iterations,
                    backend=default_backend()
                )
            else:
                raise CryptoError(f"不支持的哈希算法: {hash_algo}")
            
            return kdf.derive(password)
        else:
            raise CryptoError("需要安装 pycryptodome 或 cryptography 库")


class EncryptedVolumeHeader:
    """
    加密卷头
    
    用于解析 FileVault 2 加密卷的头部信息。
    """
    
    # CoreStorage 签名
    CS_SIGNATURE = b'CS'
    
    def __init__(self, data: bytes):
        """
        初始化加密卷头
        
        Args:
            data: 卷头数据（512 字节）
        """
        if len(data) < 512:
            raise CryptoError("卷头数据不足 512 字节")
        
        self.data = data
        self._parse()
    
    def _parse(self):
        """解析卷头"""
        # 检查签名
        if self.data[88:90] != self.CS_SIGNATURE:
            raise CryptoError("无效的 CoreStorage 签名")
        
        # 解析字段
        self.key_data_size = struct.unpack_from('>I', self.data, 168)[0]
        self.encryption_method = struct.unpack_from('>I', self.data, 172)[0]
        self.key_data = self.data[176:176 + self.key_data_size]
        self.physical_volume_id = self.data[304:320]
        self.logical_volume_group_id = self.data[320:336]
    
    @property
    def is_encrypted(self) -> bool:
        """是否加密"""
        return self.encryption_method == 2  # AES-XTS
    
    @property
    def encryption_method_name(self) -> str:
        """加密方法名称"""
        if self.encryption_method == 0:
            return "无"
        elif self.encryption_method == 1:
            return "AES-CBC"
        elif self.encryption_method == 2:
            return "AES-XTS"
        else:
            return f"未知 ({self.encryption_method})"