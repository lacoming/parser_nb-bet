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
| 01 | Скелет + config + logging | ⬜ TODO | — |
| 02 | NB-Bet парсер (JSON API) | ⬜ TODO | — |
| 03 | Фильтр лиг + DecisionEngine | ⬜ TODO | — |
| 04 | Matcher NB ↔ Kush | ⬜ TODO | — |
| 05 | Kush client (session, events, odds) | ⬜ TODO | — |
| 06 | Kush bet placer + dry-run | ⬜ TODO | — |
| 07 | Telegram уведомления | ⬜ TODO | — |
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
