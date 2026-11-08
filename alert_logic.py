from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_TEMPLATE = """⚠️ 宿舍电量预警
房间：{room}（{campus} {building} {floor}）
剩余：{balance} 度（约 {money} 元，单价 {price} 元/度）
近 7 天日均：{avg_usage} 度/天
预计可用：约 {days_left} 天
抄表时间：{reading_time}
请及时充值
"""


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class Reading:
    balance: float
    reading_time: str


@dataclass(frozen=True)
class UsageStats:
    avg_daily: float | None
    total: float | None


def parse_reading(data: dict[str, Any]) -> Reading:
    balance = float(data["shengYu"])
    raw = str(data.get("readingDate") or "")
    reading_time = raw.replace("T", " ")[:16] if raw else "-"
    return Reading(balance=balance, reading_time=reading_time)


def compute_usage_stats(usages: dict[str, Any], days: int = 7) -> UsageStats:
    valid: list[tuple[str, float]] = []
    for item in usages.get("details") or []:
        value = item.get("zongLiang")
        if value is None:
            continue
        try:
            valid.append((str(item.get("chaoBiao") or ""), float(value)))
        except (TypeError, ValueError):
            continue
    valid.sort(key=lambda pair: pair[0])
    points = [value for _, value in valid]
    diffs = [b - a for a, b in zip(points, points[1:]) if b >= a]
    if diffs:
        total = sum(diffs)
        return UsageStats(avg_daily=total / len(diffs), total=total)
    total_usage = usages.get("totalUsage")
    if total_usage is None:
        return UsageStats(avg_daily=None, total=None)
    try:
        total = float(total_usage)
    except (TypeError, ValueError):
        return UsageStats(avg_daily=None, total=None)
    return UsageStats(avg_daily=total / days if days > 0 else None, total=total)


def compute_days_left(balance: float, avg_daily: float | None) -> float | None:
    if not avg_daily or avg_daily <= 0:
        return None
    return round(balance / avg_daily, 1)


def build_message_values(reading: Reading, payview: dict[str, Any],
                         stats: UsageStats) -> dict[str, str]:
    room = payview.get("room") or {}
    meter = payview.get("meter") or {}
    price_raw = meter.get("price")
    try:
        price = float(price_raw) if price_raw is not None else None
    except (TypeError, ValueError):
        price = None
    money = reading.balance * price if price is not None else None
    days_left = compute_days_left(reading.balance, stats.avg_daily)
    return {
        "room": str(room.get("roomNo") or meter.get("huming") or "-"),
        "campus": str(room.get("campus") or "-"),
        "building": str(room.get("building") or "-"),
        "floor": str(room.get("floor") or "-"),
        "balance": f"{reading.balance:.1f}",
        "price": f"{price:.2f}" if price is not None else "-",
        "money": f"{money:.2f}" if money is not None else "-",
        "avg_usage": f"{stats.avg_daily:.2f}" if stats.avg_daily is not None else "-",
        "days_left": f"{days_left:.1f}" if days_left is not None else "-",
        "reading_time": reading.reading_time or "-",
    }


def render_message(template: str, values: dict[str, str]) -> str:
    try:
        return template.format(**values).strip()
    except (KeyError, ValueError, IndexError) as exc:
        raise TemplateError(str(exc)) from exc


def should_alert(balance: float, threshold: float, last_alert_date: str | None,
                 today: str) -> bool:
    return balance <= threshold and last_alert_date != today
