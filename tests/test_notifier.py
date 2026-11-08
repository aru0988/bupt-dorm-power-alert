from unittest.mock import Mock

import pytest
import requests

import notifier


def test_send_serverchan_success(monkeypatch):
    resp = Mock(status_code=200)
    resp.json.return_value = {"code": 0, "message": ""}
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: resp)
    notifier.send_serverchan("SCTkey", "标题", "正文")


def test_send_serverchan_error_code(monkeypatch):
    resp = Mock(status_code=200)
    resp.json.return_value = {"code": 40001, "message": "错误的Key"}
    monkeypatch.setattr(notifier.requests, "post", lambda *a, **k: resp)
    with pytest.raises(notifier.PushError):
        notifier.send_serverchan("SCTkey", "标题", "正文")


def test_send_serverchan_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(notifier.requests, "post", boom)
    with pytest.raises(notifier.PushError):
        notifier.send_serverchan("SCTkey", "标题", "正文")


def test_send_serverchan_non_200(monkeypatch):
    monkeypatch.setattr(notifier.requests, "post",
                        lambda *a, **k: Mock(status_code=500, text="err"))
    with pytest.raises(notifier.PushError):
        notifier.send_serverchan("SCTkey", "标题", "正文")
