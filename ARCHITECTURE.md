# ARCHITECTURE.md — parser_nb-bet (Python)

## Выбранный стек

> Стек: Python 3.11+ / PyInstaller. Цель: exe < 10 МБ.
> Миграция с C# .NET 8 (exe = 167 МБ → не проходит ограничение <10 МБ).

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| Язык | **Python 3.11+** | Лёгкий exe через PyInstaller, быстрая разработка |
| HTTP | **requests** | Session-based, proxy, retry, широко используется |
| Парсинг HTML | **beautifulsoup4 + lxml** | Стандарт для Python, быстрый |
| Fuzzy matching | **rapidfuzz** | WRatio — аналог legacy Python кода |
| Excel read | **openpyxl** | Чтение leagues.xlsx |
| Excel write | **xlsxwriter** | Лёгкий, только запись |
| GUI | **tkinter** (stdlib) | Встроен в Python, нет доп. зависимостей |
| Telegram | **requests** (Bot API) | Прямые HTTP-вызовы, без SDK |
| Состояние | **In-memory** (dict/set) | Нет SQLite, минимальный footprint |
| Планировщик | **threading + zoneinfo** (stdlib) | MSK = Europe/Moscow |
| Логирование | **logging + RotatingFileHandler** (stdlib) | Встроено |
| Retry | **Manual** (loop + time.sleep) | Без tenacity |
| Packaging | **PyInstaller + UPX** | --onefile, exe < 10 МБ |

---

## Структура проекта

```
parser_nb-bet/
├── src/
│   ├── main.py              # Entry point (argparse)
│   ├── __init__.py
│   ├── config/
│   │   ├── loader.py        # JSON config loader + validation
│   │   └── schema.py        # Dataclass config models
│   ├── log_setup.py         # logging + RotatingFileHandler
│   ├── state.py             # In-memory state (dicts/sets)
│   ├── nb/
│   │   ├── client.py        # NB-Bet JSON API parser
│   │   ├── models.py        # Match dataclass
│   │   └── odds_decoder.py  # sl_keys.json decoder
│   ├── kush/
│   │   ├── session.py       # requests.Session + CSRF
│   │   ├── client.py        # KushClient (events, odds)
│   │   ├── matcher.py       # EventMatcher (rapidfuzz)
│   │   ├── normalizer.py    # Team name normalization
│   │   ├── bet_placer.py    # Ratio check + bet placement
│   │   ├── bet_result.py    # BetResult dataclass
│   │   └── models.py        # KushEvent, MatchResult
│   ├── decision/
│   │   ├── engine.py        # Decision rules from spec
│   │   ├── league_loader.py # openpyxl leagues.xlsx
│   │   ├── league_filter.py # Filter + sl_chemps_zamen
│   │   └── models.py        # LeagueSetting, BetDecision
│   ├── telegram/
│   │   └── notifier.py      # Bot API notifications
│   ├── excel/
│   │   ├── writer.py        # xlsxwriter output
│   │   ├── default_mapper.py
│   │   └── models.py        # ExcelRow
│   ├── scheduler/
│   │   ├── msk_scheduler.py # MSK timezone scheduler
│   │   └── cycle_runner.py  # Full cycle orchestration
│   └── ui/
│       └── main_window.py   # Tkinter window
├── tests/                   # pytest tests
├── assets/data/             # sl_keys.json, sl_chemps_zamen.json, sl_stavok.json
├── scripts/build.ps1        # PyInstaller build
├── config.example.json
├── requirements.txt
└── dist/                    # PyInstaller output
```

---

## Компоненты системы

### NbClient (`nb/`)
- **Назначение:** Получить список текущих матчей с `nb-bet.com` (JSON API).
- **API:** `GET https://app.nb-bet.com/v1/{soccer|hockey}/math-analysis/page?timestamp={unix_ms}`
- **Выход:** `list[Match]`
- **Headers:** Origin=nb-bet.com, Referer=nb-bet.com/
- **JSON:** response.data.leagues[].4[] = matches

### LeagueFilter (`decision/`)
- **Назначение:** Фильтрация по лигам из `leagues.xlsx`.
- **Маппинг:** sl_chemps_zamen.json (NB → Kush нормализация имён лиг).

### DecisionEngine (`decision/`)
- **Назначение:** Правила ставок по ТЗ.
- **Правила:**
  - kf1 > kf2: 1X(kf1≤8, kf1X≥1.5, kf2≥1.4), 1(kf1≤8, kf2≥1.4), 2(kf2≥1.5), X(same as 1X)
  - kf2 > kf1: 2(kf2≤8, kf1≥1.4), 1(kf1≥1.5)
  - kf1 == kf2: skip

