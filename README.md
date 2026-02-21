# parser_nb-bet

Windows-приложение (.exe) для автоматического парсинга ставок с nb-bet.com и синхронизации с kushvsporte.ru.

## Возможности

- Парсинг матчей с NB-Bet (JSON API)
- Фильтрация по лигам из `leagues.xlsx`
- Автоматические решения по ставкам (1X / 1 / 2 / X) по правилам ТЗ
- Синхронизация с kushvsporte.ru (поиск событий, автоставка)
- Уведомления в Telegram
- Вывод результатов в Excel (.xlsx)
- Поддержка прокси
- Режимы: `--once` (однократно) и `--daemon` (по расписанию)
- GUI (Tkinter) с логом и кнопками управления

## Стек

- Python 3.11+
- requests, beautifulsoup4, lxml, rapidfuzz, openpyxl, xlsxwriter
- tkinter (stdlib), threading + zoneinfo (stdlib)
- PyInstaller + UPX (exe < 10 МБ)

## Установка (разработка)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск

```bash
# Однократный цикл (dry-run)
python src/main.py --once --dry-run

# Daemon режим
python src/main.py --daemon

# GUI режим (по умолчанию)
python src/main.py

# Тест Telegram
python src/main.py --test-telegram
```

## Сборка .exe

```powershell
.\scripts\build.ps1
# Результат: dist\parser_nb-bet.exe (< 10 МБ)
```

## Конфигурация

Скопируйте `config.example.json` → `config.json` и заполните:
- Telegram token и chat_ids
- Kush логин/пароль
- Пороги ставок

Подробности: [CONFIG.md](CONFIG.md)

## Структура

```
src/          — исходный код
tests/        — тесты (pytest)
assets/data/  — справочники (sl_keys, sl_chemps_zamen, sl_stavok)
scripts/      — скрипты сборки
_legacy/      — legacy код (не в git)
dist/         — собранный exe (не в git)
```
