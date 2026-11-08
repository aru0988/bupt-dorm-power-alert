from __future__ import annotations

import requests


class PushError(RuntimeError):
    pass


def send_serverchan(sendkey: str, title: str, body: str, timeout: int = 20) -> None:
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": body}, timeout=timeout)
    except requests.RequestException as exc:
        raise PushError(str(exc)) from exc
    if resp.status_code != 200:
        raise PushError(f"HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise PushError("推送服务返回了非 JSON 响应") from exc
    if payload.get("code") != 0:
        raise PushError(f"code={payload.get('code')} message={payload.get('message')}")
