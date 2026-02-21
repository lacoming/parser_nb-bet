# ARCHITECTURE.md — parser_nb-bet

## Выбранный стек

> Стек зафиксирован по требованию заказчика: C# / .NET 8, минимальный вес, надёжность, нативный Windows.
> Context7 MCP недоступен в текущей среде — уточнение API через официальную документацию, отмечено в PROGRESS.md.

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| Язык | **C# 12 / .NET 8** | Нативный Windows, быстрый, типобезопасный, отличная поддержка WinForms |
| UI окно | **WinForms** (`System.Windows.Forms`) | Встроен в .NET, нативные диалоги, нет зависимостей |
| Трей | **`NotifyIcon`** (WinForms stdlib) | Нативный Windows-трей из коробки, контекстное меню, иконка |
| HTTP | **`HttpClient`** (stdlib) | Встроен в .NET, пул соединений, proxy support |
| Парсинг HTML | **HtmlAgilityPack** (NuGet) | Стандарт для C#, XPath/LINQ, малый вес |
| Excel | **ClosedXML** (NuGet) | Хороший API, поддержка шаблонов, без COM |
| Telegram | **`HttpClient`** напрямую (Bot API) | Без тяжёлых SDK, rate-limit руками |
| Состояние | **SQLite** через `Microsoft.Data.Sqlite` (NuGet) | Надёжно, транзакции, нет внешних зависимостей |
| Планировщик | **`PeriodicTimer`** + **`TimeZoneInfo`** (stdlib) | Встроен в .NET 6+, timezone MSK через TimeZoneInfo |
| Retry/backoff | **Polly** (NuGet) | Декларативные retry-политики |
| Fuzzy matching | **FuzzySharp** (NuGet) | Порт FuzzyWuzzy для C#, WRatio для матчинга команд |
| Логирование | **Serilog** (NuGet) | Файловая ротация, консоль, структурированные логи |
| Сборка .exe | **`dotnet publish`** | Self-contained single-file, win-x64, ~60–80 MB |

---

## Структура решения (C#)

```
parser_nb-bet/
├── ParserNbBet.sln
├── src/
│   └── ParserNbBet/               # Основной проект
│       ├── ParserNbBet.csproj     # WinForms, net8.0-windows
│       ├── Program.cs             # Точка входа (args парсинг, запуск)
│       ├── Config/                # Загрузка/валидация config.json
│       ├── Logging/               # Настройка логирования
│       ├── State/                 # SQLite — очередь, дедуп
│       ├── Nb/                    # Парсер nb-bet.com
│       ├── Kush/                  # KushClient + Matcher + BetPlacer
│       ├── Decision/              # DecisionEngine + LeagueFilter
│       ├── Excel/                 # ExcelWriter (ClosedXML)
│       ├── Telegram/              # TelegramNotifier
│       ├── Scheduler/             # Планировщик (PeriodicTimer)
│       └── Ui/                    # WinForms окно + NotifyIcon
├── tests/
│   └── ParserNbBet.Tests/         # xUnit тесты
│       └── ParserNbBet.Tests.csproj
├── scripts/
│   └── build.ps1                  # dotnet publish → dist/
├── assets/
│   ├── icon.ico
│   └── customer/                  # Шаблоны заказчика
├── _legacy/                       # Существующий код (не смешивать)
└── dist/                          # Артефакты сборки (не в git)
```

---

## Компоненты системы

### ParserNB (`Nb/`)
- **Назначение:** Получить список текущих матчей с `nb-bet.com/Results`.
- **Вход:** `AppConfig` (proxy, timeouts, retries).
- **Выход:** `IReadOnlyList<Match>`.
- **Детали:** Анализируем HTML/API в шаге 05. HttpClient + HtmlAgilityPack.
- **Namespace:** `ParserNbBet.Nb`

### LeagueFilter (`Decision/`)
- **Назначение:** Отфильтровать матчи по списку лиг из `leagues.xlsx`.
- **Вход:** `IEnumerable<Match>`, путь к `leagues.xlsx`.
- **Выход:** `IEnumerable<Match>` — только совпавшие лиги.
- **Namespace:** `ParserNbBet.Decision`

### DecisionEngine (`Decision/`)
- **Назначение:** Применить правила ставок по ТЗ.
- **Вход:** `Match` (Odds1, OddsX, Odds2).
- **Выход:** `Decision { BetType, Passes, Reasons }`.
- **Правила:**
  - Если kf1 > kf2 → ветка "1X / 1"
  - Если kf2 > kf1 → ветка "2 / X"
  - Точные пороги — из ТЗ, зафиксируем в шаге 06.