### EventMatcher (`kush/matcher.py`)
- **Алгоритм:**
  1. Нормализация: lower → transliterate ru→en → remove punctuation → collapse whitespace
  2. Fuzzy: rapidfuzz `WRatio` на нормализованных строках, проверяет оба порядка команд
  3. TimeScore: линейный decay от 1.0 до 0.0 на границе tolerance
  4. Confidence = nameScore * 0.70 + timeScore * 0.30
  5. Порог: ≥ 0.80 → принят

### KushClient (`kush/`)
- **Session:** requests.Session + CSRF из `<meta name="csrf-token">` + cookies
- **Login:** POST /users/login (form + _csrf)
- **Events:** POST /bet/event-list по CID лиги
- **Odds:** POST /bet/cf-list по event ID
- **Rate-limiting:** 1.8 сек между запросами

### KushBetPlacer (`kush/bet_placer.py`)
- **Формула:** `KfKush * (1 + ROI) / KfNB > threshold`
  - threshold: 1.10 (обычные), 1.05 (big leagues)
- **Bet flow:** get odds → find entry → check ratio → dry-run/real
- **Real:** login → add_coupon → create_coupon

### TelegramNotifier (`telegram/`)
- **Events:** placed, missing, critical, cycle_summary, test
- **MarkdownV2 + fallback** to plain text
- **Rate-limit:** configurable delay between messages

### ExcelWriter (`excel/`)
- **xlsxwriter:** 24 колонки, файл по дате
- **Mapping pattern** для подмены колонок

### MskScheduler (`scheduler/`)
- **Режимы:** --once, --daemon
- **MSK:** zoneinfo("Europe/Moscow")
- **Slots:** start_time + interval, graceful shutdown via threading.Event

### UI (`ui/main_window.py`)
- **Tkinter:** status panel, log viewer (Text widget), buttons
- **UX:** Start visible, X → "Выйти/Свернуть?" dialog
- **Thread-safe:** root.after() for log updates

---

## Модели данных

```python
@dataclass
class Match:
    match_key: str      # "{league}|{home}|{away}|{date:%Y%m%d}"
    league: str
    team_home: str
    team_away: str
    start_time_utc: datetime
    nb_slug: str
    sport: str
    odds_1_start: float | None
    odds_x_start: float | None
    odds_2_start: float | None
    odds_1_end: float | None
    odds_x_end: float | None
    odds_2_end: float | None

    @property
    def odds_1x_end(self) -> float | None:
        if self.odds_1_end and self.odds_x_end:
            return min(self.odds_1_end, self.odds_x_end)
        return None

@dataclass
class BetDecision:
    bet_type: str       # "1X" | "1" | "2" | "X" | "skip"
    passes: bool
    reasons: list[str]

@dataclass
class KushEvent:
    event_id: str
    league: str
    team_home: str
    team_away: str
    start_time_utc: datetime
    odds: dict[str, float]
    url: str
```

---

## Поток данных (один цикл)

```
NbClient.get_matches()
    → LeagueFilter.filter()
        → DecisionEngine.decide()
            → foreach passing match:
                → KushClient.find_event()
                    → found  → BetPlacer.place() (если ratio OK)
                              → TelegramNotifier.notify_placed()
                              → ExcelWriter.add_row()
                    → None   → State.enqueue_pending()
                              → TelegramNotifier.notify_missing()
    → ExcelWriter.save()
    → Scheduler.schedule_next()
```

---

## NB-Bet API (из legacy)

- Endpoint: `GET https://app.nb-bet.com/v1/{soccer|hockey}/math-analysis/page?timestamp={unix_ms}`
- No auth required, JSON response
- Headers: Origin=nb-bet.com, Referer=nb-bet.com/
- JSON structure: response.data.leagues[].4[] = matches
- Match fields: '3'=slug, '4'=timestamp(ms), '5'=end_odds, '6'=start_odds, '7'=home, '15'=away

## Kushvsporte.ru flow (из legacy)

- CSRF chain: GET page → extract meta csrf-token + PHPSESSID + _csrf cookies
- Leagues: GET /centerbet/football?day={0|1}
- Matches: POST /bet/event-list {cid, day}
- Odds: POST /bet/cf-list {eid}
- Auth: POST /users/login (login-form[login], login-form[password], _csrf)
- Bet: GET /coupon/add-coupon?eid=&cfid= → POST /coupon/create-coupon (tokens + bet_amount)

## Data assets (в assets/data/)

- sl_keys.json — odds key ID → string key mapping (1000+ entries)
- sl_chemps_zamen.json — NB league name → Kush league name mapping (248+ entries)
- sl_stavok.json — NB bet type → [Kush direct, Kush inverse] mapping
