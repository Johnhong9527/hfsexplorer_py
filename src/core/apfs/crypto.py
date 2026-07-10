"""
APFS 加密支持模块

提供 APFS 文件系统的加密和解密功能。
支持 FileVault 2 加密的 APFS 卷。

注意：这是一个简化的实现，用于演示基本原理。
完整的 APFS 加密实现需要更复杂的密钥管理和加密算法。
"""

import struct
import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, BinaryIO
from enum import IntEnum


# =============================================================================
# APFS 加密常量
# =============================================================================

# 加密算法
class CryptoAlgorithm(IntEnum):
    """加密算法"""
    AES_XTS = 1  # AES-XTS 模式
    AES_CBC = 2  # AES-CBC 模式


# 密钥类型
class KeyType(IntEnum):
    """密钥类型"""
    USER_PASSWORD = 1  # 用户密码
    RECOVERY_KEY = 2  # 恢复密钥
    INSTITUTIONAL_KEY = 3  # 机构密钥
    IRREVERSIBLE_KEY = 4  # 不可逆密钥


# 密钥包魔数
KEYBAG_MAGIC = b'NON!'
ENCRYPTED_KEYBAG_MAGIC = b'EKEY'


# =============================================================================
# APFS 加密数据结构
# =============================================================================

@dataclass
class APFSKeybagHeader:
    """APFS 密钥包头部"""
    magic: bytes  # 魔数
    version: int  # 版本
    count: int  # 密钥数量
    salt: bytes  # 盐值
    iterations: int  # PBKDF2 迭代次数
    uuid: bytes  # UUID
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'APFSKeybagHeader':
        """从字节序列解析"""
        magic = data[offset:offset + 4]
        version = struct.unpack_from('<I', data, offset + 4)[0]
        count = struct.unpack_from('<I', data, offset + 8)[0]
        salt = data[offset + 12:offset + 44]  # 32 字节盐值
        iterations = struct.unpack_from('<I', data, offset + 44)[0]
        uuid = data[offset + 48:offset + 64]  # 16 字节 UUID
        
        return cls(
            magic=magic,
            version=version,
            count=count,
            salt=salt,
            iterations=iterations,
            uuid=uuid
        )


@dataclass
class APFSKeyEntry:
    """APFS 密钥条目"""
    key_class: int  # 密钥类
    key_type: int  # 密钥类型
    uuid: bytes  # UUID
    tag: int  # 标签
    key_data: bytes  # 密钥数据
    wrapped_key: bytes  # 包装后的密钥
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'APFSKeyEntry':
        """从字节序列解析"""
        key_class = struct.unpack_from('<I', data, offset)[0]
        key_type = struct.unpack_from('<I', data, offset + 4)[0]
        uuid = data[offset + 8:offset + 24]  # 16 字节 UUID
        tag = struct.unpack_from('<I', data, offset + 24)[0]
        
        # 密钥数据长度
        key_len = struct.unpack_from('<I', data, offset + 28)[0]
        key_data = data[offset + 32:offset + 32 + key_len]
        
        # 包装密钥长度
        wrapped_offset = offset + 32 + key_len
        wrapped_len = struct.unpack_from('<I', data, wrapped_offset)[0]
        wrapped_key = data[wrapped_offset + 4:wrapped_offset + 4 + wrapped_len]
        
        return cls(
            key_class=key_class,
            key_type=key_type,
            uuid=uuid,
            tag=tag,
            key_data=key_data,
            wrapped_key=wrapped_key
        )


@dataclass
class APFSEncryptionInfo:
    """APFS 加密信息"""
    algorithm: int  # 加密算法
    key_size: int  # 密钥大小
    block_size: int  # 加密块大小
    uuid: bytes  # 卷 UUID
    
    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> 'APFSEncryptionInfo':
        """从字节序列解析"""
        algorithm = struct.unpack_from('<I', data, offset)[0]
        key_size = struct.unpack_from('<I', data, offset + 4)[0]
        block_size = struct.unpack_from('<I', data, offset + 8)[0]
        uuid = data[offset + 12:offset + 28]
        
        return cls(
            algorithm=algorithm,
            key_size=key_size,
            block_size=block_size,
            uuid=uuid
        )


# =============================================================================
# APFS 加密/解密实现
# =============================================================================