- **Namespace:** `ParserNbBet.Decision`

### Matcher (`Kush/`)
- **Назначение:** Сопоставить матч NB с событием на Куше.
- **Алгоритм:**
  - Нормализация: ToLower, удаление пунктуации, транслитерация.
  - Допуск по времени: ±2 часа (настраивается).
  - Confidence score (Levenshtein/fuzzy по названиям команд).
- **Порог:** < 0.80 → не ставим, только лог.
- **Namespace:** `ParserNbBet.Kush`

### KushClient (`Kush/`)
- **Назначение:** Получить список событий с `kushvsporte.ru`.
- **Методы:**
  - `GetEventsAsync()` → `IReadOnlyList<KushEvent>`
  - `FindEventAsync(Match)` → `KushEvent?`
- **Namespace:** `ParserNbBet.Kush`

### KushBetPlacer (`Kush/`)
- **Назначение:** Проставить ставку на Куше.
- **Формула:** `KfKush * (1 + ROI) / KfNB > threshold`
  - threshold: 1.10 (обычные), 1.05 (big leagues)
- **Dry-run:** флаг — не делает реальных запросов, только логирует.
- **Namespace:** `ParserNbBet.Kush`

### StateStore (`State/`)
- **Назначение:** Очередь матчей, ожидающих появления на Куше. Дедупликация.
- **Реализация:** SQLite, таблица `pending_matches`.
- **Ключ дедупа:** `match_key` = `{league}|{home}|{away}|{date}`.
- **Namespace:** `ParserNbBet.State`

### ExcelWriter (`Excel/`)
- **Назначение:** Записать результаты в `.xlsx` по шаблону заказчика.
- **Mapping-слой:** `IColumnMapper` — легко подменить колонки.
- **Выходные файлы:** `output/{yyyy-MM-dd}_results.xlsx`.
- **Namespace:** `ParserNbBet.Excel`

### TelegramNotifier (`Telegram/`)
- **Назначение:** Отправить уведомления в Telegram.
- **События:** MatchFound, MissingOnKush, BetPlaced, CriticalError.
- **Namespace:** `ParserNbBet.Telegram`

### Scheduler (`Scheduler/`)
- **Назначение:** Запускать цикл по расписанию.
- **Режимы:** `--once`, `--daemon`.
- **Расписание:** 08:00 МСК (`TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time")`), каждые 4 часа, окно 14 дней.
- **Graceful shutdown:** `CancellationToken`.
- **Namespace:** `ParserNbBet.Scheduler`

### UI + Tray (`Ui/`)
- **Назначение:** WinForms окно статуса + `NotifyIcon` трей.
- **UX:**
  - Старт → окно открыто (`MainForm.Show()`).
  - Кнопка "Скрыть" → `this.Hide()` + трей.
  - X (`FormClosing`) → модальный диалог "Выйти/Свернуть" (`MessageBox` или кастомный `Form`).
  - Трей (`NotifyIcon.ContextMenuStrip`): "Открыть окно", "Выход".
- **Статус в окне:** last run, next run, total matches, placed bets.
- **Namespace:** `ParserNbBet.Ui`

---

## Модели данных (C#)

```csharp
// Nb/Models.cs
public record Match(
    string MatchKey,       // "{league}|{home}|{away}|{date:yyyyMMdd}"
    string League,
    string TeamHome,
    string TeamAway,
    DateTime StartTimeUtc,
    string NbUrl,
    double? Odds1,
    double? OddsX,
    double? Odds2
) {
    public double? Odds1X => (Odds1.HasValue && OddsX.HasValue)
        ? Math.Min(Odds1.Value, OddsX.Value) : null;
}

// Decision/Models.cs
public record Decision(
    string MatchKey,
    string BetType,    // "1X" | "1" | "2" | "X" | "skip"
    bool Passes,
    IReadOnlyList<string> Reasons
);

// Kush/Models.cs
public record KushEvent(
    string KushId,
    string League,
    string TeamHome,
    string TeamAway,
    DateTime StartTimeUtc,
    IReadOnlyDictionary<string, double> Odds,
    string Url
);
```

---

## Поток данных (один цикл)

