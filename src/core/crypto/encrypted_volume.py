"""
HFS+ 加密卷解析器

用于解析和解密 FileVault 2 加密卷。
"""

import struct
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import IntEnum

from . import CryptoError, AESXTS, AESKeyWrap, PBKDF2Deriver


class KeybagEntryType(IntEnum):
    """密钥包条目类型"""
    KEYBAG_ENTRY_WRAPPED_KEK = 1  # 包装的 KEK
    KEYBAG_ENTRY_WRAPPED_VEK = 2  # 包装的 VEK
    KEYBAG_ENTRY_WRAPPED_KEK_RECOVERY = 3  # 恢复 KEK
    KEYBAG_ENTRY_WRAPPED_VEK_RECOVERY = 4  # 恢复 VEK


@dataclass
class KeybagEntry:
    """
    密钥包条目
    
    Attributes:
        uuid: UUID
        entry_type: 条目类型
        wrapped_key: 包装的密钥
        iterations: PBKDF2 迭代次数
        salt: PBKDF2 盐值
    """
    uuid: bytes
    entry_type: int
    wrapped_key: bytes
    iterations: int = 0
    salt: bytes = b''


class Keybag:
    """
    密钥包
    
    用于存储加密卷的密钥信息。
    """
    
    def __init__(self, data: bytes):
        """
        初始化密钥包
        
        Args:
            data: 密钥包数据
        """
        self.data = data
        self.entries: List[KeybagEntry] = []
        self._parse()
    
    def _parse(self):
        """解析密钥包"""
        offset = 0
        
        while offset < len(self.data):
            # 检查是否有足够的数据
            if offset + 16 > len(self.data):
                break
            
            # 解析条目头
            entry_type = struct.unpack_from('>H', self.data, offset)[0]
            entry_length = struct.unpack_from('>H', self.data, offset + 2)[0]
            
            if entry_length == 0:
                break
            
            # 解析条目数据
            if entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK:
                # KEK 条目
                uuid = self.data[offset + 4:offset + 20]
                iterations = struct.unpack_from('>Q', self.data, offset + 20)[0]
                salt = self.data[offset + 28:offset + 44]
                wrapped_key = self.data[offset + 44:offset + 44 + 40]
                
                self.entries.append(KeybagEntry(
                    uuid=uuid,
                    entry_type=entry_type,
                    wrapped_key=wrapped_key,
                    iterations=iterations,
                    salt=salt
                ))
            elif entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK:
                # VEK 条目
                uuid = self.data[offset + 4:offset + 20]
                wrapped_key = self.data[offset + 20:offset + 20 + 40]
                
                self.entries.append(KeybagEntry(
                    uuid=uuid,
                    entry_type=entry_type,
                    wrapped_key=wrapped_key
                ))
            elif entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK_RECOVERY:
                # 恢复 KEK 条目
                uuid = self.data[offset + 4:offset + 20]
                iterations = struct.unpack_from('>Q', self.data, offset + 20)[0]
                salt = self.data[offset + 28:offset + 44]
                wrapped_key = self.data[offset + 44:offset + 44 + 40]
                
                self.entries.append(KeybagEntry(
                    uuid=uuid,
                    entry_type=entry_type,
                    wrapped_key=wrapped_key,
                    iterations=iterations,
                    salt=salt
                ))
            elif entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK_RECOVERY:
                # 恢复 VEK 条目
                uuid = self.data[offset + 4:offset + 20]
                wrapped_key = self.data[offset + 20:offset + 20 + 40]
                
                self.entries.append(KeybagEntry(
                    uuid=uuid,
                    entry_type=entry_type,
                    wrapped_key=wrapped_key
                ))
            
            offset += entry_length
    
    def get_kek_entry(self, uuid: Optional[bytes] = None) -> Optional[KeybagEntry]:
        """获取 KEK 条目"""
        for entry in self.entries:
            if entry.entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK:
                if uuid is None or entry.uuid == uuid:
                    return entry
        return None
    
    def get_vek_entry(self, uuid: Optional[bytes] = None) -> Optional[KeybagEntry]:
        """获取 VEK 条目"""
        for entry in self.entries:
            if entry.entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK:
                if uuid is None or entry.uuid == uuid:
                    return entry
        return None
    
    def get_recovery_kek_entry(self, uuid: Optional[bytes] = None) -> Optional[KeybagEntry]:
        """获取恢复 KEK 条目"""
        for entry in self.entries:
            if entry.entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_KEK_RECOVERY:
                if uuid is None or entry.uuid == uuid:
                    return entry
        return None
    
    def get_recovery_vek_entry(self, uuid: Optional[bytes] = None) -> Optional[KeybagEntry]:
        """获取恢复 VEK 条目"""
        for entry in self.entries:
            if entry.entry_type == KeybagEntryType.KEYBAG_ENTRY_WRAPPED_VEK_RECOVERY:
                if uuid is None or entry.uuid == uuid:
                    return entry
        return None


