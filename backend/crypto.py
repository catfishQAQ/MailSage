"""
本地密码加密工具（Fernet 对称加密）。
密钥存储在 .env 文件或环境变量 SECRET_KEY 中。
首次运行若不存在则自动生成并写入 .env。
"""
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet

_ENV_FILE = Path(__file__).parent / ".env"
_KEY_NAME = "SECRET_KEY"
_fernet: Fernet | None = None


def _load_or_create_key() -> bytes:
    # 优先读环境变量
    key = os.environ.get(_KEY_NAME)
    if key:
        return key.encode()

    # 读 .env 文件
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            if line.startswith(f"{_KEY_NAME}="):
                return line.split("=", 1)[1].strip().encode()

    # 生成新密钥并持久化
    new_key = Fernet.generate_key()
    with _ENV_FILE.open("a") as f:
        f.write(f"{_KEY_NAME}={new_key.decode()}\n")
    return new_key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
