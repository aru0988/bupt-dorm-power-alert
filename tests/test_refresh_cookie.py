import hashlib
import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import refresh_cookie


def test_decrypt_cookie_with_host_hash():
    key = b"0" * 32
    host = "xsgyfk.bupt.edu.cn"
    plain = hashlib.sha256(host.encode()).digest() + b"cookie-value"
    nonce = b"123456789012"
    ct = AESGCM(key).encrypt(nonce, plain, None)
    encrypted = b"v10" + nonce + ct
    assert refresh_cookie.decrypt_cookie(encrypted, key, host) == "cookie-value"


def test_decrypt_cookie_without_host_hash():
    key = b"1" * 32
    host = "xsgyfk.bupt.edu.cn"
    nonce = b"abcdefghijkl"
    ct = AESGCM(key).encrypt(nonce, b"plain-cookie", None)
    encrypted = b"v10" + nonce + ct
    assert refresh_cookie.decrypt_cookie(encrypted, key, host) == "plain-cookie"


def test_decrypt_cookie_bad_prefix():
    with pytest.raises(refresh_cookie.CookieRefreshError):
        refresh_cookie.decrypt_cookie(b"nope", b"0" * 32, "host")


def test_update_config(tmp_path):
    config = tmp_path / "config.ini"
    config.write_text("[auth]\naspnet_cookie = old\n\n[meter]\nmeter_no = x\n",
                      encoding="utf-8")
    refresh_cookie.update_config(config, "new-cookie")
    text = config.read_text(encoding="utf-8")
    assert "new-cookie" in text
    assert "meter_no = x" in text


def test_find_cookie_dbs(tmp_path):
    a = tmp_path / "multitab_a" / "Network"
    b = tmp_path / "multitab_b" / "Network"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "Cookies").write_bytes(b"a")
    (b / "Cookies").write_bytes(b"b")
    os.utime(a / "Cookies", (1, 1))
    os.utime(b / "Cookies", (2, 2))
    dbs = refresh_cookie.find_cookie_dbs(tmp_path)
    assert dbs[0].parent.parent.name == "multitab_b"
