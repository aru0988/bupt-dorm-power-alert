from __future__ import annotations

import base64
import configparser
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HOST = "xsgyfk.bupt.edu.cn"
COOKIE_NAME = ".AspNetCore.Cookies"
PROFILE_ROOT = Path(os.path.expandvars(
    r"%APPDATA%\Tencent\xwechat\radium\web\profiles"))
LOCAL_STATE = PROFILE_ROOT.parent / "Local State"


class CookieRefreshError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def dpapi_unprotect(data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data)
    blob_in = DATA_BLOB(len(data),
                        ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0,
            ctypes.byref(blob_out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def get_chromium_key(local_state: Path) -> bytes:
    data = json.loads(local_state.read_text(encoding="utf-8"))
    encrypted = base64.b64decode(data["os_crypt"]["encrypted_key"])
    if encrypted[:5] != b"DPAPI":
        raise CookieRefreshError("Local State 的密钥格式不是 DPAPI")
    return dpapi_unprotect(encrypted[5:])


def decrypt_cookie(encrypted_value: bytes, key: bytes, host: str) -> str:
    if encrypted_value[:3] not in (b"v10", b"v11"):
        raise CookieRefreshError("Cookie 加密前缀不是 v10/v11")
    plain = AESGCM(key).decrypt(encrypted_value[3:15], encrypted_value[15:], None)
    if plain[:32] == hashlib.sha256(host.encode()).digest():
        plain = plain[32:]
    return plain.decode("utf-8")


def find_cookie_dbs(root: Path) -> list[Path]:
    return sorted(root.glob("*/Network/Cookies"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def vss_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["esentutl", "/y", "/vss", str(src), "/d", str(dst)],
        capture_output=True, text=True)
    if result.returncode != 0 or not dst.exists():
        detail = result.stderr.strip() or result.stdout.strip()
        raise CookieRefreshError(f"卷影复制失败（需要管理员权限）：{detail}")


def extract_cookie(db_path: Path, key: bytes) -> str:
    con = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        row = con.execute(
            "select encrypted_value from cookies where host_key=? and name=?",
            (HOST, COOKIE_NAME)).fetchone()
    finally:
        con.close()
    if not row:
        raise CookieRefreshError(
            "Cookie 库里没有 xsgyfk 的会话，请先在电脑微信打开公寓缴费页面")
    return decrypt_cookie(bytes(row[0]), key, HOST)


def update_config(path: Path, cookie: str) -> None:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("auth"):
        cfg.add_section("auth")
    cfg.set("auth", "aspnet_cookie", cookie)
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def verify_cookie(cookie: str) -> None:
    session = requests.Session()
    session.cookies.set(COOKIE_NAME, cookie, domain=HOST, path="/")
    resp = session.get(f"https://{HOST}/api/User", timeout=20,
                       allow_redirects=False)
    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or "application/json" not in content_type:
        raise CookieRefreshError(f"新 Cookie 验证失败：HTTP {resp.status_code}")


def main() -> int:
    if not is_admin():
        print("请右键以管理员身份运行 refresh_cookie.bat（需要卷影复制）。")
        return 1
    base = Path(__file__).resolve().parent
    config_path = base / "config.ini"
    if not config_path.exists():
        print(f"缺少配置文件：{config_path}，请先复制 config.example.ini 为 config.ini")
        return 1
    if not LOCAL_STATE.exists():
        print(f"找不到微信 Local State：{LOCAL_STATE}")
        return 1

    try:
        key = get_chromium_key(LOCAL_STATE)
    except Exception as exc:
        print(f"读取微信密钥失败：{exc}")
        return 1

    temp_dir = Path(tempfile.mkdtemp(prefix="dorm_cookie_"))
    try:
        for db in find_cookie_dbs(PROFILE_ROOT):
            copy = temp_dir / "Cookies"
            try:
                vss_copy(db, copy)
                cookie = extract_cookie(copy, key)
                verify_cookie(cookie)
            except Exception as exc:
                print(f"尝试 {db.parent.parent.name} 失败：{exc}")
                continue
            update_config(config_path, cookie)
            print(f"会话已刷新（Cookie 长度 {len(cookie)}）。")
            return 0
        print("未找到可用的 xsgyfk 会话。请先在电脑微信打开一次公寓缴费页面，再重试。")
        return 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    input("按回车退出...")
    sys.exit(code)
