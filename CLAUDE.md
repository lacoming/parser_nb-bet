# CLAUDE.md — Project instructions for Claude Code (parser_nb-bet)

## Model policy (MANDATORY)
We are working with Claude Code prompts intended for **Claude Opus 4.6**.

**Before you do any work**, confirm the active model in this session is **Opus 4.6**.
- If the active model is not Opus 4.6 (e.g., Sonnet), STOP and reply with a single line:
  **"Active model is not Opus 4.6. Switch to Opus 4.6 and re-run this prompt."**
  Do not change files in that case.

> Note: User sends steps after `/clear`. Therefore you MUST rely on repository documents (below) and re-open them each step.

---

## Step preflight (MANDATORY at the start of every step)
At the beginning of every step:
1) Read these files (if they exist): `PLAN.md`, `PROGRESS.md`, `ARCHITECTURE.md`, `CONFIG.md`, `CLAUDE.md`.
2) Print the intended step number and title.
3) Verify environment prerequisites:
   - `python --version` must be available (requires Python 3.11+).
   - If `python` is missing, do NOT proceed; instead:
     - update `PROGRESS.md` with a blocking note
     - print installation instruction for Python 3.11+
     - stop.

At the end of every step:
- Update `PROGRESS.md` (mark DONE, short summary, follow-ups).
- Run verifications relevant to the change (pytest, lint, run).
- Show `git status`.
- Commit with a meaningful message (unless explicitly told not to).

---

## Project goal (what we're building)
We are building a Windows desktop app (.exe, **<10 MB** via PyInstaller) that:
1) Parses https://nb-bet.com/Results for current matches (JSON API).
2) Filters matches by leagues loaded from `leagues.xlsx` and applies betting decision rules (1X / 1 / 2 / X) per spec.
3) Syncs with https://kushvsporte.ru/:
   - if event missing -> enqueue "pending" + send Telegram signal "missing on kush"
   - if event appears -> compute ratio threshold -> place bet (or dry-run) + Telegram "placed"
4) Outputs results to Excel `.xlsx` by customer template.
5) Sends Telegram notifications to configured chats.
6) Supports proxies loaded from `proxies.txt`.
7) Runs either:
   - `--once` (single cycle then exit; optional no-UI)
   - `--daemon` (scheduled: from 08:00 MSK, every 4 hours, window 14 days; configurable)
8) Has Tkinter UI window:
   - On app start: UI window opens.
   - Buttons: "Запустить", "Пауза", "Скрыть", "Выход".
   - Clicking window close (X) shows dialog: "Хотите выйти или свернуть?"
   - Optional tray icon via pystray (dynamic import, not required).

Non-functional:
- **exe < 10 MB** (PyInstaller + UPX).
- No Electron/Qt.
- Robust to failures (timeouts, retries, partial site outages).
- Clear logs; minimal dependencies.

---

## Tech stack (FIXED — Python)
**Python 3.11+ / PyInstaller** (Windows .exe).

| Component | Library | Notes |
|-----------|---------|-------|
| HTTP | `requests` | Session-based, proxy support |
| HTML parse | `beautifulsoup4` + `lxml` | Kush HTML parsing |
| Fuzzy match | `rapidfuzz` | WRatio for team matching |
| Excel read | `openpyxl` | leagues.xlsx |
| Excel write | `xlsxwriter` | Output results |
| GUI | `tkinter` (stdlib) | Window, buttons, log viewer |
| Scheduler | `threading` + `zoneinfo` (stdlib) | MSK = Europe/Moscow |
| Logging | `logging` + `RotatingFileHandler` (stdlib) | File + console |
| Telegram | `requests` (Bot API) | Direct HTTP, no SDK |
| State | In-memory dicts/sets | No SQLite needed |
| Retry | Manual (loop + sleep) | No tenacity |
| Packaging | PyInstaller + UPX | --onefile, <10 MB |

Do NOT introduce Node/Electron, Qt, C#/.NET, or heavy frameworks.

---

## Source of truth
Product behavior and UX are defined in this repo's docs:
- `PLAN.md` (step-by-step prompts)
- `ARCHITECTURE.md`
- `CONFIG.md`
- `PROGRESS.md`

If a conflict appears, update docs first and then implement.

---

## Working style (how to proceed)
We work step-by-step. One step = one prompt = one deliverable.

When unsure, prefer:
- small, testable increments
- documented decisions in `ARCHITECTURE.md`
- keep PR-size changes
- no speculative refactors

---

