import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from crypto_utils import _get_volume_serial, encrypt_value, decrypt_value, is_encrypted

log = logging.getLogger("spee4ka.license")

SERVER_URL = "https://spee4ka.ru"
MACHINE_ID = _get_volume_serial()

GRACE_PERIOD_DAYS = 30
CHECK_INTERVAL_SEC = 24 * 3600


def _license_path(root: Path) -> Path:
    return root / "license.dat"


def _read_local(root: Path) -> Optional[dict]:
    p = _license_path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data["key"] = decrypt_value(data.get("key", ""))
        data["machine_id"] = decrypt_value(data.get("machine_id", ""))
        return data
    except Exception as ex:
        log.warning(f"Failed to read license cache: {ex}")
        return None


def _write_local(root: Path, key: str, status: str, expires: str, checked_at: float):
    p = _license_path(root)
    data = {
        "key": encrypt_value(key),
        "machine_id": encrypt_value(MACHINE_ID),
        "status": status,
        "expires": expires,
        "checked_at": checked_at,
    }
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def get_saved_key(root: Path) -> str:
    local = _read_local(root)
    if local and local.get("key"):
        return local["key"]
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("SPEE4KA_LICENSE="):
                val = line.split("=", 1)[1].strip()
                if val and is_encrypted(val):
                    return decrypt_value(val)
                return val
    return ""


def activate(key: str, root: Path) -> dict:
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/activate",
            json={"key": key, "machine_id": MACHINE_ID},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("valid"):
            _write_local(root, key, "active", data.get("expires", ""), time.time())
            log.info(f"License activated: {key[:9]}...")
            return {"ok": True, "expires": data.get("expires", "")}
        return {"ok": False, "error": data.get("error", "Activation failed")}
    except requests.RequestException as ex:
        log.warning(f"Activation network error: {ex}")
        return {"ok": False, "error": "No connection to license server"}


def check(root: Path) -> dict:
    key = get_saved_key(root)
    if not key:
        return {"valid": False, "error": "no_key"}

    local = _read_local(root)
    if local and local.get("machine_id") != MACHINE_ID:
        return {"valid": False, "error": "machine_mismatch"}

    try:
        resp = requests.post(
            f"{SERVER_URL}/api/check",
            json={"key": key, "machine_id": MACHINE_ID},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("valid"):
            _write_local(root, key, "active", data.get("expires", ""), time.time())
            return {"valid": True, "expires": data.get("expires", "")}
        _clear_local(root)
        return {"valid": False, "error": data.get("error", "invalid")}
    except requests.RequestException as ex:
        log.warning(f"License check network error: {ex}")
        if local:
            elapsed = time.time() - local.get("checked_at", 0)
            if elapsed < GRACE_PERIOD_DAYS * 86400:
                log.info(f"Grace period: {elapsed / 86400:.1f} days since last check")
                return {"valid": True, "expires": local.get("expires", ""), "grace": True}
            return {"valid": False, "error": "grace_expired"}
        return {"valid": False, "error": "no_connection"}


def _clear_local(root: Path):
    p = _license_path(root)
    if p.exists():
        p.unlink()


def is_licensed(root: Path) -> bool:
    return check(root).get("valid", False)
