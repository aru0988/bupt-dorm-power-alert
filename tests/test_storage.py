import pytest

from alert_logic import DEFAULT_TEMPLATE
import storage


def test_load_config_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        storage.load_config(tmp_path / "missing.ini")


def test_load_config_reads_values(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[alert]\nthreshold_kwh = 10\n", encoding="utf-8")
    cfg = storage.load_config(path)
    assert cfg.getfloat("alert", "threshold_kwh") == 10.0


def test_state_roundtrip_and_corrupt(tmp_path):
    path = tmp_path / "state.json"
    assert storage.load_state(path) == {}
    storage.save_state(path, {"a": 1})
    assert storage.load_state(path) == {"a": 1}
    path.write_text("{bad", encoding="utf-8")
    assert storage.load_state(path) == {}


def test_template_precedence(tmp_path):
    (tmp_path / "message_template.example.txt").write_text(
        "example {room}", encoding="utf-8")
    assert storage.load_template(tmp_path) == "example {room}"
    (tmp_path / "message_template.txt").write_text(
        "local {room}", encoding="utf-8")
    assert storage.load_template(tmp_path) == "local {room}"
    (tmp_path / "message_template.txt").unlink()
    (tmp_path / "message_template.example.txt").unlink()
    assert storage.load_template(tmp_path) == DEFAULT_TEMPLATE
