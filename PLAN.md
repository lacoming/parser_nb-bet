# PLAN.md — parser_nb-bet (Python rewrite)

> **Правило:** 1 шаг = 1 промт для **Claude Opus 4.6**.
> Каждый шаг самодостаточный: цель → требования → критерии готовности → проверки.
> В конце каждого шага: обновить `PROGRESS.md`, показать проверки, сделать коммит.
>
> **ВАЖНО:** ты вставляешь шаги через `/clear`, поэтому каждый промт должен начинаться с чтения `CLAUDE.md`, `PLAN.md`, `PROGRESS.md`, `ARCHITECTURE.md`, `CONFIG.md`.

---

## Контекст

C# .NET 8 реализация завершена (165 тестов, 13 модулей), но exe = 167 МБ.
Условие заказа: **<10 МБ**, стек: **Python → PyInstaller**.
Legacy Python-код имеет рабочий `nbbet.exe` = 9.0 МБ. Решено откатиться на Python.

---

## Стек Python

| Компонент | Библиотека | Размер (в exe) |
|-----------|-----------|----------------|
| HTTP | requests | ~1 МБ |
| HTML | beautifulsoup4 + lxml | ~1.5 МБ |
| Fuzzy match | rapidfuzz | ~1 МБ |
| Excel read | openpyxl | ~0.4 МБ |
| Excel write | xlsxwriter | ~0.4 МБ |
| GUI | tkinter (stdlib) | ~0.5 МБ |
| Scheduler | threading + zoneinfo (stdlib) | 0 |
| Logging | logging + RotatingFileHandler (stdlib) | 0 |
| Telegram | requests (Bot API) | 0 (shared) |
| Python runtime | embedded (UPX compressed) | ~4 МБ |
| **Итого** | | **~8-9 МБ** |

Без SQLite, без pystray/Pillow, без APScheduler, без tenacity.

---

## STEP 00 — Git setup + переписать все docs

- Создать ветку `python-rewrite` от `72d032e`
- Переписать: CLAUDE.md, PLAN.md, PROGRESS.md, ARCHITECTURE.md, CONFIG.md
- Обновить: requirements.txt, .gitignore, config.example.json
- Сохранить: `_legacy/`, `assets/data/`
- Коммит: `docs: rewrite project docs for Python migration`

---

## STEP 01 — Скелет + config + logging

- `src/main.py` — argparse: `--once`, `--daemon`, `--dry-run`, `--test-telegram`
- `src/config/loader.py` — загрузка config.json, валидация, defaults, env overrides
- `src/config/schema.py` — dataclass-модели конфигурации
- `src/log_setup.py` — logging + RotatingFileHandler + console
- `src/state.py` — in-memory state (dict/set): pending, placed, known_keys
- Тесты: test_config.py (8-10 тестов)
- Коммит: `feat: project skeleton, config, logging (step 01)`

---

## STEP 02 — NB-Bet парсер (JSON API)

- `src/nb/client.py` — NbClient: get_matches(), parse JSON, retry, proxy
- `src/nb/models.py` — Match dataclass
- `src/nb/odds_decoder.py` — декодер ключей из sl_keys.json
- Тесты: test_nb_client.py (12-15 тестов)
- Коммит: `feat: NB-Bet JSON API parser (step 02)`

---

## STEP 03 — Фильтр лиг + DecisionEngine

- `src/decision/league_loader.py` — чтение leagues.xlsx (openpyxl)
- `src/decision/league_filter.py` — фильтр + sl_chemps_zamen.json
- `src/decision/engine.py` — правила ставок из ТЗ
- Тесты: test_decision.py (17+), test_league_filter.py (6+)
- Коммит: `feat: league filter + decision engine (step 03)`

---

## STEP 04 — Matcher NB ↔ Kush

- `src/kush/normalizer.py` — нормализация команд (transliterate, lowercase, punctuation)
- `src/kush/matcher.py` — EventMatcher: rapidfuzz WRatio, time tolerance, confidence
- `src/kush/models.py` — KushEvent, MatchResult dataclasses
- Тесты: test_normalizer.py (10), test_matcher.py (17)
- Коммит: `feat: NB-Kush event matcher (step 04)`

---

## STEP 05 — Kush client (session, leagues, events, odds)

- `src/kush/session.py` — requests.Session + CSRF + cookies + login
- `src/kush/client.py` — KushClient: get_all_events, get_odds, find_event, parse HTML
- Тесты: test_kush_client.py (22 теста — parsing)
- Коммит: `feat: Kush client with session and event search (step 05)`

---

## STEP 06 — Kush bet placer + dry-run

- `src/kush/bet_placer.py` — ratio check, bet type mapping, add_coupon, create_coupon
- `src/kush/bet_result.py` — BetResult dataclass
- Интеграция в main.py: matched → place per passing bet
- Тесты: test_bet_placer.py (22 теста)
- Коммит: `feat: Kush bet placer with dry-run (step 06)`

---

## STEP 07 — Telegram уведомления

- `src/telegram/notifier.py` — notify_placed, notify_missing, notify_critical, send_test, send_document
- MarkdownV2 + fallback, rate-limit, multiple chat_ids
- `--test-telegram` флаг
- Тесты: test_telegram.py (16 тестов)
- Коммит: `feat: Telegram notifications (step 07)`

---

## STEP 08 — Excel writer

- `src/excel/writer.py` — xlsxwriter, буфер строк, save по дате
- `src/excel/default_mapper.py` — 24 колонки
- `src/excel/models.py` — ExcelRow dataclass
- Тесты: test_excel.py (13 тестов)
- Коммит: `feat: Excel writer with xlsxwriter (step 08)`

---

## STEP 09 — Scheduler + режимы запуска

- `src/scheduler/msk_scheduler.py` — compute_next_run, run_once, run_daemon
- `src/scheduler/cycle_runner.py` — полный цикл: NB → filter → decide → Kush → bet → excel → telegram
- zoneinfo("Europe/Moscow"), threading.Event для shutdown
- Тесты: test_scheduler.py (13 тестов)
- Коммит: `feat: MSK scheduler with once/daemon modes (step 09)`

---

## STEP 10 — Tkinter UI

- `src/ui/main_window.py` — Tkinter: status panel, log viewer, buttons
- Кнопки: "Запустить", "Пауза", "Скрыть", "Выход"
- X → messagebox "Выйти или свернуть?"
- Thread-safe log через root.after()
- Коммит: `feat: Tkinter UI window (step 10)`

---

## STEP 11 — E2E + PyInstaller packaging

- PyInstaller spec: `--onefile --name parser_nb-bet --add-data assets/data`
- UPX compression
- Exclude неиспользуемых модулей
- Замер размера (цель: <10 МБ)
- E2E: `--once --dry-run`, `--daemon --dry-run`, `--test-telegram`, UI mode
- README.md + runbook для заказчика
- Коммит: `feat: E2E + PyInstaller packaging (step 11)`

---

## Верификация

- Каждый шаг: `python -m pytest tests/ -v`
- Финал: `dist/parser_nb-bet.exe --once --dry-run` работает
- Размер: `(Get-Item dist/parser_nb-bet.exe).Length / 1MB` < 10
