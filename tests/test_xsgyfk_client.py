from unittest.mock import Mock

import pytest

import xsgyfk_client
from xsgyfk_client import ApiError, AuthExpired, XsgyfkClient


class FakeResponse:
    def __init__(self, status=200, payload=None,
                 content_type="application/json", text=""):
        self.status_code = status
        self._payload = payload
        self.headers = {"Content-Type": content_type}
        self.text = text

    def json(self):
        return self._payload


def make_client(session):
    return XsgyfkClient("cookie-value", session=session, retries=2, backoff=(0, 0))


def test_get_reading_success():
    session = Mock()
    session.get.return_value = FakeResponse(payload={"shengYu": 100.0})
    client = make_client(session)
    assert client.get_reading("000000000000") == {"shengYu": 100.0}
    args, kwargs = session.get.call_args
    assert args[0].endswith("/api/Common/Reading/000000000000")
    assert kwargs["allow_redirects"] is False


def test_401_raises_auth_expired_without_retry():
    session = Mock()
    session.get.return_value = FakeResponse(status=401)
    client = make_client(session)
    with pytest.raises(AuthExpired):
        client.get_reading("x")
    assert session.get.call_count == 1


def test_302_raises_auth_expired_without_retry():
    session = Mock()
    session.get.return_value = FakeResponse(status=302)
    client = make_client(session)
    with pytest.raises(AuthExpired):
        client.get_reading("x")
    assert session.get.call_count == 1


def test_500_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(xsgyfk_client.time, "sleep", lambda _: None)
    session = Mock()
    session.get.side_effect = [
        FakeResponse(status=500, text="err"),
        FakeResponse(payload={"ok": True}),
    ]
    client = make_client(session)
    assert client.get_reading("x") == {"ok": True}
    assert session.get.call_count == 2


def test_500_all_retries_raises(monkeypatch):
    monkeypatch.setattr(xsgyfk_client.time, "sleep", lambda _: None)
    session = Mock()
    session.get.return_value = FakeResponse(status=500, text="err")
    client = make_client(session)
    with pytest.raises(ApiError):
        client.get_reading("x")
    assert session.get.call_count == 3


def test_non_json_200_is_auth_expired():
    session = Mock()
    session.get.return_value = FakeResponse(
        content_type="text/html", text="<html>login</html>")
    client = make_client(session)
    with pytest.raises(AuthExpired):
        client.get_reading("x")


def test_get_usages_params():
    session = Mock()
    session.get.return_value = FakeResponse(payload={"totalUsage": 1.0})
    client = make_client(session)
    client.get_usages("000000000000", days=7)
    args, kwargs = session.get.call_args
    assert args[0].endswith("/api/Common/Usages/000000000000")
    assert kwargs["params"]["type"] == "D"
    assert "begin" in kwargs["params"] and "end" in kwargs["params"]


def test_get_payview_params():
    session = Mock()
    session.get.return_value = FakeResponse(payload={"meter": {}})
    client = make_client(session)
    client.get_payview(2)
    args, kwargs = session.get.call_args
    assert args[0].endswith("/api/Common/PayView")
    assert kwargs["params"] == {"cls": 2}


def test_get_meters_list():
    session = Mock()
    session.get.return_value = FakeResponse(payload=[{"meterNo": "x"}])
    client = make_client(session)
    assert client.get_meters() == [{"meterNo": "x"}]
