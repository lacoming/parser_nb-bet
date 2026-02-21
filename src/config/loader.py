"""Config loader: JSON file + env overrides + validation."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from src.config.schema import (
    AppConfig,
    FilesConfig,
    KushConfig,
    LoggingConfig,
    NbConfig,
    ProxiesConfig,
    ScheduleConfig,
    TelegramConfig,
    ThresholdsConfig,
    UiConfig,
)


class ConfigValidationError(Exception):
    """Raised when config validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


def load_config(path: str = "config.json") -> AppConfig:
    """Load config from JSON file, apply env overrides, validate."""
    config_path = os.environ.get("NB_CONFIG_PATH", path)
    p = Path(config_path)

    if p.exists():
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = {}

    cfg = _parse_raw(raw)
    _apply_env_overrides(cfg)
    _validate(cfg)
    return cfg


def _parse_raw(raw: dict[str, Any]) -> AppConfig:
    """Parse raw JSON dict into AppConfig."""
    return AppConfig(
        schedule=_make(ScheduleConfig, raw.get("schedule", {})),
        telegram=_make(TelegramConfig, raw.get("telegram", {})),
        proxies=_make(ProxiesConfig, raw.get("proxies", {})),
        thresholds=_make(ThresholdsConfig, raw.get("thresholds", {})),
        files=_make(FilesConfig, raw.get("files", {})),
        ui=_make(UiConfig, raw.get("ui", {})),
        kush=_make(KushConfig, raw.get("kush", {})),
        nb=_make(NbConfig, raw.get("nb", {})),
        logging=_make(LoggingConfig, raw.get("logging", {})),
    )


def _make(cls, data: dict[str, Any]):
    """Create dataclass instance from dict, ignoring unknown keys."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in field_names}
    return cls(**filtered)


def _apply_env_overrides(cfg: AppConfig) -> None:
    """Apply environment variable overrides."""
    tg_token = os.environ.get("NB_TG_TOKEN")
    if tg_token:
        cfg.telegram.token = tg_token

    dry_run = os.environ.get("NB_DRY_RUN")
    if dry_run in ("1", "true", "True"):
        cfg.kush.dry_run = True


def _validate(cfg: AppConfig) -> None:
    """Validate config, raise ConfigValidationError if issues found."""
    errors: list[str] = []

    # Schedule validation
    if not re.match(r"^\d{2}:\d{2}$", cfg.schedule.start_time_msk):
        errors.append(f"schedule.start_time_msk must be HH:MM, got '{cfg.schedule.start_time_msk}'")
    if cfg.schedule.interval_hours < 1 or cfg.schedule.interval_hours > 24:
        errors.append(f"schedule.interval_hours must be 1-24, got {cfg.schedule.interval_hours}")

    # Thresholds validation
    if cfg.thresholds.roi < 0 or cfg.thresholds.roi > 1:
        errors.append(f"thresholds.roi must be 0-1, got {cfg.thresholds.roi}")
    if cfg.thresholds.default_ratio < 1:
        errors.append(f"thresholds.default_ratio must be >= 1, got {cfg.thresholds.default_ratio}")
    if cfg.thresholds.big_league_ratio < 1:
        errors.append(f"thresholds.big_league_ratio must be >= 1, got {cfg.thresholds.big_league_ratio}")

    # Kush validation
    if cfg.kush.min_confidence < 0 or cfg.kush.min_confidence > 1:
        errors.append(f"kush.min_confidence must be 0-1, got {cfg.kush.min_confidence}")

    if errors:
        raise ConfigValidationError(errors)


def load_proxies(path: str = "proxies.txt") -> list[str]:
    """Load proxy list from file. Returns empty list if file missing."""
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
