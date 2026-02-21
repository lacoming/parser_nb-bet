# EXISTING_CODE_REVIEW.md — Анализ legacy-кода

## 1. Обзор архивов

### nb3.zip (standalone парсер NB-Bet)
- **Язык:** Python 3 (tkinter GUI)
- **Файлы:** `nbbet.py`, `decode_key.py`, `sl_keys.json`, `nbbet.exe` (скомпилированный)
- **Назначение:** GUI-приложение для парсинга результатов с nb-bet.com (хоккей/футбол) за выбранный диапазон дат → вывод в Excel

### kushvsporte_autostavka.zip (автоставка)
- **Язык:** Python 3.10
- **Файлы:** `main.py`, `kushvsporte.py`, `nbbet.py`, `sopostavlenie.py`, `read_xlsx_settings.py`, `decode_key.py`, `settings.json`, `sl_stavok.json`, `sl_chemps_zamen.json`, `sl_keys.json`
- **Зависимости:** requests, beautifulsoup4, openpyxl, xlsxwriter, rapidfuzz
- **Назначение:** Полный цикл: парсинг NB → фильтрация по лигам/стратегиям → матчинг с kushvsporte.ru → автоставка → Telegram-уведомления

### ТЗ 2 бота - 1ХХХ.docx
- **Содержание:** Бизнес-требования (ставки, формулы, расписание) — см. раздел 6

---

## 2. Парсинг NB-Bet (ключевой для переиспользования)

### API-эндпоинт (НЕ HTML-парсинг!)
NB-Bet отдаёт данные через **JSON API**:
```
GET https://app.nb-bet.com/v1/soccer/math-analysis/page?timestamp={unix_ms}
GET https://app.nb-bet.com/v1/hockey/math-analysis/page?timestamp={unix_ms}
```

**Headers обязательные:**
- `Origin: https://nb-bet.com`
- `Referer: https://nb-bet.com/`
- `Accept: application/json, text/plain, */*`
- User-Agent (Firefox)

**Формат timestamp:** unix timestamp в миллисекундах (13 цифр), например `1708646399999` (конец дня 23:59:59).

### Структура JSON-ответа
```
response.json()['data']['leagues'] → массив лиг
  каждая лига:
    '1' → страна
    '3' → название лиги
    '4' → массив матчей
      каждый матч:
        '3' → ссылка/slug (для идентификации)
        '4' → unix timestamp (мс, 13 цифр → отрезать последние 3)
        '5' → КФ конечные {1: П1, 2: П2, 3: Х} (end odds)
        '6' → КФ начальные {1: П1, 2: П2, 3: Х} (start odds)
        '7' → home team name
        '15' → away team name
        '10','18' → итоговый счёт (home, away)
        '11','19' → счёт 1-го тайма/периода
        '26','27' → счёт 2-го
        '28','29' → счёт 3-го
        '46','47' → точный счёт
        '48' → МП (most probable) → {1: key_id, 2: end_kf, 3: start_kf}
        '49' → ПП (probably prediction)
        '50' → ПС (precise score prediction)
```

### Декодирование ключей ставок
Файл `sl_keys.json` содержит маппинг числовых ключей → строковые ключи ставок (>1000 записей).
Файл `decode_key.py` (1365 строк) — полная логика декодирования ключей ставок в читаемый вид.

**Решение:** sl_keys.json нужно включить в assets. Логику decode_key переписать на C# (структура if/else легко портируется).

---

## 3. Kushvsporte.ru (автоставка)

### Архитектура взаимодействия
1. **Получение лиг:** `GET https://kushvsporte.ru/centerbet/football?day={0|1}&_pjax=#center-bet`
   - Из HTML парсим: CSRF-токен (meta), PHPSESSID, _csrf (cookies), список стран (div.centerEventLink)

2. **Получение матчей по лиге:** `POST https://kushvsporte.ru/bet/event-list`
   - data: `{cid, day, status}`
   - cookies: `{PHPSESSID, _csrf}`
   - header: `X-CSRF-Token`
   - Из HTML: дата, время, команды, ссылка

