# PROGRESS.md — parser_nb-bet

## Чеклист шагов

| # | Шаг | Статус | Дата |
|---|-----|--------|------|
| 00 | Создать/обновить CLAUDE.md | ✅ DONE | 2026-02-21 |
| 01 | Инициализация репо и каркас проекта | ✅ DONE | 2026-02-21 |
| 02 | Анализ существующих архивов (_legacy) | ⬜ TODO | — |
| 03 | Выбор финального стека и план сборки | ⬜ TODO | — |
| 04 | Конфигурация, логирование, хранение состояния | ⬜ TODO | — |
| 05 | Парсер nb-bet Results (MVP) | ⬜ TODO | — |
| 06 | Фильтр по лигам + бизнес-условия ставок | ⬜ TODO | — |
| 07 | Matcher NB ↔ Kush | ⬜ TODO | — |
| 08 | KushClient (поиск события) + очередь ожидания | ⬜ TODO | — |
| 09 | Автоставка на Куш + dry-run | ⬜ TODO | — |
| 10 | Telegram уведомления | ⬜ TODO | — |
| 11 | Excel вывод по шаблону | ⬜ TODO | — |
| 12 | Планировщик + режимы запуска | ⬜ TODO | — |
| 13 | UI окно + трей UX | ⬜ TODO | — |
| 14 | E2E прогон + упаковка в .exe | ⬜ TODO | — |

---

## Шаг 00 — DONE (2026-02-21)
**Задача:** Создать CLAUDE.md с инструкциями для Claude Code.

**Сделано:**
- CLAUDE.md создан с полным описанием цели, UX, правил, структуры папок, требования к Context7.
- PLAN.md создан с 15 промтами (шаги 00–14).

**Решения:**
- Секреты (TG токены, proxies) исключены из коммитов через .gitignore.

---

## Шаг 01 — DONE (2026-02-21)
**Задача:** Инициализация репо и каркас проекта.

**Сделано:**
- Инициализирован git-репозиторий.
- Созданы файлы: `README.md`, `ARCHITECTURE.md`, `PROGRESS.md`, `CONFIG.md`.
- Структура папок: `src/ParserNbBet/{Config,Logging,State,Nb,Kush,Decision,Excel,Telegram,Scheduler,Ui}`, `tests/ParserNbBet.Tests/`, `assets/customer/`, `scripts/`, `_legacy/`, `dist/`.
- `.gitignore` актуализирован.
- **Стек: C# 12 / .NET 8** (по требованию заказчика: нативный Windows, малый .exe, надёжность).
  - UI: WinForms + NotifyIcon (трей из коробки)
  - HTTP: HttpClient (stdlib)
  - HTML: HtmlAgilityPack
  - Excel: ClosedXML
  - State: Microsoft.Data.Sqlite
  - Scheduler: PeriodicTimer + TimeZoneInfo (stdlib)
  - Retry: Polly
  - Logging: Serilog
  - Build: `dotnet publish --self-contained -r win-x64 -p:PublishSingleFile=true`
- Созданы: `ParserNbBet.sln`, `ParserNbBet.csproj`, `Program.cs`, `CliArgs.cs`, `Ui/MainForm.cs`, `Ui/CloseDialog.cs`.

**Context7:** Недоступен в среде выполнения — стек выбран на основе официальной документации (зафиксировано).

**Примечание:** Стек предложен в шаге 01 и подтверждён пользователем. Финальная фиксация — шаг 03.

**Follow-ups:**
- Шаг 02: распаковать и проанализировать _legacy-архивы (nb3.zip, kushvsporte_autostavka.zip).
- Установить .NET 8 SDK для сборки.
- Шаг 03: финально зафиксировать стек после анализа legacy.