## Repository structure (intended)
```
parser_nb-bet/
├── src/
│   ├── main.py              # Entry point (argparse)
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py        # JSON config loader + validation
│   │   └── schema.py        # Dataclass config models
│   ├── log_setup.py         # logging + RotatingFileHandler
│   ├── state.py             # In-memory state (dicts/sets)
│   ├── nb/
│   │   ├── __init__.py
│   │   ├── client.py        # NB-Bet JSON API parser
│   │   ├── models.py        # Match dataclass
│   │   └── odds_decoder.py  # sl_keys.json decoder
│   ├── kush/
│   │   ├── __init__.py
│   │   ├── session.py       # requests.Session + CSRF
│   │   ├── client.py        # KushClient (events, odds)
│   │   ├── matcher.py       # EventMatcher (rapidfuzz)
│   │   ├── normalizer.py    # Team name normalization
│   │   ├── bet_placer.py    # Ratio check + bet placement
│   │   ├── bet_result.py    # BetResult dataclass
│   │   └── models.py        # KushEvent, MatchResult
│   ├── decision/
│   │   ├── __init__.py
│   │   ├── engine.py        # Decision rules from spec
│   │   ├── league_loader.py # openpyxl leagues.xlsx reader
│   │   ├── league_filter.py # Filter + sl_chemps_zamen mapping
│   │   └── models.py        # LeagueSetting, BetDecision
│   ├── telegram/
│   │   ├── __init__.py
│   │   └── notifier.py      # Bot API notifications
│   ├── excel/
│   │   ├── __init__.py
│   │   ├── writer.py        # xlsxwriter output
│   │   ├── default_mapper.py
│   │   └── models.py        # ExcelRow
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── msk_scheduler.py # MSK timezone scheduler
│   │   └── cycle_runner.py  # Full cycle orchestration
│   └── ui/
│       ├── __init__.py
│       └── main_window.py   # Tkinter window
├── tests/                   # pytest tests (~130+)
├── assets/data/             # sl_keys.json, sl_chemps_zamen.json, sl_stavok.json
├── scripts/build.ps1        # PyInstaller build
├── config.example.json
├── requirements.txt
├── _legacy/                 # Reference code (not committed)
└── dist/                    # PyInstaller output (not committed)
```

---

## Implementation rules

### Secrets & configuration
- Never commit secrets: Telegram tokens, credentials, proxies, cookies.
- `config.json`, `proxies.txt`, customer-provided sensitive files are excluded by `.gitignore`.
- Provide `config.example.json` without secrets.

### Networking
- Use `requests.Session` for connection reuse.
- Add retry with exponential backoff for transient failures.
- Respect robots/ToS; don't DoS target sites (rate limits).

### Data model
Use a normalized `Match` dataclass:
- league, team_home, team_away, start_time_utc, nb_slug
- odds_1, odds_x, odds_2, odds_1x (derived)
- stable `match_key` for dedupe

### Decision engine
Implement exact rules from spec:
- Branch on `kf1 > kf2` vs `kf2 > kf1`
- Produce `{ bet_type, passes, reasons[] }`

### Matching NB ↔ Kush
- Normalize team names (lower, punctuation removal; transliteration).
- Time tolerance window (±2h default).
- Confidence score (name 70% + time 30%). Never place bet if confidence < 0.80.

### Scheduler
- Must support `--once` and `--daemon`.
- `--daemon` computes next run times based on MSK start time + interval.
- Support graceful shutdown via threading.Event.

### UI (Tkinter)
- Start with window visible.
- Buttons: "Запустить", "Пауза", "Скрыть", "Выход".
- On X -> messagebox "Хотите выйти или свернуть?" with "Выйти"/"Свернуть".
- Thread-safe log viewer via root.after().

### Excel
- Implement mapping layer so customer template can be plugged in easily.

### Telegram
- Support multiple chats.
- Rate-limit to avoid flood.
- Provide a `--test-telegram` mode.

---

## Commands & verification (required)
After coding changes, run relevant checks:
- `python -m pytest tests/ -v`
- Smoke run: `python src/main.py --once --dry-run`

Always include:
- `git status`
- what changed (short summary)

---

## What to update when you learn something new
If you:
- discover an API endpoint for NB or Kush
- learn exact Excel template columns
- refine matching rules
Then update:
1) `ARCHITECTURE.md` or `CONFIG.md`
2) `PROGRESS.md` with the new assumption/decision
Then implement.

---

## Files to treat carefully
- `config.json` (local)
- `proxies.txt` (local)
- Telegram tokens/credentials (never commit)
- Customer templates (store in `assets/customer/` and commit only with permission)