3. **Получение коэффициентов:** `POST https://kushvsporte.ru/bet/cf-list`
   - data: `{eid}` (event ID из ссылки)
   - Из HTML: кнопки `button.coefLink` → ставка (div.d-sm-none) + коэф (span) + URL

4. **Авторизация:** `POST https://kushvsporte.ru/users/login`
   - `login-form[login]`, `login-form[password]`, `_csrf`
   - Сессионные cookies сохраняются

5. **Создание купона (ставка):**
   - `GET /coupon/add-coupon?eid={}&cfid={}`  → парсим hidden inputs (tokens)
   - `POST /coupon/create-coupon` → form data с токенами + `Coupon[bet_amount]=400`
   - Успех: `"Прогноз успешно добавлен"` в ответе

### Риски
- **CSRF-защита:** требуется правильная цепочка CSRF-токенов (meta + cookie + header)
- **Сессия:** нужны cookies PHPSESSID + _csrf, обновляемые при каждом шаге
- **Антибот:** нет явной капчи/JS-проверки, но сайт может добавить
- **Rate-limiting:** задержки 1.5–2.5 сек между запросами (legacy уже делает)
- **Лимит ставок:** в legacy есть `COUNT_LIMIT_STAVKA >= 30` (макс. 30 ставок за цикл)

---

## 4. Матчинг NB ↔ Kush (sopostavlenie.py)

### Алгоритм
- **Библиотека:** RapidFuzz (WRatio)
- **Порог:** `param_ratio = 87` (0–100)
- **Нормализация:** словарь замен `sl_chemps_zamen.json` (248+ записей, маппинг "Чемпионат X" → "Страна. Лига Y")
- **Логика:** для каждой лиги NB ищет лучший WRatio-матч среди лиг Kush. При 100% — удаляет из списка (1:1).

### Матчинг команд
- Используется slug из URL (`'-'.join(link.split('-')[1:]).split('-prognoz-na-match')[0]`)
- Если slug совпадает — прямое совпадение
- Иначе — fuzzy match по slug с порогом 81

**Решение для C#:** Использовать FuzzySharp (NuGet, порт FuzzyWuzzy) или SimMetrics. Словарь замен перенести 1:1.

---

## 5. Telegram-уведомления

### Реализация (в main.py)
- `POST https://api.telegram.org/bot{TOKEN}/sendDocument` — отправка xlsx-файла
- Настройки из `settings.json`: `TOKEN_API`, `CHAT_IDS` (массив)
- 3 попытки с задержкой 1.3 сек
- Отправка в несколько чатов

