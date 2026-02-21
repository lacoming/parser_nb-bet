# ARCHITECTURE.md — parser_nb-bet

## Выбранный стек

> Context7 MCP недоступен в текущей среде — стек выбран на основе официальной документации и практики.
> Зафиксировано в PROGRESS.md (шаг 01).

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| Язык | **Python 3.11** | Лучшая экосистема для парсинга/Excel/Telegram, хорошая поддержка PyInstaller |
| UI окно | **tkinter** (stdlib) | Встроен в Python, нет зависимостей, достаточно для статусного окна |
| Трей | **pystray** | Минимальная библиотека, Windows-native трей, PIL/Pillow для иконки |
| HTTP | **httpx** | Async-capable, нативная поддержка прокси, retries через tenacity |
| Парсинг HTML | **BeautifulSoup4** + **lxml** | Стандарт, быстрый парсер |
| Динамические страницы | **playwright** (только если нужно, по факту анализа) | Резерв |
| Excel | **openpyxl** | Нативная работа с .xlsx, шаблоны, mapping-слой |
| Telegram | **httpx** (Bot API напрямую) | Без тяжёлых фреймворков, rate-limit своими руками |
| Состояние | **SQLite** (stdlib sqlite3) | Надёжно, нет лишних зависимостей |
| Планировщик | **APScheduler** | Поддержка timezone (MSK/pytz), cron-style и interval |
| Сборка .exe | **PyInstaller** | Де-факто стандарт для Python→.exe, хорошая поддержка Windows |
| Retries/backoff | **tenacity** | Простая декораторная схема |
| Timezone | **pytz** | MSK (Europe/Moscow) |

---

## Компоненты системы

### ParserNB
- **Назначение:** Получить список текущих матчей с `nb-bet.com/Results`.
- **Вход:** config (proxy, timeouts, retries).
- **Выход:** `list[Match]` — нормализованный список матчей.
- **Детали:** Анализируем HTML/API (шаг 05). Если сайт использует JS-рендеринг — подключаем playwright.
- **Файлы:** `src/nb/`

### LeagueFilter
- **Назначение:** Отфильтровать матчи по списку лиг из `leagues.xlsx`.
- **Вход:** `list[Match]`, путь к `leagues.xlsx`.
- **Выход:** `list[Match]` — только совпавшие лиги.
- **Файлы:** `src/decision/league_filter.py`

### DecisionEngine
- **Назначение:** Применить правила ставок по ТЗ.
- **Вход:** `Match` (odds1, oddsX, odds2).
- **Выход:** `Decision(bet_type, passes, reasons[])`.
- **Правила:**
  - Если kf1 > kf2 → ветка "1X / 1"
  - Если kf2 > kf1 → ветка "2 / X"
  - Точные пороги — из ТЗ, зафиксируем в шаге 06.
- **Файлы:** `src/decision/engine.py`

### Matcher (NB ↔ Kush)
- **Назначение:** Сопоставить матч NB с событием на Куше.
- **Алгоритм:**
  - Нормализация команд: casefold, удаление пунктуации, транслитерация.
  - Допуск по времени: ±2 часа (настраивается).
  - Confidence score (fuzzy match по названиям команд).
- **Порог доверия:** < 0.80 → не ставим, только лог.
- **Файлы:** `src/kush/matcher.py`

### KushClient
- **Назначение:** Получить список событий с `kushvsporte.ru`.
- **Методы:**
  - `get_events()` → `list[KushEvent]`
  - `find_event(nb_match)` → `KushEvent | None`
- **Файлы:** `src/kush/client.py`

### KushBetPlacer
- **Назначение:** Проставить ставку на Куше.
- **Формула:** `KfKush * (1 + ROI) / KfNB > threshold`
  - threshold: 1.10 (обычные), 1.05 (big leagues)
- **Dry-run:** не делает реальных запросов, только логирует.
- **Файлы:** `src/kush/bet_placer.py`