class APFSCrypto:
    """
    APFS 加密/解密类
    
    提供 APFS 卷的加密和解密功能。
    """
    
    def __init__(self):
        """初始化加密类"""
        self._keybag: Optional[APFSKeybagHeader] = None
        self._keys: List[APFSKeyEntry] = []
        self._encryption_info: Optional[APFSEncryptionInfo] = None
        self._volume_key: Optional[bytes] = None
        
    def parse_keybag(self, data: bytes, offset: int = 0) -> bool:
        """
        解析密钥包
        
        Args:
            data: 密钥包数据
            offset: 偏移量
            
        Returns:
            是否成功
        """
        try:
            self._keybag = APFSKeybagHeader.from_bytes(data, offset)
            
            if self._keybag.magic not in [KEYBAG_MAGIC, ENCRYPTED_KEYBAG_MAGIC]:
                return False
                
            # 解析密钥条目
            entry_offset = offset + 64  # 头部之后
            for i in range(self._keybag.count):
                if entry_offset + 32 > len(data):
                    break
                    
                key_entry = APFSKeyEntry.from_bytes(data, entry_offset)
                self._keys.append(key_entry)
                
                # 计算下一个条目的偏移
                key_len = struct.unpack_from('<I', data, entry_offset + 28)[0]
                wrapped_offset = entry_offset + 32 + key_len
                wrapped_len = struct.unpack_from('<I', data, wrapped_offset)[0]
                entry_offset = wrapped_offset + 4 + wrapped_len
                
            return True
        except Exception as e:
            print(f"解析密钥包失败: {e}")
            return False
            
    def parse_encryption_info(self, data: bytes, offset: int = 0) -> bool:
        """
        解析加密信息
        
        Args:
            data: 加密信息数据
            offset: 偏移量
            
        Returns:
            是否成功
        """
        try:
            self._encryption_info = APFSEncryptionInfo.from_bytes(data, offset)
            return True
        except Exception as e:
            print(f"解析加密信息失败: {e}")
            return False
            
    def derive_key(self, password: str) -> bytes:
        """
        从密码派生密钥
        
        Args:
            password: 用户密码
            
        Returns:
            派生的密钥
        """
        if not self._keybag:
            raise RuntimeError("密钥包未初始化")
            
        # 使用 PBKDF2 派生密钥
        salt = self._keybag.salt
        iterations = self._keybag.iterations if self._keybag.iterations > 0 else 10000
        
        # PBKDF2-HMAC-SHA256
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations,
            dklen=32  # 256 位密钥
        )
        
        return key
        
    def unwrap_key(self, wrapped_key: bytes, kek: bytes) -> Optional[bytes]:
        """
        解包密钥
        
        Args:
            wrapped_key: 包装后的密钥
            kek: 密钥加密密钥
            
        Returns:
            解包后的密钥
        """
        # 简化的密钥解包实现
        # 实际应该使用 AES Key Wrap (RFC 3394)
        
        if len(wrapped_key) < 32:
            return None
            
        # 使用 XOR 简化解包（实际应该用 AES）
        unwrapped = bytearray(32)
        for i in range(32):
            unwrapped[i] = wrapped_key[i] ^ kek[i % len(kek)]
            
        return bytes(unwrapped)
        
    def decrypt_block(self, block_num: int, encrypted_data: bytes, 
                      key: Optional[bytes] = None) -> bytes:
        """
        解密数据块
        
        Args:
            block_num: 块号
            encrypted_data: 加密数据
            key: 解密密钥（如果为 None，使用卷密钥）
            
        Returns:
            解密后的数据
        """
        if key is None:
            key = self._volume_key
            
        if key is None:
            return encrypted_data  # 无密钥，返回原始数据
            
        # 简化的 AES-XTS 解密
        # 实际应该使用 cryptography 库
        
        block_size = len(encrypted_data)
        decrypted = bytearray(block_size)
        
        # 使用 XOR 简化解密（实际应该用 AES-XTS）
        for i in range(block_size):
            # 使用块号作为 tweak
            tweak = (block_num >> (i % 8)) & 0xFF
            decrypted[i] = encrypted_data[i] ^ key[i % len(key)] ^ tweak
            
        return bytes(decrypted)
        
    def decrypt_with_password(self, password: str) -> bool:
        """
        使用密码解密
        
        Args:
            password: 用户密码
            
        Returns:
            是否成功
        """
        if not self._keybag:
            return False
            
        # 派生密钥
        kek = self.derive_key(password)
        
        # 查找用户密钥
        for key_entry in self._keys:
            if key_entry.key_type == KeyType.USER_PASSWORD:
                # 解包卷密钥
                volume_key = self.unwrap_key(key_entry.wrapped_key, kek)
                if volume_key:
                    self._volume_key = volume_key
                    return True
                    
        return False
        
    def is_unlocked(self) -> bool:
        """是否已解锁"""
        return self._volume_key is not None
        
    def get_volume_key(self) -> Optional[bytes]:
        """获取卷密钥"""
        return self._volume_key


# =============================================================================
# APFS 加密卷读取器
# =============================================================================

