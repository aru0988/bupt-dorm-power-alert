from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

from alert_logic import (DEFAULT_TEMPLATE, TemplateError, build_message_values,
                         compute_usage_stats, parse_reading, render_message,
                         should_alert)
from notifier import PushError, send_serverchan
from storage import load_config, load_state, load_template, save_state
from xsgyfk_client import ApiError, AuthExpired, XsgyfkClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")

LOG = logging.getLogger("dorm_alert")
Notifier = Callable[[str, str, str], None]


@dataclass(frozen=True)
class Settings:
    cookie: str
    meter_no: str
    cls: int
    threshold: float
    title: str
    sendkey: str


@dataclass
class AlertResult:
    balance: float
    avg_daily: float | None
    days_left: float | None
    price: float | None
    money: float | None
    message: str
    below: bool
    alerted: bool
    reset: bool
    template_fallback: bool = False


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_settings(cfg) -> Settings:
    cookie = cfg.get("auth", "aspnet_cookie", fallback="").strip()
    meter_no = cfg.get("meter", "meter_no", fallback="").strip()
    sendkey = cfg.get("push", "serverchan_sendkey", fallback="").strip()
    if not cookie:
        raise ValueError("config.ini 缺少 [auth] aspnet_cookie，请先运行 refresh_cookie.bat")
    if not meter_no:
        raise ValueError("config.ini 缺少 [meter] meter_no")
    if not sendkey:
        raise ValueError("config.ini 缺少 [push] serverchan_sendkey")
    return Settings(
        cookie=cookie,
        meter_no=meter_no,
        cls=cfg.getint("meter", "cls", fallback=2),
        threshold=cfg.getfloat("alert", "threshold_kwh", fallback=10.0),
        title=cfg.get("message", "title", fallback="⚠️ 宿舍电量预警").strip(),
        sendkey=sendkey,
    )


def run_once(settings: Settings, state: dict, client: Any, notifier: Notifier,
             template: str, today: str, dry_run: bool = False,
             force_alert: bool = False) -> AlertResult:
    reading = parse_reading(client.get_reading(settings.meter_no))
    stats = compute_usage_stats(client.get_usages(settings.meter_no))
    payview = client.get_payview(settings.cls)
    values = build_message_values(reading, payview, stats)
    fallback = False
    try:
        message = render_message(template, values)
    except TemplateError:
        fallback = True
        message = render_message(DEFAULT_TEMPLATE, values)

    below = reading.balance <= settings.threshold
    alert_due = below and (force_alert or should_alert(
        reading.balance, settings.threshold, state.get("last_alert_date"), today))
    alerted = False
    reset = False

    if dry_run:
        return AlertResult(
            balance=reading.balance, avg_daily=stats.avg_daily,
            days_left=_safe_float(values["days_left"]),
            price=_safe_float(values["price"]),
            money=_safe_float(values["money"]),
            message=message, below=below, alerted=False, reset=False,
            template_fallback=fallback)

    if alert_due:
        notifier(settings.sendkey, settings.title, message)
        state["last_alert_date"] = today
        state["last_alert_sent_at"] = datetime.now().isoformat(timespec="seconds")
        alerted = True
    elif not below:
        if state.get("last_alert_date") is not None:
            reset = True
        state["last_alert_date"] = None

    state["consecutive_failures"] = 0
    state["last_success_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_balance"] = reading.balance
    return AlertResult(
        balance=reading.balance, avg_daily=stats.avg_daily,
        days_left=_safe_float(values["days_left"]),
        price=_safe_float(values["price"]),
        money=_safe_float(values["money"]),
        message=message, below=below, alerted=alerted, reset=reset,
        template_fallback=fallback)


