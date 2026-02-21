# PROGRESS.md — parser_nb-bet (Python rewrite)

## Контекст миграции

C# .NET 8 реализация завершена (165 тестов, 13 модулей), но exe = 167 МБ.
Условие заказа: **<10 МБ**. Решено переписать на Python → PyInstaller.
C# код остаётся в ветке `main`/`master` как бэкап.

---

## Чеклист шагов

| # | Шаг | Статус | Дата |
|---|-----|--------|------|
| 00 | Git setup + переписать docs | ✅ DONE | 2026-02-21 |
| 01 | Скелет + config + logging | ✅ DONE | 2026-02-21 |
| 02 | NB-Bet парсер (JSON API) | ✅ DONE | 2026-02-21 |
| 03 | Фильтр лиг + DecisionEngine | ✅ DONE | 2026-02-21 |
| 04 | Matcher NB ↔ Kush | ✅ DONE | 2026-02-21 |
| 05 | Kush client (session, events, odds) | ✅ DONE | 2026-02-21 |
| 06 | Kush bet placer + dry-run | ✅ DONE | 2026-02-21 |
| 07 | Telegram уведомления | ✅ DONE | 2026-02-21 |
| 08 | Excel writer | ⬜ TODO | — |
| 09 | Scheduler + режимы запуска | ⬜ TODO | — |
| 10 | Tkinter UI | ⬜ TODO | — |
| 11 | E2E + PyInstaller packaging | ⬜ TODO | — |

---

## Шаг 00 — DONE (2026-02-21)
**Задача:** Git setup + переписать все docs для Python миграции.

**Сделано:**
- Создана ветка `python-rewrite` от коммита `72d032e` (первый коммит, до C#)
- Переписаны: CLAUDE.md, PLAN.md, PROGRESS.md, ARCHITECTURE.md, CONFIG.md, README.md
- Обновлены: requirements.txt (Python deps), .gitignore (Python + PyInstaller)
- Скопированы data assets из master: sl_keys.json, sl_chemps_zamen.json, sl_stavok.json
- Сохранён существующий Python skeleton (src/main.py, __init__.py файлы)
- config.example.json обновлён (Python logging format)
- scripts/build.ps1 переписан для PyInstaller

**Решения:**
- Без SQLite (in-memory state)
- Без pystray/Pillow (tkinter only, tray опционально)
- Без APScheduler (threading + zoneinfo)
- Без tenacity (manual retry)
- rapidfuzz вместо FuzzySharp

**Follow-ups:**
- Step 01: config loader, logging setup, state module

## Шаг 01 — DONE (2026-02-21)
**Задача:** Скелет проекта: argparse, config, logging, state.

**Сделано:**
- `src/main.py` — argparse: --once, --daemon, --dry-run, --test-telegram, --config
- `src/config/schema.py` — 9 dataclass-моделей конфигурации с defaults
- `src/config/loader.py` — JSON loader + env overrides (NB_TG_TOKEN, NB_DRY_RUN) + validation
- `src/log_setup.py` — RotatingFileHandler + console + optional UI handler
- `src/state.py` — AppState: pending queue, placed set, known set, recheck logic
- `tests/test_config.py` — 12 тестов
- `tests/test_state.py` — 11 тестов
- Smoke run: `python -m src.main --once --dry-run` — OK
- Коммит: `4e93a72`

**Follow-ups:**
- Step 02: NB-Bet JSON API parser

## Шаг 02 — DONE (2026-02-21)
**Задача:** NB-Bet JSON API парсер.

**Сделано:**
- `src/nb/models.py` — Match dataclass (match_key, odds, odds_1x_end property)
- `src/nb/client.py` — NbClient: get_matches(), retry с backoff, proxy rotation
- `src/nb/odds_decoder.py` — sl_keys.json loader + decode (портировано из legacy)
- `tests/test_nb_client.py` — 33 теста (model, parse, util, decoder, client mock)
- Коммит: `849fddd`

**Follow-ups:**
- Step 03: League filter + DecisionEngine

## Шаг 03 — DONE (2026-02-21)
**Задача:** Фильтр лиг + DecisionEngine.

**Сделано:**
- `src/decision/models.py` — LeagueSetting, BetDecision dataclasses
- `src/decision/league_loader.py` — openpyxl чтение leagues.xlsx
- `src/decision/league_filter.py` — LeagueFilter + sl_chemps_zamen.json маппинг
- `src/decision/engine.py` — DecisionEngine: правила ставок из ТЗ
- `tests/test_decision.py` — 31 тест
- Коммит: `feaab08`

## Шаг 04 — DONE (2026-02-21)
**Задача:** Matcher NB ↔ Kush.

**Сделано:**
- `src/kush/models.py` — KushEvent, MatchResult dataclasses
- `src/kush/normalizer.py` — нормализация: lower → transliterate ru→en → remove punct → FC/FK
- `src/kush/matcher.py` — EventMatcher: rapidfuzz WRatio, time tolerance, confidence
- `tests/test_normalizer.py` — 15 тестов
- `tests/test_matcher.py` — 16 тестов
- Коммит: `aa7b53a`

## Шаг 05 — DONE (2026-02-21)
**Задача:** Kush client (session, leagues, events, odds).

**Сделано:**
- `src/kush/session.py` — KushSession: requests.Session + CSRF chain + login + rate-limiting + retry
- `src/kush/client.py` — KushClient: get_leagues, get_events, get_all_events, get_odds, find_odds_entry
- `tests/test_kush_client.py` — 33 теста (HTML parsing, session mock, client integration)
- Все 151 тестов проходят

**Follow-ups:**
- Step 06: Kush bet placer + dry-run

## Шаг 06 — DONE (2026-02-21)
**Задача:** Kush bet placer + dry-run.

**Сделано:**
- `src/kush/bet_result.py` — BetResult dataclass (match_key, kf_nb/kf_kush, ratio, threshold, placed, dry_run, success, summary)
- `src/kush/bet_placer.py` — BetPlacer: compute_ratio, check_ratio, get_threshold (big/default leagues), place_bet (dry-run + real), _add_coupon (GET form tokens), _create_coupon (POST with stake)
- `tests/test_bet_placer.py` — 29 тестов (ratio calc, threshold, dry-run, real placement, login failure, error extraction, edge cases)
- Портирован flow из legacy: get_all_variants_po_stavkam → add_coupon → create_coupon
- Формула ratio: `kf_kush * (1 + ROI) / kf_nb > threshold`
- Все 180 тестов проходят

**Follow-ups:**
- Step 07: Telegram уведомления

## Шаг 07 — DONE (2026-02-21)
**Задача:** Telegram уведомления.

**Сделано:**
- `src/telegram/notifier.py` — TelegramNotifier: sendMessage, sendDocument, MarkdownV2 + fallback
- Методы: notify_placed, notify_missing, notify_critical, notify_cycle_summary, send_test, send_document
- escape_md2 для безопасного экранирования спецсимволов MarkdownV2
- Rate-limit между сообщениями (configurable)
- Broadcast на все chat_ids с retry (MD2 → plain text fallback)
- `--test-telegram` интегрирован в main.py
- `tests/test_telegram.py` — 26 тестов
- Все 206 тестов проходят

**Follow-ups:**
- Step 08: Excel writer
