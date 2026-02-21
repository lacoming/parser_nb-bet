# PROGRESS.md — parser_nb-bet

## Чеклист шагов

| # | Шаг | Статус | Дата |
|---|-----|--------|------|
| 00 | Создать/обновить CLAUDE.md | ✅ DONE | 2026-02-21 |
| 01 | Инициализация репо и каркас проекта | ✅ DONE | 2026-02-21 |
| 02 | Анализ существующих архивов (_legacy) | ✅ DONE | 2026-02-21 |
| 03 | Выбор финального стека и план сборки | ✅ DONE | 2026-02-21 |
| 04 | Конфигурация, логирование, хранение состояния | ✅ DONE | 2026-02-21 |
| 05 | Парсер nb-bet Results (MVP) | ✅ DONE | 2026-02-21 |
| 06 | Фильтр по лигам + бизнес-условия ставок | ✅ DONE | 2026-02-21 |
| 07 | Matcher NB ↔ Kush | ✅ DONE | 2026-02-21 |
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

---

## Шаг 05 — DONE (2026-02-21)
**Задача:** Парсер nb-bet Results (MVP).

**Сделано:**
- `Nb/Match.cs` — модель матча: League, TeamHome, TeamAway, StartTimeUtc, NbSlug, Sport, Odds1/X/2 (Start+End), Odds1XEnd (derived), MatchKey для дедупа
- `Nb/NbClient.cs` — HTTP-клиент к NB-Bet JSON API:
  - URL: `app.nb-bet.com/v1/{soccer|hockey}/math-analysis/page?timestamp={unix_ms}`
  - Обязательные headers (Origin, Referer, User-Agent) из legacy
  - Proxy support через HttpClientHandler.Proxy (из ProxyConfig)
  - Retry/backoff через Polly ResiliencePipeline (конфигурируемое количество/задержка)
  - `GetMatchesAsync(windowDays)` — итерация по дням, агрегация матчей
  - `ParseResponse(json)` — static, парсинг JSON → List<Match>, public для тестирования
  - Обработка: null odds, string/number timestamp, пустые команды (skip)
- `Program.cs` — RunHeadless подключён: NbClient → лог кол-ва матчей + 3 примера
- 14 тестов NbClientTests: count, league, teams, timestamp, start/end odds, null odds, match_key, Odds1XEnd, sport, empty JSON, no leagues, skip без команд, string odds

**Проверки:**
- `dotnet build --configuration Release` ✅ (0 ошибок, 0 предупреждений)
- `dotnet test` ✅ (29/29 passed: 15 old + 14 new)

**Follow-ups:**
- Шаг 06: LeagueLoader + LeagueFilter + DecisionEngine
- Шаг 08: KushClient использует тот же HttpClient-подход с proxy

---

## Шаг 06 — DONE (2026-02-21)
**Задача:** Парсер leagues.xlsx + LeagueFilter + DecisionEngine по правилам ТЗ.

**Сделано:**
- `Decision/LeagueSetting.cs` — модель стратегии: Sport, Leagues[], MinKf, MaxKf, BetTypeNb, BetTypeKush, IsInverse
- `Decision/LeagueLoader.cs` — чтение leagues.xlsx через ClosedXML:
  - Формат: A=Спорт, B=Лига, C=МинКф, D=МаксКф, E=Ставка_НБ, F=Ставка_Куш
  - Группировка по стратегиям (новый спорт = новая группа)
  - Поддержка запятой и точки как десятичного разделителя
- `Decision/LeagueFilter.cs` — фильтрация матчей по загруженным лигам:
  - Использует словарь замен лиг sl_chemps_zamen.json (NB→Kush нормализация)
  - Case-insensitive сравнение
  - Возвращает пары (Match, LeagueSetting) для дальнейшей обработки
- `Decision/BetDecision.cs` — модели: BetDecision (тип, passes, reasons) + MatchDecision (агрегация)
- `Decision/DecisionEngine.cs` — правила ставок из ТЗ:
  - kf1 > kf2: 1X(kf1≤8, kf1X≥1.5, kf2≥1.4), 1(kf1≤8, kf2≥1.4), 2(kf2≥1.5), X(same as 1X)
  - kf2 > kf1: 2(kf2≤8, kf1≥1.4), 1(kf1≥1.5)
  - kf1 == kf2: skip (no clear favourite)
  - Null odds: skip
  - Reasons с invariant culture formatting
- `Program.cs` — RunHeadless обновлён: NB → LeagueFilter → DecisionEngine, логи counts
- 17 тестов DecisionEngineTests: null odds, equal odds, home fav all pass, kf1>8, kf1X<1.5, kfX null, kf2<1.5, kf2<1.4, boundary values, away fav all pass, kf2>8, kf1<1.5, kf1<1.4, boundary, reasons
- 6 тестов LeagueFilterTests: matching, no match, case insensitive, rename dict, attaches setting, normalize

**Проверки:**
- `dotnet build --configuration Release` ✅ (0 ошибок, 0 предупреждений)
- `dotnet test` ✅ (52/52 passed: 29 old + 17 decision + 6 filter)

**Follow-ups:**
- Шаг 07: Matcher NB ↔ Kush (FuzzySharp + sl_chemps_zamen.json)
- Шаг 08: KushClient + pending queue

---

## Шаг 07 — DONE (2026-02-21)
**Задача:** Matcher NB ↔ Kush — сопоставление событий.

**Сделано:**
- `Kush/KushEvent.cs` — модель события Kush (EventId, League, Teams, StartTimeUtc, Odds dict, Url)
- `Kush/TeamNormalizer.cs` — нормализация имён команд:
  - ToLower → транслитерация кириллица→латиница → remove diacritics → remove punctuation → collapse whitespace
  - Генерированные Regex (source-generated) для производительности
- `Kush/EventMatcher.cs` — fuzzy matching NB ↔ Kush:
  - FuzzySharp `Fuzz.WeightedRatio` (WRatio) — порт RapidFuzz из legacy Python
  - Проверяет оба порядка (normal + swapped home/away)
  - TimeScore: линейный decay от 1.0 (exact) до 0.0 (на границе tolerance)
  - Confidence = nameScore * 0.70 + timeScore * 0.30
  - Configurable: tolerance hours, min confidence (из KushConfig)
- `Kush/MatchResult.cs` — результат матчинга: KushEvent?, NameScore, TimeScore, Confidence, IsAccepted, Reason
- ARCHITECTURE.md обновлён: детали алгоритма матчинга
- 10 тестов TeamNormalizerTests: lowercase, punctuation, whitespace, cyrillic, diacritics, mixed, edge cases
- 17 тестов EventMatcherTests: exact match, fuzzy names, cyrillic↔latin, swapped teams, time tolerance, confidence formula, threshold, best match selection, edge cases

**Проверки:**
- `dotnet build --configuration Release` ✅ (0 ошибок, 0 предупреждений)
- `dotnet test` ✅ (79/79 passed: 52 old + 10 normalizer + 17 matcher)

**Follow-ups:**
- Шаг 08: KushClient (HTTP, CSRF chain, поиск события) + pending queue
- Шаг 09: KushBetPlacer (авторизация, ratio check, dry-run)
