# PROGRESS.md — parser_nb-bet

## Чеклист шагов

| # | Шаг | Статус | Дата |
|---|-----|--------|------|
| 00 | Создать/обновить CLAUDE.md | ✅ DONE | 2026-02-21 |
| 01 | Инициализация репо и каркас проекта | ✅ DONE | 2026-02-21 |
| 02 | Анализ существующих архивов (_legacy) | ✅ DONE | 2026-02-21 |
| 03 | Выбор финального стека и план сборки | ✅ DONE | 2026-02-21 |
| 04 | Конфигурация, логирование, хранение состояния | ✅ DONE | 2026-02-21 |
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

---

## Шаг 02 — DONE (2026-02-21)
**Задача:** Распаковать legacy-архивы и составить EXISTING_CODE_REVIEW.md.

**Сделано:**
- Распакованы `nb3.zip` и `kushvsporte_autostavka.zip` в `_legacy/`
- Извлечён текст из `ТЗ 2 бота - 1ХХХ.docx`
- Создан `EXISTING_CODE_REVIEW.md` с полным анализом:
  - NB-Bet API: JSON API на `app.nb-bet.com/v1/{sport}/math-analysis/page?timestamp=` (без авторизации)
  - Kush: HTML-парсинг через BeautifulSoup, CSRF-цепочка, авторизация через сессию
  - Матчинг: RapidFuzz (WRatio), порог 87%, словарь замен лиг (248+ записей)
  - Telegram: Bot API sendDocument, множество чатов
  - Decision engine: условия из ТЗ (кф1>кф2 / кф2>кф1), формула ratio
- Скопированы data-файлы в `assets/customer/`: sl_keys.json, sl_chemps_zamen.json, sl_stavok.json

**Ключевые находки:**
1. NB-Bet — чистый JSON API (не HTML), парсинг очень простой
2. Kushvsporte — HTML + CSRF, авторизация обязательна для ставок
3. Формула порога: `КфКуш*(1+ROI)/КфНБ > 1.10` (обычные) / `> 1.05` (биг-лиги)
4. Ставка: сразу (кэф падает) или за час до матча (кэф растёт)
5. Словарь замен лиг — критически важен для матчинга

**Решения:**
- Legacy-исходники НЕ коммитим (чужой код, credentials внутри)
- Data-файлы (json) скопированы в assets/ и будут закоммичены
- Для fuzzy match в C#: FuzzySharp (NuGet)

**Follow-ups:**
- Шаг 03: зафиксировать стек (добавить FuzzySharp в зависимости)
- Шаг 05: использовать API endpoint из legacy для NB-парсера
- Шаг 08-09: воспроизвести CSRF-цепочку Kush на C#

---

## Шаг 03 — DONE (2026-02-21)
**Задача:** Финальная фиксация стека и стратегия релиза.

**Сделано:**
- ARCHITECTURE.md обновлён: финальная таблица стека, добавлен FuzzySharp, убран PuppeteerSharp (резерв)
- Добавлена секция «Стратегия сборки и публикации»: self-contained vs framework-dependent, trimming (отключён), R2R, полная таблица NuGet-зависимостей
- CONFIG.md: формат logging исправлен с Python-стиля на Serilog (outputTemplate, level=Information)
- build.ps1 финализирован: добавлены флаги `-FrameworkDependent`, `-Trim`, preflight-проверка dotnet SDK, размер .exe в выводе
- .editorconfig создан: C# formatting, naming conventions (_camelCase для приватных полей, PascalCase для публичных)
- nuget.config создан (nuget.org — отсутствовал, restore не работал)
- csproj: добавлен FuzzySharp, убраны publish-специфичные свойства из csproj (RuntimeIdentifier, SelfContained) — теперь только через CLI в build.ps1, иконка закомментирована (до шага 13)

**Проверки:**
- `dotnet restore` ✅
- `dotnet build --configuration Release` ✅ (0 ошибок, 0 предупреждений)
- `dotnet test` ✅ (тестов пока нет — добавятся в шаге 04)
- Trial publish — пропущен (долгое скачивание runtime; перенесён на шаг 14)

**Follow-ups:**
- Шаг 04: config loader, Serilog, SQLite state
- Шаг 13: добавить icon.ico
- Шаг 14: полный publish + замер размера .exe

---

## Шаг 04 — DONE (2026-02-21)
**Задача:** Конфигурация, логирование, хранение состояния.

**Сделано:**
- `config.example.json` обновлён: Serilog-формат, все ключи из CONFIG.md, без секретов
- `Config/AppConfig.cs` — strongly-typed модель конфигурации (9 секций: schedule, telegram, proxies, thresholds, files, ui, kush, nb, logging)
- `Config/ConfigLoader.cs` — загрузка JSON, env overrides (NB_TG_TOKEN, NB_DRY_RUN), валидация с множественными ошибками, `ConfigValidationException`
- `Logging/LoggingSetup.cs` — Serilog: file sink (ротация по размеру, retained count) + console sink, настраиваемый уровень и шаблон
- `State/StateStore.cs` — SQLite: таблицы `pending_matches` + `placed_bets`, деdup по match_key (INSERT OR IGNORE), CRUD: Enqueue, GetDuePending, UpdateNextCheck, RemovePending, RecordBet, IsKnown, PendingCount
- `Program.cs` — подключен config + logging + state при запуске, "boot ok" в лог
- 8 тестов ConfigTests: defaults, JSON parse, validation (interval, roi, ratio, start_time, multiple errors, pass)
- 7 тестов StateStoreTests: init, enqueue, dedup, IsKnown, remove, due pending, record bet

**Проверки:**
- `dotnet build --configuration Release` ✅ (0 ошибок, 0 предупреждений)
- `dotnet test` ✅ (15/15 passed)

**Follow-ups:**
- Шаг 05: NB-Bet парсер (использовать JSON API из legacy)
- Шаг 06: leagues + DecisionEngine