**Решение:** Переиспользуем 1:1, но через HttpClient (C#). Добавим sendMessage для текстовых уведомлений.

---

## 6. Ключевые требования из ТЗ (docx)

### Общий поток
1. Сканировать NB на необходимые лиги
2. Как появляются нужные матчи → проставлять на Куше + отправлять в ТГ
3. Если матч есть на NB, но нет на Куше → отложить в очередь + ТГ "отсутствуют на куше"
4. Когда появляется → проставить + ТГ "проставлено"

### Расписание
- Каждые **4 часа**, начиная с **08:00 МСК**
- Диапазон парсинга: **14 дней**
- Эти три значения должны быть **конфигурируемыми**

### Лиги
- Загружать через **Excel** (.xlsx)
- Формат таблицы: столбцы A=Спорт, B=Страна/Лига, C=Мин.кф, D=Макс.кф, E=Ставка_НБ, F=Ставка_Куш

### Виды ставок и условия

**При кф1 > кф2:**
| Ставка | Условия |
|--------|---------|
| 1X | кф1 ≤ 8, кф1X ≥ 1.5, кф2 ≥ 1.4 |
| 1 | кф1 ≤ 8, кф2 ≥ 1.4 |
| 2 | кф2 ≥ 1.5 |
| X | кф1 ≤ 8, кф1X ≥ 1.5, кф2 ≥ 1.4 |

**При кф2 > кф1:**
| Ставка | Условия |
|--------|---------|
| 2 | кф2 ≤ 8, кф1 ≥ 1.4 |
| 1 | кф ≥ 1.5 |

### Формула проставления на Куше
```
ratio = КфКуш * (1 + ROI) / КфНБ
```
- **Обычные лиги:** ratio > **1.10** → ставим
- **Биг-лиги:** ratio > **1.05** → ставим (отдельный список)

### Направление ставки (прямая/обратная)
- Если ставка NB ≠ ставка Куш → обратная ставка
- sl_stavok.json: `{"ТБ (2.5)": ["ТБ (2.50)", "ТМ (2.50)"], ...}` — [0]=прямая, [1]=обратная

### Логика "сразу vs за час до игры"
- Если кэф **падает** (start ≥ end) → ставим **сразу**
- Если кэф **растёт** (start < end) → ставим **за час до начала**
- Для обратной ставки — логика зеркальная

---

## 7. Что переиспользовать / переписать

### Переиспользуемое 1:1 (данные/конфиги):
| Что | Файл | Как |
|-----|-------|-----|
| Словарь ключей ставок | `sl_keys.json` | Скопировать в assets/ |
| Словарь замен лиг NB↔Kush | `sl_chemps_zamen.json` | Скопировать в assets/ |
| Словарь ставок NB→Kush | `sl_stavok.json` | Скопировать в assets/ |
| Excel-шаблон (шапка колонок) | `nbbet.py` (zapis_v_exel_*) | Портировать в ClosedXML |

### Переписать на C# (логика):
| Модуль | Legacy-файл | Объём |
|--------|------------|-------|
| NB API client | `nbbet.py` (get_matches) | ~100 строк → Match model + HttpClient |
| Kush HTML parser | `kushvsporte.py` | ~580 строк → HtmlAgilityPack |
| Kush auth + bet placer | `kushvsporte.py` (login, add_coupon, create_coupon) | ~200 строк |
| League matcher (fuzzy) | `sopostavlenie.py` | ~50 строк → FuzzySharp |
| Settings reader (xlsx) | `read_xlsx_settings.py` | ~100 строк → ClosedXML |
| Decision engine | `main.py` (условия из ТЗ) | Новый модуль |
| Decode key | `decode_key.py` | ~1350 строк (по желанию, или просто sl_keys.json lookup) |
| Excel writer | `nbbet.py` (zapis_v_exel_*) | ~250 строк → ClosedXML mapping |
| Scheduler | `main.py` (start_monitor) | Переписать на PeriodicTimer |

### Не переиспользуемое:
- tkinter GUI → заменяем на WinForms (уже есть каркас)
- xlsxwriter → заменяем на ClosedXML
- requests → заменяем на HttpClient

---

## 8. Риски и нюансы

1. **NB-Bet API без аутентификации:** API публичный, но может измениться. Нет документации. Мониторить стабильность.
2. **Kushvsporte CSRF-цепочка:** Сложная последовательность CSRF-токенов. Нужно точно воспроизвести.
3. **Кодировка:** Legacy использует кириллицу в путях и именах файлов. В C# на Windows — ОК.
4. **Сумма ставки:** Хардкод `400` в legacy (`Coupon[bet_amount]`). Сделать конфигурируемой.
5. **Лимит ставок:** 30 за цикл (legacy). Сделать конфигурируемым.
6. **Прокси:** Legacy НЕ использует прокси. Нужно добавить (требование из CLAUDE.md).
7. **Обратная ставка:** Логика "прямая/обратная" зависит от совпадения ставки NB и Kush — важно не перепутать.
8. **Сессия Kush:** Может протухать. Нужен retry с повторной авторизацией.
9. **Credentials в settings.json:** Legacy хранит логин/пароль в JSON. Мы делаем так же, но .gitignore.