def handle_failure(state: dict, settings: Settings, notifier: Notifier,
                   today: str, error: Exception, kind: str) -> bool:
    state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
    key = "last_auth_notice_date" if kind == "auth" else "last_failure_notice_date"
    if kind == "generic" and state["consecutive_failures"] < 3:
        return False
    if state.get(key) == today:
        return False
    if kind == "auth":
        title = "宿舍电量预警：登录已过期"
        body = ("查询宿舍电量失败：登录会话已过期。\n\n"
                "请在电脑微信中打开一次「公寓缴费」页面，然后双击项目目录下的 "
                "refresh_cookie.bat 刷新会话。")
    else:
        title = "宿舍电量预警：连续查询失败"
        body = f"宿舍电量连续查询失败：{error}\n\n请检查网络或运行 --dry-run 查看日志。"
    try:
        notifier(settings.sendkey, title, body)
    except Exception:
        LOG.exception("发送异常提醒失败")
        return False
    state[key] = today
    return True


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    LOG.setLevel(logging.INFO)
    LOG.addHandler(handler)
    LOG.addHandler(stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="宿舍电量预警")
    parser.add_argument("--dry-run", action="store_true",
                        help="只查询并打印，不推送、不改状态")
    parser.add_argument("--test-push", action="store_true",
                        help="发送一条测试推送")
    parser.add_argument("--threshold", type=float,
                        help="临时覆盖阈值（度）")
    parser.add_argument("--force-alert", action="store_true",
                        help="忽略每日一次限制（仅测试）")
    parser.add_argument("--config", type=Path, default=None,
                        help="配置文件路径")
    args = parser.parse_args(argv)

    base = Path(__file__).resolve().parent
    config_path = args.config or (base / "config.ini")
    state_path = base / "state.json"
    setup_logging(base / "logs" / "alert.log")

    try:
        cfg = load_config(config_path)
        settings = load_settings(cfg)
        if args.threshold is not None:
            settings = Settings(settings.cookie, settings.meter_no, settings.cls,
                                args.threshold, settings.title, settings.sendkey)
        if args.test_push:
            send_serverchan(
                settings.sendkey, "宿舍电量预警测试",
                "如果你收到这条消息，说明 Server酱 推送已经打通。\n\n"
                "这是测试消息，不需要操作。")
            print("测试消息已发送，请检查微信（Server酱 公众号）。")
            return 0

        state = load_state(state_path)
        template = load_template(base)
        client = XsgyfkClient(settings.cookie)
        today = date.today().isoformat()
        result = run_once(settings, state, client, send_serverchan, template,
                          today, dry_run=args.dry_run,
                          force_alert=args.force_alert)
        if args.dry_run:
            print(f"当前：{result.balance:.1f} 度，日均 "
                  f"{result.avg_daily if result.avg_daily is not None else '-'} 度/天，"
                  f"预计 {result.days_left if result.days_left is not None else '-'} 天")
            print(f"阈值：{settings.threshold:.1f} 度 → "
                  f"{'低于阈值' if result.below else '未低于阈值'}")
            print(f"金额：约 {result.money if result.money is not None else '-'} 元，"
                  f"单价 {result.price if result.price is not None else '-'} 元/度")
            if result.template_fallback:
                print("模板占位符有误，已使用默认模板。")
            print("文案预览：")
            print(result.message)
            return 0

        save_state(state_path, state)
        LOG.info("查询成功 balance=%.1f avg=%s days_left=%s alerted=%s",
                 result.balance, result.avg_daily, result.days_left, result.alerted)
        if result.alerted:
            LOG.info("已发送预警推送")
        return 0
    except AuthExpired as exc:
        settings = locals().get("settings")
        state = locals().get("state", {})
        if settings is not None:
            handle_failure(state, settings, send_serverchan,
                           date.today().isoformat(), exc, "auth")
            save_state(state_path, state)
        LOG.error("登录会话过期：%s", exc)
        return 2
    except (ApiError, PushError, FileNotFoundError, ValueError, KeyError) as exc:
        settings = locals().get("settings")
        state = locals().get("state", {})
        if settings is not None:
            handle_failure(state, settings, send_serverchan,
                           date.today().isoformat(), exc, "generic")
            save_state(state_path, state)
        LOG.error("查询失败：%s", exc)
        return 1
    except Exception as exc:
        LOG.exception("未预期错误：%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
