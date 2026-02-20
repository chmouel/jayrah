# MIGRATION: Python -> Rust Ratatui TUI

## Rewrite Status
- overall_phase: Phase 0
- last_updated: 2026-02-20
- owner: TBD

## Required Step Log (append-only)
All rewrite contributors must append a log entry for each meaningful step. Do not rewrite or delete historical entries.

Required format:
`YYYY-MM-DD HH:MM UTC | actor | area | action | result | next`

## Step Log Entries
2026-02-20 00:00 UTC | codex | migration-doc | Initialized root migration doc and logging scaffold | complete | Continue with AGENTS rewrite governance update
2026-02-20 00:05 UTC | codex | repo-governance | Added mandatory rewrite workflow rules in AGENTS.md | complete | Finalize migration document move
2026-02-20 00:07 UTC | codex | docs-cleanup | Removed old misc migration file after moving plan to root MIGRATION.md | complete | Ready for Phase 0 implementation

---

# Rust + Ratatui TUI Migration Plan (MVP)

## Goal
Ship a lean, highly responsive Rust TUI for browsing Jira issues, while keeping the current Python app working during migration.

## Scope: TUI Only
This plan intentionally excludes web UI, MCP server, and non-TUI command redesign.

## Current TUI Feature Inventory (Python/Textual)
Current implementation lives in:
- `jayrah/ui/tui/app.py`
- `jayrah/ui/tui/actions.py`
- `jayrah/ui/tui/views.py`

Core browse flow today:
- issue table with keyboard navigation
- detail preview panel with async loading and cache
- fuzzy filter modal
- board switching
- reload
- open issue in browser
- choose mode (`--choose`) with selected issue return

Additional modals/actions today:
- comments (view/add)
- labels/components edit
- transitions
- edit title/description
- custom field edit
- actions palette

## MVP Definition (What We Build First)
MVP includes only the minimum high-value browsing loop:
1. Load issues for one board/query
2. Fast list navigation (`j/k`, arrows)
3. Detail pane for selected issue
4. Inline or modal text filter
5. Reload issues
6. Open selected issue in browser
7. Optional choose mode (return selected ticket key)

Not in MVP:
- comments, transitions, edit flows, custom field edit, board switcher modal
- command palette parity
- full theming parity with Textual CSS

## Architecture Decision for MVP
Use a **hybrid migration** to move fast:
- Frontend/UI: Rust + Ratatui + Crossterm
- Data backend for MVP: Python CLI adapter subprocess calls (reuse existing Jira/auth/config behavior)

Rationale:
- avoids rewriting auth/config/Jira edge cases immediately
- lets us focus on responsiveness and interaction quality
- keeps risk low and iteration fast

## Proposed Rust Layout
Create a Rust workspace under `rust/`:
- `rust/jayrah-tui/` (ratatui app)
- `rust/jayrah-adapter/` (calls existing Python CLI commands, parses JSON/CSV)
- `rust/jayrah-model/` (shared structs + app state)

## Backend Adapter Contract (MVP)
Add stable machine-readable commands in Python (if missing) and treat them as contract:
- list issues for board/query (JSON)
- fetch issue details by key (JSON)
- open issue URL by key (or return URL)

Guideline:
- adapter commands must be deterministic and schema-stable
- stderr for logs, stdout for machine data only

## Performance Targets
- key navigation latency: < 16 ms perceived (no blocking on render loop)
- first issue list render: < 1 s on warm cache
- detail pane update on selection: immediate placeholder + async fetch
- no UI freezes during network/API calls

## Execution Phases

### Phase 0: Contract and Scaffold
- create Rust workspace and crates
- define JSON schemas for list/detail payloads
- add/verify Python CLI machine endpoints for TUI needs

Exit criteria:
- Rust app can fetch and print issues via adapter

### Phase 1: Browsing MVP UI
- two-pane ratatui layout (table + detail)
- keyboard navigation and selection state
- async fetch pipeline with cancellation/debounce for rapid cursor moves
- reload and filter actions

Exit criteria:
- daily browse flow works end-to-end without Textual

### Phase 2: CLI Integration
- expose new entrypoint (example: `jayrah browse --ui rust`)
- keep Textual path available as fallback
- add feature flag/config toggle for default UI

Exit criteria:
- users can switch between old/new TUI safely

### Phase 3: Post-MVP Features
- comments, transitions, edits, custom fields, board switcher
- progressively replace adapter with native Rust Jira client if desired

Exit criteria:
- decide whether to keep hybrid backend or complete full Rust client rewrite

## State Model (Ratatui)
Single source of truth:
- `AppState { issues, filtered_indices, selected_idx, detail_cache, loading_flags, mode }`

Event loop model:
- input events -> reducer/state transition
- async worker results -> message queue -> state update
- render from immutable snapshot per tick

## Testing Strategy
MVP tests should focus on behavior, not styling:
- adapter parsing tests (JSON/CSV fixtures)
- reducer/state transition tests (selection, filtering, reload)
- snapshot tests for key screen states
- one end-to-end smoke test with mocked adapter responses

