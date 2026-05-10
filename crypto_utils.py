import base64
import ctypes
import hashlib
import logging
from pathlib import Path

log = logging.getLogger("spee4ka.crypto")

_ENC_PREFIX = "ENC:"

_APP_SECRET = "spee4ka-2025-secret-salt"


def _get_volume_serial() -> str:
    kernel32 = ctypes.windll.kernel32
    serial = ctypes.c_uint32()
    result = kernel32.GetVolumeInformationW(
        "C:\\", None, 0,
        ctypes.byref(serial),
        None, None, None, 0,
    )
    if result:
        return f"{serial.value:08X}"
    return "FALLBACK"


def _derive_key() -> bytes:
    machine_id = _get_volume_serial()
    combined = f"{machine_id}:{_APP_SECRET}".encode("utf-8")
    digest = hashlib.sha256(combined).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plaintext: str) -> str:
    from cryptography.fernet import Fernet
    key = _derive_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode("utf-8"))
    return f"{_ENC_PREFIX}{encrypted.decode('ascii')}"


def decrypt_value(value: str) -> str:
    if not value.startswith(_ENC_PREFIX):
        return value
    from cryptography.fernet import Fernet
    key = _derive_key()
    f = Fernet(key)
    token = value[len(_ENC_PREFIX):].encode("ascii")
    try:
        return f.decrypt(token).decode("utf-8")
    except Exception as ex:
        log.warning(f"Decryption failed: {ex}")
        return value


def is_encrypted(value: str) -> bool:
    return value.startswith(_ENC_PREFIX)


def encrypt_env_file(env_path: Path):
    if not env_path.exists():
        return
    lines = []
    changed = False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("YANDEX_") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip()
            if (
                value
                and not is_encrypted(value)
                and not value.startswith("AQVN_paste")
                and not value.startswith("b1g_paste")
            ):
                try:
                    encrypted = encrypt_value(value)
                    lines.append(f"{key}={encrypted}")
                    changed = True
                except Exception as ex:
                    log.warning(f"Failed to encrypt {key}: {ex}")
                    lines.append(line)
            else:
                lines.append(line)
        else:
            lines.append(line)
    if changed:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info(f"Encrypted sensitive values in {env_path}")


def decrypt_env_values(env_path: Path) -> dict:
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("YANDEX_") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip()
            if value and is_encrypted(value):
                result[key] = decrypt_value(value)
            else:
                result[key] = value
    return result