```
ParserNB.GetMatchesAsync()
    → LeagueFilter.Filter()
        → DecisionEngine.Decide()
            → foreach passing match:
                → KushClient.FindEventAsync()
                    → found  → BetPlacer.PlaceAsync() (если ratio OK)
                              → TelegramNotifier.NotifyPlaced()
                              → ExcelWriter.WriteRow()
                    → null   → StateStore.Enqueue()
                              → TelegramNotifier.NotifyMissing()
    → ExcelWriter.SaveAsync()
    → Scheduler.ScheduleNext()
```

---

## Matching NB ↔ Kush — правила

1. Нормализация: `ToLower() → Remove punctuation → Transliterate (ru→en если нужно)`.
2. Fuzzy match по двум командам (home + away) — Levenshtein similarity.
3. Проверка времени: `|nb_start - kush_start| ≤ 2h`.
4. `Confidence = nameScore * 0.7 + timeScore * 0.3`.
5. Порог: ≥ 0.80 → матч принят. Ниже → только лог, никакой ставки.

---

## Решения и ограничения

| Решение | Обоснование |
|---------|-------------|
| WinForms + NotifyIcon (не Electron/Qt) | Нативный Windows, малый .exe, нет доп. рантайма |
| `dotnet publish --self-contained` | Единый .exe без установки .NET на машину заказчика |
| `PeriodicTimer` вместо Quartz.NET | Встроен в .NET 6+, нет зависимостей |
| `TimeZoneInfo` вместо NodaTime | Stdlib, MSK = "Russian Standard Time" |
| SQLite вместо файла/JSON | Транзакции, надёжность, дедупликация без race conditions |
| ClosedXML вместо Interop | Без COM/Excel установленного, кросс-сборка |
| Polly для retry | Стандарт в .NET экосистеме, декларативные политики |
| FuzzySharp вместо ручного Levenshtein | Порт FuzzyWuzzy, WRatio = аналог legacy (RapidFuzz) |
| Нет `async` в UI-потоке | `Task.Run` + `Invoke` для обновления UI из фона |

---

## Стратегия сборки и публикации

### Self-contained vs Framework-dependent

| Вариант | Размер .exe | Требования к машине | Выбор |
|---------|-------------|---------------------|-------|
| **Self-contained** | ~60–80 MB | Ничего, всё внутри | ✅ Выбрано |
| Framework-dependent | ~5–10 MB | .NET 8 Runtime на машине | ❌ |

**Обоснование:** заказчику не нужно ставить .NET Runtime. Единый .exe — скопировал и запустил.

### Trimming (IL Linker)

Trimming (`PublishTrimmed=true`) может уменьшить .exe на 30–50%, но несёт риски:
- **WinForms** использует reflection — часть контролов может быть вырезана.
- **System.Text.Json** / **ClosedXML** / **SQLite** — reflection-heavy.
- **Polly v8** — может потерять strategy builders.

**Решение:** Trimming **отключён** по умолчанию. Включаем только после полного E2E-тестирования (шаг 14). При необходимости — добавим `TrimmerRootAssembly` для проблемных сборок.

### ReadyToRun (R2R)

`PublishReadyToRun=true` — AOT-прекомпиляция. Увеличивает .exe на ~10–15%, но ускоряет холодный старт. **Включено.**

### Publish command

```bash
dotnet publish src/ParserNbBet/ParserNbBet.csproj \
  --configuration Release \
  --runtime win-x64 \
  --self-contained true \
  -p:PublishSingleFile=true \
  -p:IncludeNativeLibrariesForSelfExtract=true \
  -p:PublishReadyToRun=true \
  --output dist/
```

### NuGet-зависимости (финальный список)

| Пакет | Версия | Назначение |
|-------|--------|------------|
| HtmlAgilityPack | 1.11.* | Парсинг HTML (Kush) |
| ClosedXML | 0.102.* | Excel-вывод |
| Microsoft.Data.Sqlite | 8.* | SQLite state store |
| Polly | 8.* | Retry/backoff |
| Polly.Extensions.Http | 3.* | HTTP retry helper |
| Serilog | 4.* | Логирование |
| Serilog.Sinks.File | 6.* | Файловый sink + ротация |
| Serilog.Sinks.Console | 6.* | Консольный sink |
| Serilog.Extensions.Logging | 8.* | Интеграция с ILogger |
| FuzzySharp | 2.0.* | Fuzzy matching команд |
