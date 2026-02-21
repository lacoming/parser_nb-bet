# CONFIG.md — Конфигурация parser_nb-bet

## Файлы конфигурации

| Файл | Место | В git? | Описание |
|------|-------|--------|----------|
| `config.json` | корень проекта / рядом с .exe | ❌ НЕТ | Основная конфигурация |
| `leagues.xlsx` | рядом с .exe | ❌ НЕТ | Список разрешённых лиг |
| `proxies.txt` | рядом с .exe | ❌ НЕТ | Прокси (опционально) |
| `config.example.json` | корень | ✅ ДА | Шаблон без секретов |

---

## Схема config.json

```json
{
  "schedule": {
    "start_time_msk": "08:00",
    "interval_hours": 4,
    "window_days": 14,
    "enabled": true
  },
  "telegram": {
    "token": "BOT_TOKEN_HERE",
    "chat_ids": [123456789],
    "dev_chat_id": 123456789,
    "rate_limit_seconds": 1.0
  },
  "proxies": {
    "enabled": false,
    "file": "proxies.txt",
    "rotate": true
  },
  "thresholds": {
    "roi": 0.05,
    "default_ratio": 1.10,
    "big_league_ratio": 1.05,
    "big_leagues": []
  },
  "files": {
    "leagues_xlsx_path": "leagues.xlsx",
    "output_dir": "output",
    "logs_dir": "logs"
  },
  "ui": {
    "tray_enabled": true,
    "icon_path": "assets/icon.ico"
  },
  "kush": {
    "base_url": "https://kushvsporte.ru/",
    "login": "",
    "password": "",
    "dry_run": true,
    "default_stake": 100,
    "match_time_tolerance_hours": 2,
    "min_confidence": 0.80
  },
  "nb": {
    "base_url": "https://nb-bet.com/Results",
    "timeout_seconds": 30,
    "retries": 3,
    "retry_delay_seconds": 5
  },
  "logging": {
    "level": "INFO",
    "max_bytes": 10485760,
    "backup_count": 5,
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  }
}
```

---

## Расположение файлов при запуске .exe

```
<install_dir>/
├── parser_nb-bet.exe     # Исполняемый файл (< 10 МБ)
├── config.json           # Конфигурация (создать из config.example.json)
├── leagues.xlsx          # Список лиг
├── proxies.txt           # Прокси (опционально)
├── logs/                 # Логи (создаётся автоматически)
│   └── parser.log
└── output/               # Результаты Excel (создаётся автоматически)
    └── 2026-02-21_results.xlsx
```

---

## Переменные окружения (альтернатива)

Можно переопределить через env-переменные (приоритет выше config.json):

| Переменная | Описание |
|-----------|----------|
| `NB_TG_TOKEN` | Telegram bot token |
| `NB_CONFIG_PATH` | Путь к config.json |
| `NB_DRY_RUN` | `1` — включить dry-run |

---

## proxies.txt формат

```
http://user:pass@host:port
http://host:port
socks5://user:pass@host:port
```

Один прокси на строку. Пустые строки и строки с `#` — игнорируются.

---

## leagues.xlsx формат

Ожидается лист с колонками:
- A: Спорт (football/hockey)
- B: Лига (название)
- C: МинКф (минимальный коэффициент)
- D: МаксКф (максимальный коэффициент)
- E: Ставка_НБ (тип ставки)
- F: Ставка_Куш (тип ставки на Куше)
