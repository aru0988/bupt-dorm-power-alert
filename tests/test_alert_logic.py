import pytest

from alert_logic import (DEFAULT_TEMPLATE, Reading, TemplateError, UsageStats,
                         build_message_values, compute_days_left,
                         compute_usage_stats, parse_reading, render_message,
                         should_alert)


def test_parse_reading():
    reading = parse_reading({"shengYu": 100.0, "readingDate": "2026-11-08T23:12:00"})
    assert reading == Reading(balance=100.0, reading_time="2026-11-08 23:12")


def test_compute_usage_stats_from_cumulative():
    usages = {
        "totalUsage": 26.03,
        "details": [
            {"chaoBiao": "2026-11-02T00:00:00", "zongLiang": 2598.86},
            {"chaoBiao": "2026-11-03T00:00:00", "zongLiang": 2603.65},
            {"chaoBiao": "2026-11-04T00:00:00", "zongLiang": 2607.71},
            {"chaoBiao": "2026-11-05T00:00:00", "zongLiang": 2611.79},
            {"chaoBiao": "2026-11-06T00:00:00", "zongLiang": 2617.03},
            {"chaoBiao": "2026-11-07T00:00:00", "zongLiang": 2620.91},
            {"chaoBiao": "2026-11-08T00:00:00", "zongLiang": 2624.89},
            {"chaoBiao": "2026-11-09T00:00:00", "zongLiang": None},
        ],
    }
    stats = compute_usage_stats(usages)
    assert round(stats.total, 2) == 26.03
    assert round(stats.avg_daily, 2) == 4.34


def test_compute_usage_stats_fallback():
    stats = compute_usage_stats({"totalUsage": 14.0, "details": []})
    assert stats.total == 14.0
    assert stats.avg_daily == 2.0


def test_compute_days_left():
    assert compute_days_left(100.0, 4.34) == 23.0
    assert compute_days_left(10.0, None) is None
    assert compute_days_left(10.0, 0) is None


def test_build_message_values():
    reading = Reading(8.4, "2026-11-08 23:12")
    payview = {
        "room": {"roomNo": "1-1-101", "campus": "测试校区",
                 "building": "1号楼", "floor": "1层"},
        "meter": {"price": 0.48, "huming": "1-1-101"},
    }
    values = build_message_values(reading, payview, UsageStats(4.34, 26.03))
    assert values["room"] == "1-1-101"
    assert values["campus"] == "测试校区"
    assert values["building"] == "1号楼"
    assert values["floor"] == "1层"
    assert values["balance"] == "8.4"
    assert values["price"] == "0.48"
    assert values["money"] == "4.03"
    assert values["avg_usage"] == "4.34"
    assert values["days_left"] == "1.9"
    assert values["reading_time"] == "2026-11-08 23:12"


def test_build_message_values_missing_data():
    reading = Reading(8.4, "")
    values = build_message_values(reading, {}, UsageStats(None, None))
    assert values["room"] == "-"
    assert values["price"] == "-"
    assert values["money"] == "-"
    assert values["avg_usage"] == "-"
    assert values["days_left"] == "-"
    assert values["reading_time"] == "-"


def test_render_message_default():
    values = {
        "room": "1-1-101", "campus": "测试校区", "building": "1号楼",
        "floor": "1层", "balance": "8.4", "price": "0.48", "money": "4.03",
        "avg_usage": "4.34", "days_left": "1.9", "reading_time": "2026-11-08 23:12",
    }
    text = render_message(DEFAULT_TEMPLATE, values)
    assert "剩余：8.4 度" in text
    assert "预计可用：约 1.9 天" in text


def test_render_message_unknown_placeholder():
    with pytest.raises(TemplateError):
        render_message("{unknown}", {})


def test_should_alert():
    assert should_alert(10.0, 10.0, None, "2026-11-09") is True
    assert should_alert(10.0, 10.0, "2026-11-09", "2026-11-09") is False
    assert should_alert(10.1, 10.0, None, "2026-11-09") is False