### PendingQueue (State)
- **Назначение:** Очередь матчей, ожидающих появления на Куше.
- **Реализация:** SQLite таблица `pending_matches`.
- **Дедупликация:** по `match_key` (league + teams + date).
- **Файлы:** `src/state/`

### ExcelWriter
- **Назначение:** Записать результаты в `.xlsx` по шаблону заказчика.
- **Mapping-слой:** легко подменить колонки без изменения логики.
- **Выходные файлы:** `output/<date>_results.xlsx`.
- **Файлы:** `src/excel/`

### TelegramNotifier
- **Назначение:** Отправить уведомления в Telegram.
- **События:**
  - Match найден и проходит фильтры.
  - Отсутствует на Куше.
  - Ставка проставлена.
  - Критическая ошибка.
- **Файлы:** `src/telegram/`

### Scheduler
- **Назначение:** Запускать цикл по расписанию.
- **Режимы:**
  - `--once`: один цикл и выход.
  - `--daemon`: 08:00 МСК, каждые 4 часа, окно 14 дней.
- **Graceful shutdown:** Ctrl+C, сигнал из UI.
- **Файлы:** `src/scheduler/`

### UI + Tray
- **Назначение:** Окно статуса + трей.
- **UX:**
  - Старт → окно открыто.
  - Кнопка "Скрыть" → трей.
  - X → диалог "Выйти/Свернуть".
  - Трей правый клик: "Открыть окно", "Выход".
- **Статус в окне:** last run, next run, total matches, placed bets.
- **Файлы:** `src/ui/`

---

## Модель данных

### Match
```python
@dataclass
class Match:
    match_key: str           # Стабильный ключ (league + teams + date)
    league: str
    team_home: str
    team_away: str
    start_time: datetime     # UTC
    nb_url: str
    odds1: float | None
    oddsX: float | None
    odds2: float | None
    odds1X: float | None     # Вычисляется: min(odds1, oddsX)
```

### Decision
```python
@dataclass
class Decision:
    match_key: str
    bet_type: str            # "1X" | "1" | "2" | "X" | "skip"
    passes: bool
    reasons: list[str]
```

### KushEvent
```python
@dataclass
class KushEvent:
    kush_id: str
    league: str
    team_home: str
    team_away: str
    start_time: datetime
    odds: dict[str, float]   # {"1": 1.85, "X": 3.5, "2": 2.1}
    url: str
```

---

## Поток данных (один цикл)

```
ParserNB.get_matches()
    → LeagueFilter.filter()
        → DecisionEngine.decide()
            → [for each passing match]
                → KushClient.find_event()
                    → [found] → BetPlacer.place() (если ratio OK)
                              → TelegramNotifier.notify("placed")
                              → ExcelWriter.write_row()
                    → [not found] → PendingQueue.enqueue()
                                  → TelegramNotifier.notify("missing")
    → ExcelWriter.save()
    → Scheduler.schedule_next()
```

---

## Matching NB ↔ Kush — правила

1. Нормализация команды: `lower() → strip punctuation → translit (рус→лат при необходимости)`.
2. Fuzzy match по двум командам (home + away).
3. Проверка времени: `|nb_start - kush_start| ≤ 2h`.
4. Confidence = `(name_score * 0.7) + (time_score * 0.3)`.
5. Порог: ≥ 0.80 → матч принят.
6. Если confidence < 0.80 → не ставим, только лог (никогда не ставить при низком доверии).

---

## Решения и ограничения

| Решение | Обоснование |
|---------|-------------|
| tkinter + pystray (не Electron) | Малый размер .exe, нет Node.js |
| SQLite (не Redis/файл) | Встроен в Python, надёжен, транзакции |
| httpx вместо aiohttp | Синхронный режим проще для одного потока + async резерв |
| APScheduler вместо cron | Работает внутри процесса, Windows-совместим |
| PyInstaller --onefile | Единый .exe, проще для заказчика |
