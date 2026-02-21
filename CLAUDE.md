# CLAUDE.md — Project instructions for Claude Code (parser_nb-bet)

## Project goal (what we’re building)
We are building a lightweight Windows desktop app (.exe) that:
1) Parses https://nb-bet.com/Results for current matches.
2) Filters matches by leagues loaded from `leagues.xlsx` and applies betting decision rules (1X / 1 / 2 / X) per spec.
3) Syncs with https://kushvsporte.ru/:
   - if event missing -> enqueue "pending kush" + send Telegram signal "missing on kush"
   - if event appears -> compute ratio threshold -> place bet (or dry-run) + Telegram "placed"
4) Outputs results to Excel `.xlsx` by customer template.
5) Sends Telegram notifications to configured chats.
6) Supports proxies loaded from `proxies.txt`.
7) Runs either:
   - `--once` (single cycle then exit)
   - `--daemon` (scheduled: from 08:00 MSK, every 4 hours, window 14 days; configurable)
8) Has UI window + tray behavior:
   - On app start: UI window opens.
   - Button/menu "Hide window" -> hide to tray.
   - Clicking window close (X) shows dialog: "Exit or minimize?" with buttons:
     - "Exit" -> terminate app
     - "Minimize" -> hide to tray
   - Tray icon right-click menu includes:
     - "Open window"
     - "Exit"
     - (optional) "Run now", "Pause/Resume", "Open logs"

Non-functional:
- Keep .exe size small (avoid Electron/Qt).
- Robust to failures (timeouts, retries, partial site outages).
- Clear logs; minimal dependencies.

---

## Working style (how to proceed)
We work step-by-step. One step = one prompt = one deliverable.
At the end of each step you MUST:
- Update `PROGRESS.md` (mark step DONE, add a short summary, list any follow-ups).
- Show verification outputs (commands + results).
- Commit changes with a meaningful message (unless explicitly told not to).

When unsure, prefer:
- small, testable increments
- documented decisions in `ARCHITECTURE.md`

---

## Critical constraints
- Do NOT introduce heavy GUI frameworks (Electron, Qt) unless explicitly approved.
- Prefer a minimal UI/tray solution.
- Keep all secrets out of repo: Telegram tokens, credentials must be in config files excluded by `.gitignore`.
- Never hardcode chat IDs, tokens, proxies, or credentials.

---

## Source of truth
- Product behavior and UX are defined in this repo’s docs:
  - `ARCHITECTURE.md`
  - `CONFIG.md`
  - `PROGRESS.md`
If a conflict appears, update docs first and then implement.

---

## Context7 requirement (mandatory for tech stack docs)
Whenever you need to use or confirm library/framework behavior (APIs, tray, packaging, excel writer, telegram, scheduler, HTTP client, etc.), you MUST use Context7 MCP:

1) Resolve library:
   - tool: `resolve-library-id`
   - inputs: `libraryName` + short `query` describing what you need

2) Query docs:
   - tool: `query-docs`
   - inputs: `libraryId` + `query` about exact API/usage

Use Context7 especially before:
- choosing the GUI/tray library
- implementing Excel writing
- implementing Telegram bot sending
- setting up packaging/build into .exe
- implementing scheduling/timezones (MSK)

If Context7 is unavailable or fails:
- fall back to official docs via web search (and note it in `PROGRESS.md`).

---

## Repository structure (intended)
- `src/` — app code
  - `config/` — config schema + loader + validation
  - `logging/` — logger setup (file + rotation)
  - `state/` — persistent state (pending queue, dedupe)
  - `nb/` — NB parser client
  - `kush/` — Kush client + bet placer
  - `decision/` — decision engine (rules from spec)
  - `excel/` — excel writer
  - `telegram/` — telegram notifier
  - `scheduler/` — scheduling + run orchestration
  - `ui/` — UI window + tray + dialogs
- `tests/` — unit tests (decision engine, normalization, config)
- `_legacy/` — unpacked reference code (do not mix into new code)
- `dist/` — release artifacts (ignored by git)
- `scripts/` — build and helper scripts

---

## Implementation rules
### Networking
- Centralize HTTP client config (timeouts, retries, proxy).
- Add sane retry/backoff for transient failures.
- Respect robots/ToS; don’t DoS target sites.

### Data model
- Use a normalized `Match` model:
  - league, team_home, team_away, start_time, nb_url/id
  - odds1, oddsX, odds2, (optional) derived odds1X
- Stable `match_key` for dedupe & state.

### Decision engine
Implement exact rules from spec:
- Branch on `kf1 > kf2` vs `kf2 > kf1`
- Produce `{bet_type, passes, reasons[]}`

### Matching NB ↔ Kush
- Normalize team names (casefold, punctuation removal; optionally transliteration).
- Time tolerance window.
- Confidence score. Never place bet if confidence is low.

### Scheduler
- Must support `--once` and `--daemon`.
- `--daemon` computes next run times based on MSK start time + interval.
- Support graceful shutdown.

### UI/Tray
- Start with window visible.
- "Hide window" -> tray.
- On X -> modal dialog "Exit or minimize?" with two buttons.
- Tray menu includes "Open window" and "Exit" at minimum.

### Excel
- Implement mapping layer so customer template can be plugged in easily.

### Telegram
- Support multiple chats.
- Rate-limit to avoid flood.
- Provide a `--test-telegram` mode if useful.

---

## Commands & verification (required)
After coding changes, run relevant checks and paste results into the chat:
- unit tests (`pytest` / `dotnet test` / etc.)
- lint/format checks
- a quick `--once` run (dry-run) showing logs

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
- Any customer-provided templates (store in `/assets/customer/` and confirm if they can be committed)