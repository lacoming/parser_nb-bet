"""Configuration dataclass models for parser_nb-bet."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScheduleConfig:
    start_time_msk: str = "08:00"
    interval_hours: int = 4
    window_days: int = 14
    enabled: bool = True


@dataclass
class TelegramConfig:
    token: str = ""
    chat_ids: list[int] = field(default_factory=list)
    dev_chat_id: int = 0
    rate_limit_seconds: float = 1.0


@dataclass
class VkConfig:
    token: str = ""
    peer_id: int = 0
    rate_limit_seconds: float = 1.0


@dataclass
class ProxiesConfig:
    enabled: bool = False
    file: str = "proxies.txt"
    rotate: bool = True


@dataclass
class ThresholdsConfig:
    roi: float = 0.05
    default_ratio: float = 1.10
    big_league_ratio: float = 1.05
    big_leagues: list[str] = field(default_factory=list)


@dataclass
class FilesConfig:
    leagues_xlsx_path: str = "leagues.xlsx"
    output_dir: str = "output"
    logs_dir: str = "logs"


@dataclass
class UiConfig:
    tray_enabled: bool = True
    icon_path: str = "assets/icon.ico"


@dataclass
class KushConfig:
    base_url: str = "https://kushvsporte.ru/"
    login: str = ""
    password: str = ""
    dry_run: bool = True
    default_stake: int = 100
    match_time_tolerance_hours: int = 5
    min_confidence: float = 0.80


@dataclass
class NbConfig:
    base_url: str = "https://nb-bet.com/Results"
    timeout_seconds: int = 30
    retries: int = 3
    retry_delay_seconds: int = 5
    login: str = ""
    password: str = ""
    dry_run: bool = True
    default_stake: int = 1000


@dataclass
class LoggingConfig:
    level: str = "INFO"
    max_bytes: int = 10_485_760
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass
class AppConfig:
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    vk: VkConfig = field(default_factory=VkConfig)
    proxies: ProxiesConfig = field(default_factory=ProxiesConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    kush: KushConfig = field(default_factory=KushConfig)
    nb: NbConfig = field(default_factory=NbConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