class APFSEncryptedVolumeReader:
    """
    APFS 加密卷读取器
    
    支持读取加密的 APFS 卷。
    """
    
    def __init__(self, file_path: str):
        """
        初始化加密卷读取器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        self._crypto = APFSCrypto()
        self._file: Optional[BinaryIO] = None
        self._is_encrypted = False
        self._container = None
        self._volume = None
        
    def open(self) -> bool:
        """
        打开卷
        
        Returns:
            是否是加密卷
        """
        self._file = open(self.file_path, 'rb')
        
        # 检测是否是加密卷
        self._is_encrypted = self._detect_encryption()
        
        if self._is_encrypted:
            # 解析密钥包
            self._parse_keybag()
            
        return self._is_encrypted
        
    def close(self) -> None:
        """关闭卷"""
        if self._file:
            self._file.close()
            self._file = None
            
    def __enter__(self):
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _detect_encryption(self) -> bool:
        """检测是否是加密卷"""
        if not self._file:
            return False
            
        # 读取卷超级块
        self._file.seek(0)
        data = self._file.read(4096)
        
        # 检查加密标志
        # APFS 卷超级块中的 features 字段
        if len(data) >= 100:
            features = struct.unpack_from('<Q', data, 56)[0]
            # 检查加密标志位
            if features & 0x01:  # ENCRYPTED 标志
                return True
                
        # 检查是否有密钥包
        self._file.seek(0)
        data = self._file.read(4096 * 10)
        
        # 查找密钥包魔数
        for i in range(0, len(data) - 4, 4):
            if data[i:i + 4] in [KEYBAG_MAGIC, ENCRYPTED_KEYBAG_MAGIC]:
                return True
                
        return False
        
    def _parse_keybag(self) -> None:
        """解析密钥包"""
        if not self._file:
            return
            
        # 读取可能的密钥包位置
        self._file.seek(0)
        data = self._file.read(4096 * 10)
        
        # 查找密钥包
        for i in range(0, len(data) - 64, 4):
            if data[i:i + 4] in [KEYBAG_MAGIC, ENCRYPTED_KEYBAG_MAGIC]:
                self._crypto.parse_keybag(data, i)
                break
                
    def is_encrypted(self) -> bool:
        """是否加密"""
        return self._is_encrypted
        
    def is_unlocked(self) -> bool:
        """是否已解锁"""
        return self._crypto.is_unlocked()
        
    def unlock_with_password(self, password: str) -> bool:
        """
        使用密码解锁
        
        Args:
            password: 用户密码
            
        Returns:
            是否成功
        """
        if not self._is_encrypted:
            return True  # 未加密，直接返回成功
            
        return self._crypto.decrypt_with_password(password)
        
    def read_block(self, block_num: int) -> bytes:
        """
        读取数据块
        
        Args:
            block_num: 块号
            
        Returns:
            块数据
        """
        if not self._file:
            return b''
            
        # 读取加密数据
        block_size = 4096  # 默认块大小
        offset = block_num * block_size
        
        self._file.seek(offset)
        encrypted_data = self._file.read(block_size)
        
        # 如果已解锁，解密数据
        if self._crypto.is_unlocked():
            return self._crypto.decrypt_block(block_num, encrypted_data)
            
        return encrypted_data
        
    def get_info(self) -> Dict:
        """获取卷信息"""
        return {
            'encrypted': self._is_encrypted,
            'unlocked': self._crypto.is_unlocked(),
            'key_count': len(self._crypto._keys),
        }


# =============================================================================
# 便捷函数
# =============================================================================

def open_encrypted_apfs(path: str) -> APFSEncryptedVolumeReader:
    """
    打开加密的 APFS 卷
    
    Args:
        path: 文件路径
        
    Returns:
        加密卷读取器
    """
    reader = APFSEncryptedVolumeReader(path)
    reader.open()
    return reader


def is_apfs_encrypted(path: str) -> bool:
    """
    检查 APFS 卷是否加密
    
    Args:
        path: 文件路径
        
    Returns:
        是否加密
    """
    try:
        reader = APFSEncryptedVolumeReader(path)
        result = reader.open()
        reader.close()
        return result
    except:
        return False


def unlock_apfs(path: str, password: str) -> Optional[APFSEncryptedVolumeReader]:
    """
    解锁加密的 APFS 卷
    
    Args:
        path: 文件路径
        password: 密码
        
    Returns:
        解锁后的读取器，如果失败返回 None
    """
    reader = APFSEncryptedVolumeReader(path)
    
    if not reader.open():
        reader.close()
        return None
        
    if not reader.is_encrypted():
        return reader
        
    if reader.unlock_with_password(password):
        return reader
        
    reader.close()
    return None
