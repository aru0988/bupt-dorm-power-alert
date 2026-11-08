from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

import requests

BASE_URL = "https://xsgyfk.bupt.edu.cn"


class ApiError(RuntimeError):
    pass


class AuthExpired(ApiError):
    pass


class XsgyfkClient:
    def __init__(self, cookie: str, base_url: str = BASE_URL,
                 session: requests.Session | None = None, retries: int = 2,
                 backoff: tuple[float, ...] = (2.0, 5.0)):
        self._session = session or requests.Session()
        self._session.cookies.set(".AspNetCore.Cookies", cookie,
                                  domain="xsgyfk.bupt.edu.cn", path="/")
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        })
        self._base = base_url.rstrip("/")
        self._retries = retries
        self._backoff = backoff

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                resp = self._session.get(self._base + path, params=params,
                                         timeout=20, allow_redirects=False)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if resp.status_code in (301, 302, 401):
                    raise AuthExpired("登录会话已过期")
                if resp.status_code >= 500:
                    last_error = ApiError(f"HTTP {resp.status_code}")
                elif resp.status_code >= 400:
                    raise ApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                else:
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" not in content_type:
                        raise AuthExpired("登录会话已过期（返回非 JSON）")
                    return resp.json()
            if attempt < self._retries:
                time.sleep(self._backoff[min(attempt, len(self._backoff) - 1)])
        raise ApiError(str(last_error) if last_error else "请求失败")

    def get_reading(self, meter_no: str) -> dict[str, Any]:
        return self._get(f"/api/Common/Reading/{meter_no}")

    def get_usages(self, meter_no: str, days: int = 7) -> dict[str, Any]:
        end = date.today()
        begin = end - timedelta(days=days)
        return self._get(f"/api/Common/Usages/{meter_no}", params={
            "type": "D",
            "begin": begin.isoformat(),
            "end": end.isoformat(),
        })

    def get_payview(self, cls: int = 2) -> dict[str, Any]:
        return self._get("/api/Common/PayView", params={"cls": cls})

    def get_meters(self) -> list[dict[str, Any]]:
        data = self._get("/api/User/meters")
        return data if isinstance(data, list) else []
