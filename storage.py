from __future__ import annotations

import configparser
import json
import os
from pathlib import Path

from alert_logic import DEFAULT_TEMPLATE


def load_config(path: Path) -> configparser.ConfigParser:
    if not path.exists():
        raise FileNotFoundError(
            f"配置文件不存在：{path}，请复制 config.example.ini 为 config.ini")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path, encoding="utf-8")
    return cfg


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_template(script_dir: Path) -> str:
    for name in ("message_template.txt", "message_template.example.txt"):
        path = script_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return DEFAULT_TEMPLATE
