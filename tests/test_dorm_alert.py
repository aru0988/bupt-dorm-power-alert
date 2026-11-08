import pytest

from dorm_alert import Settings, handle_failure, run_once


class FakeClient:
    def __init__(self, balance=8.4, avg=4.34, price=0.48):
        self.balance = balance
        self.avg = avg
        self.price = price

    def get_reading(self, meter_no):
        return {"shengYu": self.balance, "readingDate": "2026-11-08T23:12:00"}

    def get_usages(self, meter_no):
        return {"totalUsage": self.avg, "details": [
            {"chaoBiao": "2026-11-07T00:00:00", "zongLiang": 0.0},
            {"chaoBiao": "2026-11-08T00:00:00", "zongLiang": self.avg},
        ]}

    def get_payview(self, cls):
        return {"room": {"roomNo": "1-1-101", "campus": "测试校区",
                         "building": "1号楼", "floor": "1层"},
                "meter": {"price": self.price}}


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def __call__(self, sendkey, title, body):
        self.calls.append((sendkey, title, body))


def make_settings(threshold=10.0):
    return Settings(cookie="c", meter_no="m", cls=2, threshold=threshold,
                    title="⚠️ 宿舍电量预警", sendkey="k")


def test_run_once_alerts_once_per_day():
    client = FakeClient(balance=8.4)
    notifier = FakeNotifier()
    state = {}
    today = "2026-11-09"
    result = run_once(make_settings(), state, client, notifier,
                      "{room} {balance}", today)
    assert result.alerted is True
    assert notifier.calls and "8.4" in notifier.calls[0][2]
    assert state["last_alert_date"] == today
    assert state["consecutive_failures"] == 0

    result2 = run_once(make_settings(), state, client, notifier,
                       "{room} {balance}", today)
    assert result2.alerted is False
    assert len(notifier.calls) == 1


def test_run_once_resets_when_above_threshold():
    client = FakeClient(balance=100.0)
    notifier = FakeNotifier()
    state = {"last_alert_date": "2026-11-08"}
    result = run_once(make_settings(), state, client, notifier,
                      "{balance}", "2026-11-09")
    assert result.below is False
    assert result.reset is True
    assert state["last_alert_date"] is None


def test_run_once_dry_run_does_not_push_or_mutate():
    client = FakeClient(balance=8.4)
    notifier = FakeNotifier()
    state = {}
    result = run_once(make_settings(), state, client, notifier,
                      "{balance}", "2026-11-09", dry_run=True)
    assert result.message == "8.4"
    assert result.alerted is False
    assert notifier.calls == []
    assert state == {}


def test_run_once_force_alert():
    client = FakeClient(balance=8.4)
    notifier = FakeNotifier()
    state = {"last_alert_date": "2026-11-09"}
    result = run_once(make_settings(), state, client, notifier,
                      "{balance}", "2026-11-09", force_alert=True)
    assert result.alerted is True
    assert len(notifier.calls) == 1


def test_handle_failure_generic_threshold():
    notifier = FakeNotifier()
    state = {"consecutive_failures": 1}
    assert handle_failure(state, make_settings(), notifier, "2026-11-09",
                          Exception("boom"), "generic") is False
    state["consecutive_failures"] = 2
    assert handle_failure(state, make_settings(), notifier, "2026-11-09",
                          Exception("boom"), "generic") is True
    assert len(notifier.calls) == 1
    assert state["last_failure_notice_date"] == "2026-11-09"


def test_handle_failure_auth_notice_once():
    notifier = FakeNotifier()
    state = {}
    assert handle_failure(state, make_settings(), notifier, "2026-11-09",
                          Exception("auth"), "auth") is True
    assert handle_failure(state, make_settings(), notifier, "2026-11-09",
                          Exception("auth"), "auth") is False
    assert len(notifier.calls) == 1
