"""Tests for config loader and schema."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from src.config.loader import ConfigValidationError, load_config
from src.config.schema import AppConfig, ScheduleConfig, ThresholdsConfig


class TestConfigDefaults:
    def test_default_config_loads(self, tmp_path):
        """Empty JSON → all defaults."""
        p = tmp_path / "config.json"
        p.write_text("{}")
        cfg = load_config(str(p))
        assert isinstance(cfg, AppConfig)
        assert cfg.schedule.start_time_msk == "08:00"
        assert cfg.schedule.interval_hours == 4
        assert cfg.kush.dry_run is True
        assert cfg.thresholds.roi == 0.05

    def test_missing_file_uses_defaults(self, tmp_path):
        """Non-existent file → all defaults."""
        cfg = load_config(str(tmp_path / "nonexistent.json"))
        assert isinstance(cfg, AppConfig)
        assert cfg.schedule.interval_hours == 4

    def test_partial_json(self, tmp_path):
        """Only some keys → rest are defaults."""
        p = tmp_path / "config.json"
        p.write_text(json.dumps({"schedule": {"interval_hours": 6}}))
        cfg = load_config(str(p))
        assert cfg.schedule.interval_hours == 6
        assert cfg.schedule.start_time_msk == "08:00"  # default


class TestConfigParsing:
    def test_full_json(self, tmp_path):
        """Full JSON with all sections."""
        data = {
            "schedule": {"start_time_msk": "10:00", "interval_hours": 2, "window_days": 7},
            "telegram": {"token": "test_token", "chat_ids": [111, 222]},
            "kush": {"dry_run": False, "min_confidence": 0.90},
            "thresholds": {"roi": 0.03, "default_ratio": 1.15},
        }
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        cfg = load_config(str(p))
        assert cfg.schedule.start_time_msk == "10:00"
        assert cfg.schedule.interval_hours == 2
        assert cfg.telegram.token == "test_token"
        assert cfg.telegram.chat_ids == [111, 222]
        assert cfg.kush.dry_run is False
        assert cfg.kush.min_confidence == 0.90
        assert cfg.thresholds.roi == 0.03

    def test_unknown_keys_ignored(self, tmp_path):
        """Unknown keys in JSON don't cause errors."""
        data = {"schedule": {"interval_hours": 3, "unknown_key": "value"}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        cfg = load_config(str(p))
        assert cfg.schedule.interval_hours == 3


class TestConfigValidation:
    def test_invalid_start_time(self, tmp_path):
        data = {"schedule": {"start_time_msk": "8am"}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(str(p))
        assert "start_time_msk" in str(exc_info.value)

    def test_invalid_interval(self, tmp_path):
        data = {"schedule": {"interval_hours": 0}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(str(p))
        assert "interval_hours" in str(exc_info.value)

    def test_invalid_roi(self, tmp_path):
        data = {"thresholds": {"roi": 1.5}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(str(p))
        assert "roi" in str(exc_info.value)

    def test_invalid_ratio(self, tmp_path):
        data = {"thresholds": {"default_ratio": 0.5}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(str(p))
        assert "default_ratio" in str(exc_info.value)

    def test_multiple_errors(self, tmp_path):
        data = {
            "schedule": {"start_time_msk": "bad", "interval_hours": 0},
            "thresholds": {"roi": -1},
        }
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(str(p))
        assert len(exc_info.value.errors) >= 3


class TestEnvOverrides:
    def test_tg_token_override(self, tmp_path, monkeypatch):
        p = tmp_path / "config.json"
        p.write_text("{}")
        monkeypatch.setenv("NB_TG_TOKEN", "env_token_123")
        cfg = load_config(str(p))
        assert cfg.telegram.token == "env_token_123"

    def test_dry_run_override(self, tmp_path, monkeypatch):
        data = {"kush": {"dry_run": False}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        monkeypatch.setenv("NB_DRY_RUN", "1")
        cfg = load_config(str(p))
        assert cfg.kush.dry_run is True
