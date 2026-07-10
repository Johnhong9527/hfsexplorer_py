"""
HFS+ 加密卷解析器

用于解析和解密 FileVault 2 加密卷。
"""

import struct
from typing import Optional, Tuple, List, Dict, Any
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
        
        # 检查是否有签名 'kbag'
        if len(self.data) >= 8 and self.data[0:4] == b'kbag':
            # 跳过签名（4字节）和大小（4字节）
            offset = 8
        
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
    
    FileVault 2 使用 CoreStorage 逻辑卷管理器，密钥包结构：
    - 物理卷头部（偏移 0）
    - 密钥包描述符（偏移 512）
    - 密钥包数据
    
    Usage:
        parser = EncryptedVolumeParser(stream)
        volume = parser.parse()
        volume.unlock(password)
    """
    
    # CoreStorage 密钥包签名
    KEYBAG_SIGNATURE = b'kbag'
    
    # 密钥包描述符大小
    KEYBAG_DESC_SIZE = 512
    
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
        keybag_data = self._read_keybag()
        
        # 解析密钥包
        keybag = Keybag(keybag_data)
        
        return EncryptedVolume(self.stream, header, keybag)
    
    def _read_keybag(self) -> bytes:
        """
        读取密钥包
        
        Returns:
            密钥包数据
        
        Raises:
            CryptoError: 如果无法找到密钥包
        """
        # 方法1：从卷头获取密钥包位置
        keybag_offset = self._find_keybag_from_header()
        if keybag_offset is not None:
            return self._read_keybag_at_offset(keybag_offset)
        
        # 方法2：扫描卷查找密钥包签名
        keybag_offset = self._scan_for_keybag()
        if keybag_offset is not None:
            return self._read_keybag_at_offset(keybag_offset)
        
        # 方法3：使用常见的密钥包位置
        for offset in [512, 4096, 1024, 2048]:
            try:
                data = self._read_keybag_at_offset(offset)
                if len(data) > 0:
                    return data
            except:
                continue
        
        raise CryptoError("无法找到密钥包")
    
    def _find_keybag_from_header(self) -> Optional[int]:
        """
        从卷头获取密钥包位置
        
        Returns:
            密钥包偏移，如果未找到则返回 None
        """
        # 读取卷头的扩展区域
        self.stream.seek(0)
        header_data = self.stream.read(512)
        
        # 检查是否有密钥包偏移字段（位置可能因版本而异）
        # CoreStorage 头部通常在偏移 88 开始
        if len(header_data) < 512:
            return None
        
        # 查找密钥包描述符
        # 在某些实现中，密钥包描述符紧跟在卷头之后
        self.stream.seek(512)
        desc_data = self.stream.read(512)
        
        if len(desc_data) >= 512:
            # 检查是否是密钥包描述符
            if desc_data[0:4] == self.KEYBAG_SIGNATURE:
                return 512
        
        return None
    
    def _scan_for_keybag(self, max_scan_mb: int = 10) -> Optional[int]:
        """
        扫描卷查找密钥包签名
        
        Args:
            max_scan_mb: 最大扫描范围（MB）
        
        Returns:
            密钥包偏移，如果未找到则返回 None
        """
        # 获取流大小
        self.stream.seek(0, 2)
        stream_size = self.stream.tell()
        
        # 限制扫描范围
        scan_size = min(max_scan_mb * 1024 * 1024, stream_size)
        
        # 从开头扫描
        self.stream.seek(0)
        buffer = b''
        chunk_size = 4096
        
        for offset in range(0, scan_size, chunk_size):
            self.stream.seek(offset)
            chunk = self.stream.read(chunk_size)
            
            if len(chunk) < 4:
                break
            
            # 在块中查找签名
            pos = chunk.find(self.KEYBAG_SIGNATURE)
            if pos >= 0:
                # 验证找到的位置是否是有效的密钥包
                keybag_offset = offset + pos
                if self._validate_keybag_at_offset(keybag_offset):
                    return keybag_offset
        
        return None
    
    def _validate_keybag_at_offset(self, offset: int) -> bool:
        """
        验证指定偏移处是否是有效的密钥包
        
        Args:
            offset: 偏移量
        
        Returns:
            是否是有效的密钥包
        """
        try:
            self.stream.seek(offset)
            data = self.stream.read(16)
            
            if len(data) < 16:
                return False
            
            # 检查签名
            if data[0:4] != self.KEYBAG_SIGNATURE:
                return False
            
            # 检查大小是否合理
            size = struct.unpack_from('>I', data, 4)[0]
            if size < 16 or size > 1024 * 1024:  # 最大 1MB
                return False
            
            return True
        except:
            return False
    
    def _read_keybag_at_offset(self, offset: int) -> bytes:
        """
        读取指定偏移处的密钥包
        
        Args:
            offset: 密钥包偏移
        
        Returns:
            密钥包数据
        """
        # 读取密钥包描述符
        self.stream.seek(offset)
        desc_data = self.stream.read(self.KEYBAG_DESC_SIZE)
        
        if len(desc_data) < self.KEYBAG_DESC_SIZE:
            raise CryptoError("无法读取密钥包描述符")
        
        # 解析密钥包描述符
        signature = desc_data[0:4]
        if signature != self.KEYBAG_SIGNATURE:
            raise CryptoError(f"无效的密钥包签名: {signature}")
        
        # 获取密钥包大小
        keybag_size = struct.unpack_from('>I', desc_data, 4)[0]
        
        if keybag_size < 16 or keybag_size > 1024 * 1024:
            raise CryptoError(f"无效的密钥包大小: {keybag_size}")
        
        # 读取完整的密钥包
        self.stream.seek(offset)
        keybag_data = self.stream.read(keybag_size)
        
        if len(keybag_data) < keybag_size:
            raise CryptoError("无法读取完整的密钥包")
        
        return keybag_data
    
    def _parse_keybag_header(self, data: bytes) -> Dict[str, Any]:
        """
        解析密钥包头部
        
        Args:
            data: 密钥包数据
        
        Returns:
            头部信息字典
        """
        if len(data) < 16:
            raise CryptoError("密钥包数据太短")
        
        signature = data[0:4]
        size = struct.unpack_from('>I', data, 4)[0]
        
        return {
            'signature': signature,
            'size': size,
            'data': data,
        }