class EncryptedVolume:
    """
    加密卷
    
    用于解密 FileVault 2 加密卷。
    
    Usage:
        volume = EncryptedVolume(stream, header, keybag)
        volume.unlock(password)
        data = volume.read_sector(sector_number)
    """
    
    def __init__(self, stream, header, keybag: Keybag):
        """
        初始化加密卷
        
        Args:
            stream: 可 seek 的二进制流
            header: 加密卷头
            keybag: 密钥包
        """
        self.stream = stream
        self.header = header
        self.keybag = keybag
        self._vek: Optional[bytes] = None
        self._xts: Optional[AESXTS] = None
    
    @property
    def is_unlocked(self) -> bool:
        """是否已解锁"""
        return self._vek is not None
    
    def unlock(self, password: str) -> bool:
        """
        使用密码解锁卷
        
        Args:
            password: 密码
        
        Returns:
            是否成功解锁
        """
        # 获取 KEK 条目
        kek_entry = self.keybag.get_kek_entry()
        if kek_entry is None:
            raise CryptoError("未找到 KEK 条目")
        
        # 派生密钥
        password_bytes = password.encode('utf-8')
        derived_key = PBKDF2Deriver.derive(
            password_bytes,
            kek_entry.salt,
            kek_entry.iterations,
            key_length=32,
            hash_algo='sha256'
        )
        
        # 解包 KEK
        try:
            kek = AESKeyWrap(derived_key).unwrap(kek_entry.wrapped_key)
        except CryptoError:
            return False
        
        # 获取 VEK 条目
        vek_entry = self.keybag.get_vek_entry()
        if vek_entry is None:
            raise CryptoError("未找到 VEK 条目")
        
        # 解包 VEK
        try:
            self._vek = AESKeyWrap(kek).unwrap(vek_entry.wrapped_key)
        except CryptoError:
            return False
        
        # 创建 AES-XTS 实例
        self._xts = AESXTS(self._vek)
        
        return True
    
    def unlock_with_recovery_key(self, recovery_key: str) -> bool:
        """
        使用恢复密钥解锁卷
        
        Args:
            recovery_key: 恢复密钥
        
        Returns:
            是否成功解锁
        """
        # 获取恢复 KEK 条目
        kek_entry = self.keybag.get_recovery_kek_entry()
        if kek_entry is None:
            raise CryptoError("未找到恢复 KEK 条目")
        
        # 派生密钥
        recovery_bytes = recovery_key.encode('utf-8')
        derived_key = PBKDF2Deriver.derive(
            recovery_bytes,
            kek_entry.salt,
            kek_entry.iterations,
            key_length=32,
            hash_algo='sha256'
        )
        
        # 解包 KEK
        try:
            kek = AESKeyWrap(derived_key).unwrap(kek_entry.wrapped_key)
        except CryptoError:
            return False
        
        # 获取恢复 VEK 条目
        vek_entry = self.keybag.get_recovery_vek_entry()
        if vek_entry is None:
            raise CryptoError("未找到恢复 VEK 条目")
        
        # 解包 VEK
        try:
            self._vek = AESKeyWrap(kek).unwrap(vek_entry.wrapped_key)
        except CryptoError:
            return False
        
        # 创建 AES-XTS 实例
        self._xts = AESXTS(self._vek)
        
        return True
    
    def read_sector(self, sector_number: int, sector_size: int = 512) -> bytes:
        """
        读取并解密一个扇区
        
        Args:
            sector_number: 扇区号
            sector_size: 扇区大小
        
        Returns:
            解密后的扇区数据
        """
        if not self.is_unlocked:
            raise CryptoError("卷未解锁")
        
        # 读取加密数据
        offset = sector_number * sector_size
        self.stream.seek(offset)
        encrypted_data = self.stream.read(sector_size)
        
        if len(encrypted_data) < sector_size:
            raise CryptoError(f"读取扇区失败: 期望 {sector_size} 字节, 实际 {len(encrypted_data)} 字节")
        
        # 解密
        return self._xts.decrypt_sector(encrypted_data, sector_number)
    
    def write_sector(self, sector_number: int, data: bytes, sector_size: int = 512):
        """
        加密并写入一个扇区
        
        Args:
            sector_number: 扇区号
            data: 明文数据
            sector_size: 扇区大小
        """
        if not self.is_unlocked:
            raise CryptoError("卷未解锁")
        
        if len(data) < sector_size:
            data = data + b'\x00' * (sector_size - len(data))
        
        # 加密
        encrypted_data = self._xts.encrypt_sector(data[:sector_size], sector_number)
        
        # 写入
        offset = sector_number * sector_size
        self.stream.seek(offset)
        self.stream.write(encrypted_data)


class EncryptedVolumeParser:
    """
    加密卷解析器
    
    用于解析 FileVault 2 加密卷。
    
    Usage:
        parser = EncryptedVolumeParser(stream)
        volume = parser.parse()
        volume.unlock(password)
    """
    
    def __init__(self, stream):
        """
        初始化加密卷解析器
        
        Args:
            stream: 可 seek 的二进制流
        """
        self.stream = stream
    
    def parse(self) -> EncryptedVolume:
        """
        解析加密卷
        
        Returns:
            加密卷对象
        """
        # 读取卷头
        self.stream.seek(0)
        header_data = self.stream.read(512)
        
        if len(header_data) < 512:
            raise CryptoError("无法读取卷头")
        
        # 解析卷头
        from . import EncryptedVolumeHeader
        header = EncryptedVolumeHeader(header_data)
        
        if not header.is_encrypted:
            raise CryptoError("卷未加密")
        
        # 读取密钥包
        # 注意：密钥包的位置取决于具体的实现
        # 这里简化处理，假设密钥包在卷的某个固定位置
        keybag_data = self._read_keybag()
        
        # 解析密钥包
        keybag = Keybag(keybag_data)
        
        return EncryptedVolume(self.stream, header, keybag)
    
    def _read_keybag(self) -> bytes:
        """
        读取密钥包
        
        Returns:
            密钥包数据
        """
        # 注意：这里简化了实现
        # 实际需要根据 CoreStorage 的格式来读取密钥包
        # 密钥包通常存储在卷的元数据区域
        
        # 这里返回一个空的密钥包作为占位
        return b''