## Risks and Mitigations
- Risk: subprocess adapter latency
  - Mitigation: cache detail payloads, debounce detail fetches, prefetch nearby rows
- Risk: schema drift between Python output and Rust parser
  - Mitigation: versioned JSON schema + fixture-based contract tests
- Risk: dual-stack maintenance burden
  - Mitigation: strict MVP boundary and phased deprecation decision

## Immediate Next Tasks
1. Add machine-friendly Python command(s) for `browse list` and `issue show` if output is not stable enough.
2. Scaffold `rust/jayrah-tui` with event loop, static mock data screen, and keymap.
3. Wire adapter call for real issue list and render table rows.
2026-02-20 16:41 UTC | codex | phase0-contract | Started Step 1 implementation for machine-friendly browse/detail endpoints | in_progress | Add dedicated CLI machine commands and tests
2026-02-20 16:42 UTC | codex | phase0-contract | Added new CLI endpoints `jayrah cli browse-list` and `jayrah cli issue-show` with stable JSON payload helpers | complete | Add contract-focused tests and run targeted pytest
2026-02-20 16:43 UTC | codex | phase0-contract | Added machine contract tests for browse-list and issue-show endpoints | complete | Run targeted lint and pytest for new contract surface
2026-02-20 16:43 UTC | codex | phase0-contract | Verified new machine endpoints with pytest and ruff checks (6 tests passed) | complete | Step 1 baseline complete; proceed to Rust scaffold in Step 2
2026-02-20 16:47 UTC | codex | phase0-scaffold | Started Step 2 scaffold for rust/jayrah-tui mock event loop and keymap | in_progress | Create Rust workspace and initial TUI crate
2026-02-20 16:48 UTC | codex | phase0-scaffold | Created Rust workspace and initial jayrah-tui crate with Ratatui mock browse UI/event loop/keymap | complete | Build-check crate and document usage
2026-02-20 16:49 UTC | codex | phase0-scaffold | Ran cargo check for rust workspace and fixed ratatui API deprecation in table highlight style | complete | Share scaffold usage and move to Step 3 adapter wiring
2026-02-20 16:49 UTC | codex | phase0-adapter | Started Step 3 adapter wiring from rust/jayrah-tui to Python machine endpoint | in_progress | Add subprocess JSON fetch path and render real issues
2026-02-20 16:51 UTC | codex | phase0-adapter | Wired jayrah-tui reload/startup path to call `uv run jayrah cli browse-list` and parse JSON issues for rendering | complete | Validate runtime args/help and cargo checks
2026-02-20 16:51 UTC | codex | phase0-adapter | Validated rust workspace with cargo fmt/check and jayrah-tui --help smoke run | complete | Phase 0 immediate tasks baseline complete
2026-02-20 17:01 UTC | codex | phase1-detail-pane | Started Phase 1 detail pane integration using `issue-show` adapter payloads with cache/loading state | in_progress | Implement async fetch flow and verify cargo checks
2026-02-20 17:04 UTC | codex | phase1-detail-pane | Added async detail fetch worker with debounce, per-issue cache/error state, and adapter-backed issue-open action in rust TUI | complete | Validate cargo fmt/check and help output
2026-02-20 17:04 UTC | codex | phase1-detail-pane | Ran `cargo fmt --all`, `cargo check --workspace`, and `cargo run -p jayrah-tui -- --help` successfully | complete | Continue Phase 1 with selection-driven cancellation/refetch behavior and choose-mode plumbing
2026-02-20 17:10 UTC | codex | phase1-adapter-compat | Started adapter compatibility fix for board JQL `currentUser()` resolution in machine browse endpoint | in_progress | Patch mcli browse-list and add regression test
2026-02-20 17:10 UTC | codex | phase1-adapter-compat | Added `currentUser()` -> configured `jira_user` resolution for `jayrah cli browse-list` board/query execution path | complete | Run machine endpoint tests and verify myissue payload in adapter output
2026-02-20 17:10 UTC | codex | phase1-adapter-compat | Verified with `uv run pytest tests/test_mcli_machine.py -q` (4 passed) and `uv run jayrah cli browse-list myissue` (issue_count=17) | complete | Re-run rust TUI with `--board myissue` for visual confirmation
2026-02-20 17:13 UTC | codex | phase1-refactor | Started splitting rust/jayrah-tui main.rs into modular units with focused tests | in_progress | Extract app/adapter/tui modules and run cargo test
2026-02-20 17:16 UTC | codex | phase1-refactor | Split rust/jayrah-tui monolithic main.rs into modules (app, adapter, tui, worker, terminal, cli args, types, utils, mocks) with thin entrypoint | complete | Run formatting, checks, and unit tests for refactored crate
2026-02-20 17:16 UTC | codex | phase1-refactor | Verified refactor with `cargo fmt --all`, `cargo check --workspace`, `cargo test -p jayrah-tui` (9 passed) | complete | Continue Phase 1 with choose-mode wiring and selection lifecycle improvements
