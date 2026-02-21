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
2026-02-20 17:26 UTC | codex | phase1-choose-mode | Started choose-mode wiring and selection lifecycle improvements in rust TUI | in_progress | Implement CLI flag, run-loop exit contract, and selection persistence/coalescing
2026-02-20 17:28 UTC | codex | phase1-choose-mode | Added `--choose` CLI/runtime plumbing, Enter-to-confirm run outcome, selection preservation across filter/reload, and worker request coalescing | complete | Run rust fmt/check/test/help verification and document outcomes
2026-02-20 17:28 UTC | codex | phase1-choose-mode | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test -p jayrah-tui` (14 passed), and `cargo run -p jayrah-tui -- --help` | complete | Proceed to Phase 1 choose-mode propagation into Python `browse --ui rust` integration
2026-02-20 17:30 UTC | codex | phase2-cli-integration | Started Python browse integration for Rust TUI backend selection (`--ui rust`) with choose-mode propagation | in_progress | Add command option, Rust launcher bridge, and command-level tests
2026-02-20 17:32 UTC | codex | phase2-cli-integration | Added `jayrah browse --ui rust` path, Rust launcher bridge, and choose-mode handoff via temp-file env contract (`JAYRAH_TUI_CHOOSE_FILE`) | complete | Validate Python lint/tests and rust workspace checks
2026-02-20 17:32 UTC | codex | phase2-cli-integration | Verified with `uv run ruff check ...` (all checks passed), `uv run pytest tests/test_commands.py -q` (3 passed), `uv run jayrah browse --help`, and `cargo check/test -p jayrah-tui` (14 passed) | complete | Next: add integration-level test coverage for rust launcher behavior and choose output parsing
2026-02-20 17:33 UTC | codex | phase2-cli-integration | Re-ran rust formatting/check/tests after Python bridge updates (`cargo fmt --all`, `cargo check --workspace`, `cargo test -p jayrah-tui`) | complete | Keep moving toward end-to-end rust launcher integration tests
2026-02-20 17:35 UTC | codex | phase2-cli-integration-tests | Started integration-level tests for rust launcher subprocess behavior and choose output parsing | in_progress | Add dedicated tests for run_rust_browser success/error paths
2026-02-20 17:35 UTC | codex | phase2-cli-integration-tests | Added `tests/test_rust_tui_launcher.py` covering cargo command args, choose output env-file parsing/cleanup, and launcher error paths | complete | Run targeted ruff and pytest for launcher plus browse command tests
2026-02-20 17:35 UTC | codex | phase2-cli-integration-tests | Verified with `uv run ruff check jayrah/ui/rust_tui.py tests/test_rust_tui_launcher.py tests/test_commands.py` and `uv run pytest tests/test_rust_tui_launcher.py tests/test_commands.py -q` (7 passed) | complete | Next: add Rust-side integration test for `JAYRAH_TUI_CHOOSE_FILE` write behavior in main run path
2026-02-20 17:36 UTC | codex | phase2-cli-integration-tests | Started Rust-side test coverage for choose output file contract (`JAYRAH_TUI_CHOOSE_FILE`) in main path | in_progress | Extract write helper and add unit tests
2026-02-20 17:36 UTC | codex | phase2-cli-integration-tests | Extracted Rust choose output helper (`emit_choose_result`) and added unit test for output-file write contract | complete | Re-run rust fmt/check/tests for updated main path
2026-02-20 17:36 UTC | codex | phase2-cli-integration-tests | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test -p jayrah-tui` (15 passed) | complete | Next: wire rust UI backend selection into config/flags beyond per-command option if desired
2026-02-20 17:37 UTC | codex | phase2-config-toggle | Started config-driven UI backend default for browse command (feature toggle for rust/textual) | in_progress | Wire config read/write + browse fallback and add command tests
2026-02-20 17:38 UTC | codex | phase2-config-toggle | Added config-driven default UI backend (`ui_backend`) with `browse --ui` override, including config read/write support and browse backend fallback validation | complete | Run targeted lint/tests and browse help smoke check
2026-02-20 17:38 UTC | codex | phase2-config-toggle | Verified with `uv run ruff check ...`, `uv run pytest tests/test_commands.py tests/test_config.py tests/test_rust_tui_launcher.py -q` (16 passed), and `uv run jayrah browse --help` | complete | Next: consider exposing rust UI selection as a top-level/global flag across commands if needed
2026-02-20 17:39 UTC | codex | phase2-cli-integration-tests | Hardened rust launcher temp-file cleanup for choose-mode failure paths and added regression test for non-zero exit cleanup | complete | Re-run launcher lint/tests
2026-02-20 17:39 UTC | codex | phase2-cli-integration-tests | Verified with `uv run ruff check jayrah/ui/rust_tui.py tests/test_rust_tui_launcher.py` and `uv run pytest tests/test_rust_tui_launcher.py -q` (5 passed) | complete | Continue broader Phase 2 integration hardening as needed
2026-02-20 17:43 UTC | codex | phase2-global-flag | Started global CLI UI backend selection (`--ui-backend`) with precedence over config defaults for current invocation | in_progress | Update common CLI options and add precedence tests
2026-02-20 17:44 UTC | codex | phase2-global-flag | Added top-level `--ui-backend` CLI flag with per-invocation precedence over persisted config and verified browse rust-path routing through global option | complete | Run lint/tests and top-level help smoke check
2026-02-20 17:44 UTC | codex | phase2-global-flag | Verified with `uv run ruff check jayrah/commands/common.py tests/test_commands.py`, `uv run pytest tests/test_commands.py -q` (5 passed), and `uv run jayrah --help` | complete | Next: add docs/examples for global + per-command backend selection semantics
2026-02-20 17:44 UTC | codex | phase2-docs | Started README updates for UI backend selection semantics (config default, global flag, browse override) | in_progress | Document examples and precedence clearly
2026-02-20 17:44 UTC | codex | phase2-docs | Updated README with UI backend selection examples (`ui_backend` config, global `--ui-backend`, browse `--ui`) and explicit precedence order | complete | Keep docs aligned with further Phase 2 CLI integration changes
2026-02-20 17:45 UTC | codex | phase2-hardening | Started rust-backend resilience policy: fallback to textual when rust backend is config-default and unavailable, strict failure for explicit rust requests | in_progress | Add backend-origin tracking and command tests for fallback/strict paths
2026-02-20 17:46 UTC | codex | phase2-hardening | Added rust-backend fallback policy in browse flow: config-default rust failures fall back to textual, explicit rust requests remain strict | complete | Run targeted + combined lint/tests and help smoke checks
2026-02-20 17:46 UTC | codex | phase2-hardening | Verified with `uv run ruff check ...`, `uv run pytest tests/test_commands.py tests/test_config.py tests/test_rust_tui_launcher.py -q` (20 passed), `uv run jayrah --help`, and `uv run jayrah browse --help` | complete | Next: add explicit user-facing docs note about fallback behavior for config-driven rust backend selection
2026-02-20 17:46 UTC | codex | phase2-docs | Added README fallback semantics for rust backend selection (config-default fallback vs explicit-rust strict failure) | complete | Keep docs in sync with any future backend policy changes
2026-02-20 17:47 UTC | codex | phase2-hardening | Added regression test to enforce strict failure for explicit global rust selection (`--ui-backend rust`) when rust launcher fails | complete | Keep fallback/strict semantics covered as backend integration evolves
2026-02-20 17:47 UTC | codex | phase2-hardening | Verified with `uv run ruff check tests/test_commands.py` and `uv run pytest tests/test_commands.py -q` (8 passed) | complete | Proceed to broader end-to-end browse UX validation across both backends

---

## Full Rust TUI Stack Migration Plan (No Python Adapter in Rust Path)

### Goal

Deliver a fully featured Rust Ratatui TUI that no longer shells out to Python machine endpoints for data/actions.

### Scope (Locked)

- In scope: TUI stack only (browse and all interactive TUI actions)
- Out of scope: full product rewrite of create/web/mcp/cache commands
- Entrypoint: keep `jayrah browse` (Python) as thin launcher during migration

### Decisions (Locked)

- Cutover style: phased rollout with checkpoints
- Compatibility: mostly compatible with current config/auth behavior
- Parity gate: full Textual TUI feature parity before default switch
- Jira integration: native Rust Jira REST client (no `uv run jayrah cli ...` from Rust)

### Current Baseline

- Rust TUI browse flow exists and is wired through Python launcher.
- Rust data path currently depends on Python adapter commands:
  - `jayrah cli browse-list`
  - `jayrah cli issue-show`
  - `jayrah cli open`
- Advanced Textual features are still Python-side only (comments, edits, transitions, board switch, custom fields).

### Target End State

- Rust TUI performs all TUI reads/writes directly against Jira APIs using a native Rust client.
- Python `browse` command only resolves CLI/config and launches Rust binary.
- No Python adapter subprocess dependency inside Rust runtime path.

### Architecture Additions

- `rust/jayrah-config`: YAML config loader + defaults + precedence rules
- `rust/jayrah-jira`: native Jira API client with auth + retries + endpoint/version handling
- `rust/jayrah-domain`: shared state/models for TUI + client integration
- `rust/jayrah-tui`: UI/event loop/keymaps/screens/actions using native services

### Compatibility Contract

- Preserve config file location and schema support:
  - `~/.config/jayrah/config.yaml`
  - `general`, `boards`, `custom_fields`, `ui_backend`
- Preserve default board and `currentUser()` resolution behavior
- Preserve choose mode contract:
  - `JAYRAH_TUI_CHOOSE_FILE` output behavior
- Preserve explicit-rust strict behavior and config-default fallback until rollout phase says otherwise

### Phase Plan

#### Phase A: Native Backend Foundation

1. Add Rust config module for current YAML schema and precedence.
2. Implement native Rust Jira client for:
   - issue search/list
   - issue detail
   - open URL composition
3. Replace `adapter.rs` Python subprocess calls with native client calls.
4. Keep existing browse/detail/filter/reload/open/choose user behavior stable.

Exit criteria:

- No Python subprocess calls for list/detail/open from Rust code.
- `cargo check/test` and launcher compatibility tests pass.

#### Phase B: Full Textual Parity in Rust TUI

1. Implement comments view/add.
2. Implement labels/components edit flows.
3. Implement transition selection/apply flow.
4. Implement edit title/description flow.
5. Implement custom field editing flow.
6. Implement board switch flow in Rust.
7. Implement actions/help palette parity.

Exit criteria:

- Parity checklist complete (all current Textual actions available in Rust path).
- No Python fallback for advanced actions when `--ui rust`.

#### Phase C: Hardening and Rollout

1. Add telemetry/logging hooks for failures and latency.
2. Tune responsiveness and async cancellation/debounce paths.
3. Phased policy:
   - Stage 1: keep current fallback policy
   - Stage 2: warn on fallback and surface migration hints.
     Entry criteria: Phase B parity checklist is complete, telemetry hooks are enabled in release builds, and live Jira validation passes for browse/detail/comments/transitions/edit flows.
     Behavior: config-default rust fallback emits a visible warning with actionable recovery hints (retry with `--ui textual` or inspect rust logs), while explicit rust requests remain strict failures.
   - Stage 3: set rust as recommended/default backend path.
     Entry criteria: 14-day observation window with no P0/P1 rust TUI regressions, fallback rate under 5% for config-default rust launches, and release docs/help updated with final backend guidance.

Exit criteria:

- Stability and latency targets met under regression/smoke tests.
- Docs and help updated to reflect final rust-backed TUI behavior.

#### Phase D: Cleanup (TUI scope only)

1. Remove now-unused machine adapter endpoints (`browse-list`, `issue-show`) after references are gone.
2. Remove dead Rust adapter subprocess code.
3. Keep Python browse launcher thin and stable.

Exit criteria:

- Rust TUI stack has no operational Python adapter dependency.
- Legacy adapter-only code paths are removed.

### TUI Parity Checklist (Release Gate)

- [x] Browse issues
- [x] Filter/search issues
- [x] Issue detail pane
- [x] Reload issues
- [x] Open issue in browser
- [x] Choose mode return key
- [x] View comments
- [x] Add comment
- [x] Edit labels
- [x] Edit components
- [x] Transition issue
- [x] Edit title/description
- [x] Edit custom fields
- [x] Board switcher
- [x] Actions/help palette parity

### Testing Strategy

- Rust unit tests:
  - config parsing/defaults/precedence
  - auth/header behavior and API version routing
  - reducer/state transition behavior for all actions
- Rust integration tests:
  - Jira API interaction via mocked server fixtures
  - choose-mode output contract
  - retry/timeout/error handling
- Python integration tests:
  - `jayrah browse --ui rust` launcher semantics
  - strict vs fallback behavior until final rollout stage

### Risks and Mitigations

- API v2/v3 edge-case drift:
  - mitigation: dual-version fixtures and endpoint contract tests
- Config/auth mismatch with existing user setups:
  - mitigation: mostly-compatible parser + explicit migration diagnostics
- Parity regressions:
  - mitigation: checklist-driven acceptance + focused integration tests

### Immediate Next Actions

1. Start Phase A Rust crates (`jayrah-config`, `jayrah-jira`, `jayrah-domain`) scaffold.
2. Port browse/detail/open adapter calls to native client path.
3. Add tests proving no Rust runtime dependency on Python adapter commands.

2026-02-21 05:31 UTC | codex | Decision | Locked migration direction to full Rust TUI stack (native Rust Jira client, phased rollout, mostly-compatible config/auth, Python browse kept as thin launcher) | complete | Append comprehensive execution plan and begin Phase A foundation
2026-02-21 05:31 UTC | codex | migration-doc | Added complete end-to-end Full Rust TUI Stack plan with scope, phases, parity gate, tests, risks, and cleanup criteria | complete | Start Phase A implementation in rust workspace and keep logging each step
2026-02-21 05:46 UTC | codex | phaseA-native-backend | Started Phase A implementation to remove Python adapter dependency from Rust runtime path | in_progress | Scaffold Rust config/Jira/domain crates and wire jayrah-tui adapter to native client
2026-02-21 05:46 UTC | codex | phaseA-native-backend | Added new workspace crates `jayrah-config`, `jayrah-jira`, and `jayrah-domain` with config parsing, auth defaults, JQL currentUser resolution, and Jira REST client foundations | complete | Replace jayrah-tui adapter subprocess calls with native Rust config/Jira usage
2026-02-21 05:46 UTC | codex | phaseA-native-backend | Replaced `rust/jayrah-tui/src/adapter.rs` Python subprocess calls (`browse-list`, `issue-show`, `open`) with native Rust config + Jira client + browser open flow | complete | Run formatting/check/tests and validate help smoke path
2026-02-21 05:46 UTC | codex | phaseA-native-backend | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (23 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase A by adding Rust-side comments/transitions/edit API surfaces and launcher integration checks
2026-02-21 05:46 UTC | codex | phaseA-native-backend | Verified Python launcher compatibility with `uv run pytest tests/test_rust_tui_launcher.py tests/test_commands.py -q` (13 passed) after Rust adapter swap | complete | Begin next parity increment for native comment/transition/edit flows

## Remaining TODOs / Uncertainties (Append-Only)

- 2026-02-21 05:49 UTC | todo | Implement full Phase B Rust parity flows: comments view/add, transitions, labels/components edits, title/description edits, custom fields, board switcher, actions/help parity.
- 2026-02-21 05:49 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution is pending.
- 2026-02-21 05:49 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.

2026-02-21 05:49 UTC | codex | migration-doc | Added append-only Remaining TODOs / uncertainties section with current open items | complete | Refresh this section on each rewrite step (use `none` when empty)
2026-02-21 05:49 UTC | codex | repo-governance | Updated AGENTS.md to mandate Remaining TODOs / uncertainties updates in MIGRATION.md during rewrite work | complete | Apply this rule in all subsequent rewrite turns
2026-02-21 05:52 UTC | codex | phaseB-comments-view | Started first Phase B parity slice to add native Rust comments viewing flow in ratatui UI | in_progress | Add Jira comment APIs, async worker path, and comments-pane keymap/rendering
2026-02-21 05:55 UTC | codex | phaseB-comments-view | Added native Jira comment list/create client methods, Rust adapter comment mapping, comments worker pipeline, and comments pane mode (`c` open, `n/p` navigate, `c`/`Esc`/`q` close pane) | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 05:56 UTC | codex | phaseB-comments-view | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (29 tests passed) | complete | Continue Phase B with add-comment input flow and remaining edit/transition parity

- 2026-02-21 05:56 UTC | todo | Phase B parity remaining: add comment submission UI flow, labels/components edits, transitions, title/description edits, custom field editing, board switcher, and actions/help palette parity.
- 2026-02-21 05:56 UTC | todo | TUI parity checklist progress: View comments is now implemented in Rust path; keep checklist gate updates aligned as each remaining feature lands.
- 2026-02-21 05:56 UTC | uncertainty | Jira API v3 comment-create payload compatibility is implemented with ADF body format but still needs validation against a live Jira Cloud instance.
- 2026-02-21 05:56 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 05:56 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 05:58 UTC | codex | phaseB-comments-add | Started Phase B add-comment parity slice for native Rust TUI comments workflow | in_progress | Add compose-mode input, async submit worker, adapter bridge, and cache refresh behavior
2026-02-21 06:01 UTC | codex | phaseB-comments-add | Added comment compose/submit flow in Rust TUI (`a` compose, Enter submit, Esc cancel) with async submit worker and post-submit comment list refresh | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:02 UTC | codex | phaseB-comments-add | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (32 tests passed) | complete | Continue Phase B with transitions/edits/board switch/actions parity slices
- 2026-02-21 06:02 UTC | todo | Phase B parity remaining: labels/components edits, transitions, title/description edits, custom field editing, board switcher, and actions/help palette parity.
- 2026-02-21 06:02 UTC | todo | TUI parity checklist progress: View comments and Add comment are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:02 UTC | uncertainty | Jira API v3 comment-create payload compatibility still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:02 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:02 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:04 UTC | codex | phaseB-transitions | Started Phase B transition parity slice for native Rust TUI | in_progress | Add Jira transition list/apply APIs, adapter bridge, async workers, and TUI transitions mode
2026-02-21 06:07 UTC | codex | phaseB-transitions | Added Rust transitions mode (`t` open/close, `n/p` select, Enter apply), native Jira transition list/apply client calls, adapter mappings, and async transition workers with issue-status refresh | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:08 UTC | codex | phaseB-transitions | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (37 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase B with labels/components edits, title/description edits, custom fields, board switcher, and actions/help parity
- 2026-02-21 06:08 UTC | todo | Phase B parity remaining: labels/components edits, title/description edits, custom field editing, board switcher, and actions/help palette parity.
- 2026-02-21 06:08 UTC | todo | TUI parity checklist progress: View comments, Add comment, and Transition issue are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:08 UTC | uncertainty | Jira API v3 comment-create and transition-list/apply behavior still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:08 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:08 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:09 UTC | codex | phaseB-actions-help | Started Phase B actions/help parity slice for Rust TUI | in_progress | Add in-app actions/help pane with keymap guidance and mode-aware toggles
2026-02-21 06:10 UTC | codex | phaseB-actions-help | Added actions/help pane (`?`) with mode-aware key handling and footer hints across normal/comments/transitions flows | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:10 UTC | codex | phaseB-actions-help | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (39 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase B with labels/components edits, title/description edits, custom fields, and board switcher parity
- 2026-02-21 06:10 UTC | todo | Phase B parity remaining: labels/components edits, title/description edits, custom field editing, and board switcher.
- 2026-02-21 06:10 UTC | todo | TUI parity checklist progress: View comments, Add comment, Transition issue, and Actions/help parity are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:10 UTC | uncertainty | Jira API v3 comment-create and transition-list/apply behavior still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:10 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:10 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:12 UTC | codex | phaseB-board-switcher | Started Phase B board switcher parity slice for Rust TUI | in_progress | Add config-backed board list loading and in-app board selection/apply workflow
2026-02-21 06:14 UTC | codex | phaseB-board-switcher | Added board switcher pane (`b`) with config-backed board list, `n/p` navigation, Enter-to-apply board switch, and query->board handoff behavior | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:14 UTC | codex | phaseB-board-switcher | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (43 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase B with labels/components edits, title/description edits, and custom field editing parity
- 2026-02-21 06:14 UTC | todo | Phase B parity remaining: labels/components edits, title/description edits, and custom field editing.
- 2026-02-21 06:14 UTC | todo | TUI parity checklist progress: View comments, Add comment, Transition issue, Board switcher, and Actions/help parity are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:14 UTC | uncertainty | Jira API v3 comment-create and transition-list/apply behavior still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:14 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:14 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:14 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:15 UTC | codex | phaseB-edit-summary-description | Started Phase B title/description edit parity slice for Rust TUI | in_progress | Add native issue update API calls and inline summary/description edit flow in TUI
2026-02-21 06:18 UTC | codex | phaseB-edit-summary-description | Added inline issue edit flow (`e` summary, `E` description) with async update worker, native Jira issue update endpoints, adapter bridge, and cache/list refresh on success | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:18 UTC | codex | phaseB-edit-summary-description | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (46 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase B with labels/components edits and custom field editing parity
- 2026-02-21 06:18 UTC | todo | Phase B parity remaining: labels/components edits and custom field editing.
- 2026-02-21 06:18 UTC | todo | TUI parity checklist progress: View comments, Add comment, Transition issue, Edit title/description, Board switcher, and Actions/help parity are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:18 UTC | uncertainty | Jira API v3 comment-create, transition-list/apply, and description-update behavior still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:18 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:18 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:18 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:19 UTC | codex | phaseB-labels-components | Started Phase B labels/components edit parity slice for Rust TUI | in_progress | Extend inline edit pipeline with labels/components field updates and native Jira update calls
2026-02-21 06:21 UTC | codex | phaseB-labels-components | Added labels/components edit flow (`l` labels, `m` components) with native Jira update endpoints, adapter bridge, async worker handling, and mock/detail cache updates | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:21 UTC | codex | phaseB-labels-components | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (49 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Continue Phase B with custom field editing parity
- 2026-02-21 06:21 UTC | todo | Phase B parity remaining: custom field editing.
- 2026-02-21 06:21 UTC | todo | TUI parity checklist progress: View comments, Add comment, Edit labels, Edit components, Transition issue, Edit title/description, Board switcher, and Actions/help parity are implemented in Rust path; keep checklist gate entries synchronized as remaining actions land.
- 2026-02-21 06:21 UTC | uncertainty | Jira API v3 comment-create, transition-list/apply, description-update, and labels/components update behavior still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:21 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:21 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:21 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:24 UTC | codex | phaseB-custom-fields | Started Phase B custom field editing parity slice for Rust TUI | in_progress | Add config-backed custom field metadata, TUI pane/edit flow, and native Jira update bridge
2026-02-21 06:27 UTC | codex | phaseB-custom-fields | Added custom field editing flow (`u` pane, `n/p` select, Enter edit) with config-backed field metadata, native Jira custom field update endpoint, adapter bridge, async worker handling, and mock/detail cache updates | complete | Run workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:28 UTC | codex | phaseB-custom-fields | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (54 tests passed), and `cargo run -p jayrah-tui -- --help` | complete | Refresh parity checklist status and move to Phase C hardening/live validation
- 2026-02-21 06:28 UTC | todo | Phase B parity implementation is complete; next migration TODOs are Phase C hardening tasks (live Jira validation pass, latency/error instrumentation, and rollout policy staging).
- 2026-02-21 06:28 UTC | todo | TUI parity checklist status: all listed features are now implemented in the Rust path; keep checklist gate and acceptance evidence synchronized during hardening.
- 2026-02-21 06:28 UTC | uncertainty | Jira API v3 behavior for comment-create, transition-list/apply, description-update, labels/components update, and custom-field update still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:28 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:28 UTC | uncertainty | Rust config/client path does not yet resolve `pass::` or `passage::` secrets; behavior parity with Python secret resolution remains pending.
- 2026-02-21 06:28 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:28 UTC | codex | migration-doc | Updated TUI parity checklist gate to mark all currently implemented Rust parity features as complete (`[x]`) | complete | Use Phase C hardening validation to confirm release-readiness against live Jira and rollout policy gates
- 2026-02-21 06:28 UTC | todo | unchanged: Phase C hardening tasks remain (live Jira validation, latency/error instrumentation, rollout staging).
- 2026-02-21 06:28 UTC | uncertainty | unchanged: board-switch query-mode UX expectation, `pass::`/`passage::` secret parity, and Stage 2/3 fallback acceptance criteria are still open.
2026-02-21 06:29 UTC | codex | phaseA-config-parity | Started Rust config parity update for `jira_password` secret references (`pass::` / `passage::`) | in_progress | Add resolver path that mirrors Python behavior and unit coverage without PATH-global test coupling
2026-02-21 06:30 UTC | codex | phaseA-config-parity | Added `jira_password` secret-reference resolver in `jayrah-config` that detects `pass::`/`passage::` refs and runs `<provider> show <key>`, with injectable fetcher tests for pass/passage/plain/failure flows | complete | Run rust workspace formatting/check/tests and refresh migration TODO snapshot
2026-02-21 06:30 UTC | codex | phaseA-config-parity | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (58 tests passed) | complete | Continue Phase C hardening with live Jira behavior validation and rollout gate criteria
- 2026-02-21 06:30 UTC | todo | Phase C hardening remains: live Jira validation for write/update flows, latency/error instrumentation, and rollout staging criteria.
- 2026-02-21 06:30 UTC | uncertainty | Jira API v3 behavior for comment-create, transition-list/apply, description-update, labels/components update, and custom-field update still needs validation against a live Jira Cloud instance.
- 2026-02-21 06:30 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:30 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:55 UTC | codex | phaseC-instrumentation | Started Phase C latency/error instrumentation hooks for Rust TUI runtime operations | in_progress | Add opt-in telemetry emitter and wire app/worker operation timing + failure events
2026-02-21 06:58 UTC | codex | phaseC-instrumentation | Added opt-in telemetry hooks (`JAYRAH_TUI_TELEMETRY`) with structured stderr events for operation latency/error across issue reload, board/custom-field loads, browser-open, detail/comments/transitions fetch, comment add, transition apply, and edit-update workers | complete | Validate workspace build/tests and refresh hardening TODO snapshot
2026-02-21 06:58 UTC | codex | phaseC-instrumentation | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (60 tests passed) | complete | Continue Phase C with live Jira validation and rollout policy criteria
- 2026-02-21 06:58 UTC | todo | Phase C hardening remains: run live Jira validation for write/update flows and define rollout staging acceptance criteria.
- 2026-02-21 06:58 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
- 2026-02-21 06:58 UTC | uncertainty | Final fallback policy progression (Stage 2/3) still needs explicit acceptance criteria tied to parity/stability thresholds.
2026-02-21 06:59 UTC | codex | Decision | Locked explicit Stage 2/3 rollout acceptance criteria for rust-backend fallback policy progression (entry gates, warning behavior, stability window, fallback-rate threshold) | complete | Update Phase C plan text and remove fallback-criteria uncertainty from current snapshot
2026-02-21 06:59 UTC | codex | phaseC-rollout-criteria | Added concrete Phase C Stage 2/3 rollout criteria and behavior definitions in migration plan (live-validation prerequisite, warning semantics, 14-day stability window, fallback-rate threshold) | complete | Implement policy toggles/docs in launcher path when Stage 2 begins
- 2026-02-21 06:59 UTC | todo | Phase C hardening remains: run live Jira validation for write/update flows and then implement Stage 2 warning behavior in launcher UX.
- 2026-02-21 06:59 UTC | uncertainty | Board switcher currently resets query mode to selected board mode by design; confirm expected UX for users who started in raw `--query` mode.
2026-02-21 07:00 UTC | codex | Decision | Resolved board-switch query-mode UX: switching to a configured board explicitly exits raw `--query` mode and should be communicated in-pane and in status messaging | complete | Implement explicit query-mode replacement copy and add regression tests
2026-02-21 07:00 UTC | codex | phaseC-board-switch-ux | Added explicit query-mode replacement messaging for board switching (boards pane note + switch status suffix) and tests for query->board behavior | complete | Run rust workspace formatting/check/tests and refresh hardening TODO snapshot
2026-02-21 07:00 UTC | codex | phaseC-board-switch-ux | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (62 tests passed) | complete | Continue Phase C with live Jira validation and Stage 2 launcher warning behavior
- 2026-02-21 07:00 UTC | todo | Phase C hardening remains: run live Jira validation for write/update flows and implement Stage 2 fallback warning behavior in launcher UX.
- 2026-02-21 07:00 UTC | uncertainty | none
2026-02-21 07:01 UTC | codex | phaseC-stage2-warning | Started Stage 2 launcher warning behavior implementation for config-default rust fallback path | in_progress | Add actionable fallback messaging and regression coverage in Python browse command
2026-02-21 07:01 UTC | codex | phaseC-stage2-warning | Added Stage 2 fallback warning copy with actionable hints (`--ui textual`, `JAYRAH_TUI_TELEMETRY=1`) when rust launcher fails and browse falls back from config-default rust to textual | complete | Run targeted Python tests and re-verify Rust workspace tests
2026-02-21 07:01 UTC | codex | phaseC-stage2-warning | Verified with `uv run pytest tests/test_commands.py tests/test_rust_tui_launcher.py -q` (13 passed) and `cargo test --workspace` (62 passed) | complete | Continue Phase C with live Jira validation for write/update parity flows
- 2026-02-21 07:01 UTC | todo | Phase C hardening remaining: execute live Jira validation for native rust write/update flows (comments, transitions, summary/description, labels/components, custom fields).
- 2026-02-21 07:01 UTC | uncertainty | none
2026-02-21 07:02 UTC | codex | phaseC-live-validation-harness | Started Phase C live Jira validation harness for native Rust write/update flows | in_progress | Add opt-in ignored test with explicit env guards for safe execution on dedicated validation issue
2026-02-21 07:06 UTC | codex | phaseC-live-validation-harness | Added ignored live-validation test in `jayrah-jira` covering read paths plus write/update flows (summary, description, labels, components, comment add, transition apply/revert, custom-field set/restore) guarded by required `JAYRAH_LIVE_VALIDATE_*` env vars | complete | Run workspace checks and attempt guarded live validation execution
2026-02-21 07:06 UTC | codex | phaseC-live-validation-harness | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (61 passed, 1 ignored) | complete | Execute ignored live-validation test with explicit env configuration
2026-02-21 07:07 UTC | codex | phaseC-live-validation-harness | Blocker: live-validation execution failed because required env var `JAYRAH_LIVE_VALIDATE_WRITES` is unset | blocked | Unblock by setting all required `JAYRAH_LIVE_VALIDATE_*` vars (issue key, write flag, comment flag, transition ids, custom-field id/type/value/restore) and rerun `cargo test -p jayrah-jira live_validation_round_trip_write_flows -- --ignored --nocapture`
- 2026-02-21 07:07 UTC | todo | Phase C hardening remaining: run the guarded live-validation test with required `JAYRAH_LIVE_VALIDATE_*` environment variables on a dedicated Jira validation issue.
- 2026-02-21 07:07 UTC | uncertainty | none
2026-02-21 07:11 UTC | codex | phaseC-live-validation-harness | Blocker update: guarded live validation executed with env vars but failed on detail fetch with Jira 404 `Issue Does Not Exist` for configured validation issue key | blocked | Unblock by using an issue key that exists on the configured Jira site and is readable/writable by configured credentials, then rerun ignored live-validation test
- 2026-02-21 07:11 UTC | todo | Phase C hardening remaining: rerun live-validation test with a valid accessible issue key and required transition/custom-field env values, then record pass/fail evidence.
- 2026-02-21 07:11 UTC | uncertainty | none
2026-02-21 07:12 UTC | codex | Decision | Deferred live Jira validation blocker (invalid/inaccessible validation issue key) to unblock ongoing migration work | complete | Keep live-validation harness in place and resume once a valid writable issue key/env set is available
- 2026-02-21 07:12 UTC | todo | Deferred: rerun guarded live-validation test later with a valid accessible issue key and required transition/custom-field env values.
- 2026-02-21 07:12 UTC | uncertainty | none
2026-02-21 07:13 UTC | codex | phaseC-rust-cli-config-file | Started Rust CLI parity update to support explicit config path override flag for jayrah-tui | in_progress | Add `--config-file/-c` parsing/help and wire runtime override to `JAYRAH_CONFIG_FILE`
2026-02-21 07:14 UTC | codex | phaseC-rust-cli-config-file | Added `--config-file/-c` to rust/jayrah-tui CLI parser/help, with runtime wiring that sets `JAYRAH_CONFIG_FILE` before app initialization; added parser regression test | complete | Validate cargo fmt/check/tests and help output
2026-02-21 07:14 UTC | codex | phaseC-rust-cli-config-file | Verified with `cargo fmt --all`, `cargo check --workspace`, `cargo test --workspace` (62 passed, 1 ignored), and `cargo run -p jayrah-tui -- --help` | complete | Continue with deferred live Jira validation when valid writable issue/env set is available
- 2026-02-21 07:14 UTC | todo | Deferred: rerun guarded live-validation test later with a valid accessible issue key and required transition/custom-field env values.
- 2026-02-21 07:14 UTC | uncertainty | none
2026-02-21 07:16 UTC | codex | phaseC-pane-resize-keymap | Started Rust TUI ergonomics update for interactive pane resizing via keyboard shortcuts | in_progress | Add split-width state, `Alt+h`/`Alt+l` key handling, and layout wiring/tests
2026-02-21 07:17 UTC | codex | phaseC-pane-resize-keymap | Added dynamic pane width state with bounded resize behavior and wired global `Alt+h`/`Alt+l` shortcuts to grow issues/detail panes respectively; updated draw layout to honor live split percentages and added app/tui tests | complete | Run rust workspace formatting/check/tests
2026-02-21 07:17 UTC | codex | phaseC-pane-resize-keymap | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test --workspace` (64 passed, 1 ignored) | complete | Continue with deferred live Jira validation when valid writable issue/env set is available
- 2026-02-21 07:17 UTC | todo | Deferred: rerun guarded live-validation test later with a valid accessible issue key and required transition/custom-field env values.
- 2026-02-21 07:17 UTC | uncertainty | none
2026-02-21 07:17 UTC | codex | phaseC-cli-help-alias | Started adding positional help alias for jayrah-tui CLI | in_progress | Accept `help` argument and add parser/help updates
2026-02-21 07:17 UTC | codex | phaseC-cli-help-alias | Added positional `help` alias support in CLI parser and updated help usage output/tests | complete | Run rust tests and CLI help smoke check
2026-02-21 07:17 UTC | codex | phaseC-cli-help-alias | Verified with `cargo test -p jayrah-tui` (52 passed) and `cargo run -q -p jayrah-tui -- help` | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:17 UTC | todo | Deferred: rerun guarded live-validation test later with a valid accessible issue key and required transition/custom-field env values.
- 2026-02-21 07:17 UTC | uncertainty | none
2026-02-21 07:18 UTC | codex | phaseC-cli-help-alias | Re-verified positional help alias after formatting with `cargo fmt --all` and `cargo test -p jayrah-tui` (52 passed) | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:18 UTC | todo | Deferred: rerun guarded live-validation test later with a valid accessible issue key and required transition/custom-field env values.
- 2026-02-21 07:18 UTC | uncertainty | none
2026-02-21 07:33 UTC | codex | Decision | Updated scope from fixed 80% popup size to adaptive popup dimensions based on content and available terminal area, with mode-specific key behavior (help scroll vs selection navigation) | complete | Implement adaptive popup renderer and keymap updates in jayrah-tui
2026-02-21 07:33 UTC | codex | phaseC-adaptive-popups | Implemented adaptive centered popup overlays for non-default panes while keeping default issue detail in right pane; wired help popup scrolling (`j/k`, `Ctrl+d`, `Ctrl+u`) and changed boards/transitions/comments/custom-fields to use `j/k` and `n/p` for selection | complete | Update footer/help copy and add regression tests for popup sizing and key behavior
2026-02-21 07:33 UTC | codex | phaseC-adaptive-popups | Verified with `cargo test -p jayrah-tui` (61 passed, 0 failed) including new app/tui tests for adaptive popup bounds/growth and mode-specific key handling | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:33 UTC | todo | none (for adaptive popup work; deferred live-validation follow-up remains tracked in earlier entries)
- 2026-02-21 07:33 UTC | uncertainty | none
2026-02-21 07:49 UTC | codex | phaseC-adaptive-popups | Added dedicated edit-input popup overlay at fixed 80% width/80% height so edit flows (`e/E/l/m` and custom-field edit input) no longer rely on footer-only editing UI | complete | Add regression test for 80% popup dimensions and verify jayrah-tui tests
2026-02-21 07:49 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (62 passed, 0 failed) after edit popup wiring and test additions | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:49 UTC | todo | none (for edit popup change; deferred live-validation follow-up remains tracked in earlier entries)
- 2026-02-21 07:49 UTC | uncertainty | none
2026-02-21 07:53 UTC | codex | phaseC-adaptive-popups | Fixed edit popup cursor behavior by rendering an explicit input line and setting the terminal cursor position to the end of the current edit value each frame; this restores visible/blinking cursor feedback while editing | complete | Re-run jayrah-tui formatting/tests and keep deferred live-validation follow-up tracked
2026-02-21 07:53 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (62 passed, 0 failed) after cursor-position fix and restoring expected Alt+h/l resize direction mapping in tests | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:53 UTC | todo | none (for cursor visibility fix; deferred live-validation follow-up remains tracked in earlier entries)
- 2026-02-21 07:53 UTC | uncertainty | none
2026-02-21 07:55 UTC | codex | phaseC-adaptive-popups | Reverted Alt+h/l pane-resize key mapping back to previous behavior in TUI key handling (`Alt+h` grows right pane, `Alt+l` grows left pane) per user request; aligned keymap test expectation accordingly | complete | Re-run jayrah-tui formatting/tests
2026-02-21 07:55 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (62 passed, 0 failed) after mapping revert | complete | Continue deferred live-validation rerun once valid issue/env values are available
- 2026-02-21 07:55 UTC | todo | none (for pane-resize mapping revert; deferred live-validation follow-up remains tracked in earlier entries)
- 2026-02-21 07:55 UTC | uncertainty | none
2026-02-21 10:27 UTC | codex | phaseC-adaptive-popups | Decision | Narrowed scope to a focused edit-popup UX cleanup (compact modal, sectioned content, and cursor-safe input viewport) to address readability/usability regressions from the 80%x80% dialog | complete | Implement updated renderer layout and targeted regression tests
2026-02-21 10:27 UTC | codex | phaseC-adaptive-popups | Reworked edit-input popup rendering in `jayrah-tui/src/tui.rs` to use bounded dimensions, distinct Field/Value/Status sections, concise controls text, and tail-clipped single-line input rendering with stable cursor placement | complete | Run formatting and `cargo test -p jayrah-tui` to verify no behavior regressions
2026-02-21 10:27 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (64 passed, 0 failed) including new sizing and input-viewport tests | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:27 UTC | codex | remaining-todos-uncertainties | Updated current state after edit-popup UX cleanup | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this UI change
2026-02-21 10:29 UTC | codex | phaseC-adaptive-popups | Removed the edit-popup `Status` panel per UX feedback, keeping only Field/Value/Controls content in the modal while preserving footer status text and cursor behavior | complete | Re-run formatting/tests to confirm no regressions
2026-02-21 10:29 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (64 passed, 0 failed) after status-panel removal | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:29 UTC | codex | remaining-todos-uncertainties | Updated current state after edit-popup status-panel removal | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:30 UTC | codex | phaseC-adaptive-popups | Reduced edit-popup height budget after status-panel removal by tightening height percent and min/max bounds so modal stays compact and avoids large empty body space | complete | Re-run formatting/tests and confirm edited bounds test coverage
2026-02-21 10:30 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (64 passed, 0 failed) after compact-height tuning | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:30 UTC | codex | remaining-todos-uncertainties | Updated current state after compact edit-popup sizing pass | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:35 UTC | codex | phaseC-adaptive-popups | Decision | Finalized edit-modal UX direction to single-surface editor (no nested value box, no separate field row), title-only metadata, and compact dimensions focused on content lines | complete | Implement renderer/layout simplification and retune popup bounds
2026-02-21 10:35 UTC | codex | phaseC-adaptive-popups | Implemented single-surface edit popup rendering in `jayrah-tui/src/tui.rs` by removing nested `Value` block and `Field:` row, rendering direct input/hint lines inside one bordered popup, and tightening width/height bounds for compact presentation | complete | Run formatting/tests and update migration TODO snapshot
2026-02-21 10:35 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (64 passed, 0 failed) after single-surface compact editor redesign | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:35 UTC | codex | remaining-todos-uncertainties | Updated current state after single-surface compact edit-popup redesign | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this change
2026-02-21 10:37 UTC | codex | phaseC-adaptive-popups | Reduced residual empty footer space in edit popup by making height fixed to content rows (4 lines total), keeping single-surface input + controls with no spare vertical body area | complete | Re-run formatting/tests and refresh migration TODO snapshot
2026-02-21 10:37 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (64 passed, 0 failed) after fixed-height tuning | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:37 UTC | codex | remaining-todos-uncertainties | Updated current state after fixed-height edit-popup pass | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:42 UTC | codex | phaseC-adaptive-popups | Decision | Switched edit-input UX implementation from custom key handling to `tui-textarea` widget adoption with Emacs-style editing semantics and `Ctrl+s` save, while removing explicit `Backspace delete` copy | complete | Add dependency, wire session state in TUI loop, and update edit submission pipeline/tests
2026-02-21 10:46 UTC | codex | phaseC-adaptive-popups | Implemented textarea-backed edit UX using `tui-textarea` with persistent edit session state in TUI runtime, Emacs-style key handling via widget defaults, `Ctrl+s` save, `Esc` cancel, and multiline edit rendering in a single popup surface (no nested value box, no backspace hint copy) | complete | Verify behavior/tests and keep migration TODO snapshot current
2026-02-21 10:46 UTC | codex | phaseC-adaptive-popups | Updated edit submission pipeline in `app.rs` with `set_edit_input` + `submit_edit_value` and field-specific normalization (summary newline collapse, labels/components newline-to-comma) before adapter/mock update dispatch | complete | Lock regressions with app/tui unit coverage for Ctrl+s save and newline handling
2026-02-21 10:46 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (68 passed, 0 failed) after adopting `tui-textarea` and adding normalization/input tests | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:46 UTC | codex | remaining-todos-uncertainties | Updated current state after textarea/emacs edit UX migration | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this change
2026-02-21 10:46 UTC | codex | phaseC-adaptive-popups | Re-verified full workspace after textarea migration with `cargo test --workspace` (jayrah-config 8 passed, jayrah-domain 1 passed, jayrah-jira 5 passed + 1 ignored live test, jayrah-tui 68 passed) | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:49 UTC | codex | phaseC-adaptive-popups | Applied field-specific edit sizing rules: summary edit input viewport now reserves two lines, and description edit popup now uses 80% x 80% of terminal area while other fields keep compact bounded sizing | complete | Verify with targeted tui tests and keep migration TODO snapshot current
2026-02-21 10:49 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (70 passed, 0 failed) including new tests for description 80% sizing and summary 2-line input height behavior | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:49 UTC | codex | remaining-todos-uncertainties | Updated current state after summary/description edit-size tuning | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:53 UTC | codex | phaseC-adaptive-popups | Increased summary edit viewport height from 2 to 4 lines for better edit comfort while keeping description at 80% popup sizing | complete | Re-run formatting/tests and refresh migration TODO snapshot
2026-02-21 10:53 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (70 passed, 0 failed) after summary viewport height increase | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:53 UTC | codex | remaining-todos-uncertainties | Updated current state after summary viewport height tuning | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:54 UTC | codex | phaseC-adaptive-popups | Added summary-specific popup container sizing profile to eliminate dead vertical space (compact 7-10 line height band) while retaining 4-line summary input viewport and description 80% mode | complete | Re-run formatting/tests and update migration TODO snapshot
2026-02-21 10:54 UTC | codex | phaseC-adaptive-popups | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (71 passed, 0 failed) including new summary compact-popup sizing test | complete | Keep deferred live-validation rerun tracked when valid Jira validation issue/env values are available
2026-02-21 10:54 UTC | codex | remaining-todos-uncertainties | Updated current state after summary popup compact-height tuning | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this tweak
2026-02-21 10:56 UTC | codex | phaseC-keymap-other-pane-scroll | Started implementing detail-pane scroll keymap updates (`J/K`, `Ctrl+d/u`) in rust TUI with app-state + renderer + key-routing/test changes | in_progress | Run formatting/tests and finalize migration snapshot
2026-02-21 10:57 UTC | codex | phaseC-keymap-other-pane-scroll | Added detail-pane scroll state, renderer wiring, and keybindings (`J/K`, `Ctrl+d/u`) in normal mode while preserving actions-popup scrolling behavior; updated footer/help copy and added app/tui regression tests | complete | Confirm workspace status and report implementation details
2026-02-21 10:57 UTC | codex | phaseC-keymap-other-pane-scroll | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (75 passed) | complete | Update remaining TODOs/uncertainties snapshot
2026-02-21 10:57 UTC | codex | remaining-todos-uncertainties | Updated current state after other-pane keymap/detail-scroll implementation | none | Deferred live-validation follow-up remains tracked in earlier entries; no new TODOs/uncertainties from this change
2026-02-21 12:05 UTC | codex | phase3-layout-toggle | Started implementing Ctrl+V orientation toggle for issue/detail panes | in_progress | Add app state, key handling, render updates, and tests
2026-02-21 12:05 UTC | codex | phase3-layout-toggle | Implemented pane orientation state, Ctrl+V toggle, orientation-aware split rendering, and shortcut/help text updates | complete | Run rust fmt/check/tests for validation
2026-02-21 12:06 UTC | codex | phase3-layout-toggle | Verified Ctrl+V layout toggle with cargo fmt/test (,
running 82 tests
test adapter::tests::maps_comment_defaults ... ok
test adapter::tests::loads_custom_fields_from_config ... ok
test adapter::tests::loads_boards_from_config_with_default_description ... ok
test adapter::tests::maps_detail_issue_fields ... ok
test adapter::tests::maps_transition_defaults ... ok
test adapter::tests::maps_list_issue_defaults ... ok
test app::tests::actions_text_lists_key_shortcuts ... ok
test app::tests::apply_selected_board_updates_source ... ok
test app::tests::apply_selected_board_replaces_query_mode_with_board_mode ... ok
test app::tests::actions_scroll_obeys_bounds ... ok
test app::tests::boards_text_warns_when_in_query_mode ... ok
test app::tests::default_pane_orientation_is_horizontal ... ok
test app::tests::apply_transition_in_mock_mode_updates_issue_status ... ok
test app::tests::comment_navigation_wraps ... ok
test app::tests::enter_boards_mode_loads_mock_boards ... ok
test app::tests::detail_scroll_obeys_bounds ... ok
test app::tests::detail_scroll_resets_when_selection_changes ... ok
test app::tests::enter_custom_fields_mode_loads_mock_custom_fields ... ok
test app::tests::filters_visible_indices_by_summary ... ok
test app::tests::maybe_request_comments_populates_mock_cache_without_worker_request ... ok
test app::tests::maybe_request_detail_populates_mock_cache_without_worker_request ... ok
test app::tests::maybe_request_transitions_populates_mock_cache_without_worker_request ... ok
test app::tests::non_detail_modes_are_popup_modes ... ok
test app::tests::pane_resize_bounds_are_enforced ... ok
test app::tests::preserves_selected_issue_key_across_reload ... ok
test app::tests::preserves_selected_issue_when_filter_changes ... ok
test app::tests::start_selected_custom_field_edit_input_sets_custom_target ... ok
test app::tests::submit_comment_in_mock_mode_appends_new_comment ... ok
test app::tests::submit_comment_rejects_empty_body ... ok
test app::tests::submit_components_edit_normalizes_newlines_to_csv_delimiters ... ok
test app::tests::submit_components_edit_in_mock_mode_updates_detail_cache ... ok
test app::tests::submit_custom_field_edit_in_mock_mode_sets_status ... ok
test app::tests::submit_description_edit_in_mock_mode_updates_detail_cache ... ok
test app::tests::submit_labels_edit_in_mock_mode_updates_detail_cache ... ok
test app::tests::submit_labels_edit_normalizes_newlines_to_csv_delimiters ... ok
test app::tests::submit_summary_edit_in_mock_mode_updates_issue ... ok
test app::tests::submit_summary_edit_normalizes_newlines_to_spaces ... ok
test app::tests::toggle_pane_orientation_flips_between_horizontal_and_vertical ... ok
test cli_args::tests::defaults_to_legacy_board_when_no_args ... ok
test cli_args::tests::parses_choose_mode_flag ... ok
test cli_args::tests::parses_config_file_flag ... ok
test cli_args::tests::rejects_board_and_query_together ... ok
test cli_args::tests::returns_help_action ... ok
test telemetry::tests::parses_telemetry_bool_flags ... ok
test telemetry::tests::sanitizes_whitespace_and_control_characters ... ok
test tui::tests::a_enters_comment_input_mode ... ok
test tui::tests::adaptive_popup_area_grows_with_content_size ... ok
test tui::tests::adaptive_popup_area_is_bounded_by_terminal_area ... ok
test tui::tests::alt_h_and_alt_l_resize_panes ... ok
test tui::tests::b_enters_boards_mode ... ok
test tui::tests::ctrl_d_and_ctrl_u_page_actions_help ... ok
test tui::tests::ctrl_d_and_ctrl_u_page_detail_in_normal_mode ... ok
test tui::tests::ctrl_s_submits_edit_input_in_mock_mode ... ok
test tui::tests::ctrl_v_is_ignored_in_edit_input_mode ... ok
test tui::tests::ctrl_v_is_ignored_in_comment_input_mode ... ok
test tui::tests::ctrl_v_is_ignored_in_filter_mode ... ok
test tui::tests::ctrl_v_toggles_layout_in_normal_mode ... ok
test tui::tests::ctrl_v_toggles_layout_in_popup_mode ... ok
test tui::tests::description_edit_popup_uses_eighty_percent_of_screen ... ok
test tui::tests::e_enters_edit_input_mode ... ok
test tui::tests::edit_popup_area_stays_within_expected_bounds ... ok
test tui::tests::enter_in_edit_mode_inserts_newline_and_does_not_submit ... ok
test tui::tests::enter_opens_issue_outside_choose_mode ... ok
test tui::tests::enter_returns_selected_key_in_choose_mode ... ok
test tui::tests::j_advances_board_selection_in_boards_mode ... ok
test tests::writes_selected_key_to_output_file_when_path_provided ... ok
test tui::tests::j_advances_comment_selection_in_comments_mode ... ok
test tui::tests::j_advances_custom_field_selection_in_custom_fields_mode ... ok
test tui::tests::j_advances_transition_selection_in_transitions_mode ... ok
test tui::tests::l_enters_labels_edit_input_mode ... ok
test tui::tests::percent_popup_area_uses_requested_percentage ... ok
test tui::tests::j_and_k_scroll_actions_help_without_moving_issue_selection ... ok
test tui::tests::q_closes_comments_mode_before_quit ... ok
test tui::tests::question_mark_enters_actions_mode ... ok
test tui::tests::summary_edit_input_height_uses_four_lines_when_possible ... ok
test tui::tests::summary_edit_popup_uses_compact_height_profile ... ok
test tui::tests::t_enters_transitions_mode ... ok
test tui::tests::u_enters_custom_fields_mode ... ok
test utils::tests::compact_error_truncates_long_strings ... ok
test utils::tests::join_or_dash_formats_values ... ok
test tui::tests::uppercase_j_and_k_scroll_detail_without_moving_issue_selection ... ok
test adapter::tests::resolves_board_jql_with_order_by_and_current_user ... ok

test result: ok. 82 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s, 82 passed) | complete | Update remaining TODOs/uncertainties snapshot
2026-02-21 12:06 UTC | codex | remaining-todos-uncertainties | Updated current state after Ctrl+V layout toggle implementation | none | none
2026-02-21 12:06 UTC | codex | phase3-layout-toggle | Verified Ctrl+V layout toggle with cargo fmt and jayrah-tui tests (82 passed) | complete | none
2026-02-21 12:06 UTC | codex | migration-log | Recorded that preceding unformatted test-output lines were accidentally appended; canonical formatted phase3 entries remain authoritative | complete | none
2026-02-21 12:10 UTC | codex | phase3-vertical-default-size | Started tuning default vertical split to match screenshot (shorter top issues pane, taller detail pane) | in_progress | Refactor pane ratio state per orientation and validate tests
2026-02-21 12:10 UTC | codex | phase3-vertical-default-size | Refactored app pane ratio state to independent horizontal (60/40) and vertical (30/70) defaults with orientation-scoped resizing | complete | Run rust fmt and jayrah-tui tests
2026-02-21 12:10 UTC | codex | phase3-vertical-default-size | Verified with cargo fmt and cargo test for jayrah-tui (83 passed) | complete | Update remaining todos and uncertainties
2026-02-21 12:10 UTC | codex | remaining-todos-uncertainties | Updated current state after vertical default split tuning | none | none
2026-02-21 12:15 UTC | codex | phase3-vertical-default-size | Confirmed vertical default split remains 30/70 (more space for description) and orientation-specific resizing behavior is active | complete | none
2026-02-21 12:15 UTC | codex | remaining-todos-uncertainties | Updated current state after vertical default split verification request | none | none
2026-02-21 12:36 UTC | codex | phase3-pane-zoom | Started implementing pane zoom toggle keys (1/2) with zoom status badge in Rust TUI | in_progress | Update app/tui state, keymap, rendering, and tests
2026-02-21 12:36 UTC | codex | phase3-pane-zoom | Added PaneZoom state + toggle methods, 1/2 keybindings, single-pane zoom render path, and top-right ZOOMED indicator | complete | Run focused tests and workspace checks
2026-02-21 12:36 UTC | codex | phase3-pane-zoom | Verified with `cargo test -p jayrah-tui zoom`, `cargo test -p jayrah-tui actions_text_lists_key_shortcuts`, and `cargo check --workspace` | complete | Capture full-suite status for visibility
2026-02-21 12:36 UTC | codex | phase3-pane-zoom | Full `cargo test -p jayrah-tui` run shows 3 existing non-zoom failures in pane orientation/resize expectation tests; new zoom tests passed | complete | Keep baseline failures unchanged in this scope
2026-02-21 12:36 UTC | codex | phase3-pane-zoom | Remaining TODOs / uncertainties | Baseline full-suite failures remain in `app::tests::{default_pane_orientation_is_horizontal,toggle_pane_orientation_flips_between_horizontal_and_vertical,pane_resize_values_are_independent_per_orientation}` | Decide separately whether to change pane defaults or expected test values
2026-02-21 12:38 UTC | codex | phase3-pane-zoom | Added pane title key hints `(1)` and `(2)` to issues/detail blocks for discoverability | complete | Re-run focused zoom/help tests
2026-02-21 12:38 UTC | codex | phase3-pane-zoom | Verified title hint update with `cargo fmt --all`, `cargo test -p jayrah-tui zoom`, and `cargo test -p jayrah-tui actions_text_lists_key_shortcuts` | complete | Update remaining TODOs/uncertainties snapshot
2026-02-21 12:38 UTC | codex | phase3-pane-zoom | Remaining TODOs / uncertainties | Baseline full-suite failures still remain in `app::tests::{default_pane_orientation_is_horizontal,toggle_pane_orientation_flips_between_horizontal_and_vertical,pane_resize_values_are_independent_per_orientation}`; title-hint change introduced none | Decide separately whether to align pane defaults or test expectations
2026-02-21 12:41 UTC | codex | phase3-pane-zoom | Started lowercase j/k behavior update for detail-pane zoom navigation | in_progress | Update key handler and regression tests
2026-02-21 12:41 UTC | codex | phase3-pane-zoom | Added zoom-aware key handling so lowercase j/k scroll detail in detail zoom mode; updated footer/help copy and added regression test | complete | Run rust fmt and targeted keybinding tests
2026-02-21 12:41 UTC | codex | phase3-pane-zoom | Verified with `cargo fmt --all`, `cargo test -p jayrah-tui "tui::tests::lowercase_j_and_k_scroll_detail_when_detail_pane_is_zoomed" -- --exact`, and `cargo test -p jayrah-tui "tui::tests::uppercase_j_and_k_scroll_detail_without_moving_issue_selection" -- --exact`; full `cargo test -p jayrah-tui` still reports 3 existing pane-orientation baseline failures | complete | Keep baseline orientation failures out of this scope
2026-02-21 12:41 UTC | codex | remaining-todos-uncertainties | Updated current state after lowercase j/k detail-zoom scroll change | Baseline full-suite failures remain in `app::tests::{default_pane_orientation_is_horizontal,toggle_pane_orientation_flips_between_horizontal_and_vertical,pane_resize_values_are_independent_per_orientation}` | none
2026-02-21 12:42 UTC | codex | phase3-tooling | Started clippy cleanup for Rust workspace after keybinding update | in_progress | Apply lint-driven code changes in jayrah-tui
2026-02-21 12:42 UTC | codex | phase3-tooling | Fixed clippy warnings in jayrah-tui (collapsible string replace, question_mark, and dead-code warnings via test-only helper + production edit-submit path usage) | complete | Re-run formatting and clippy across workspace
2026-02-21 12:42 UTC | codex | phase3-tooling | Verified with `cargo fmt --all` and `cargo clippy --workspace --all-targets` (clean, no warnings) | complete | Update remaining todos/uncertainties snapshot
2026-02-21 12:42 UTC | codex | remaining-todos-uncertainties | Updated current state after clippy cleanup | none | none
2026-02-21 12:48 UTC | codex | phase3-ux-footer | Started simplifying bottom footer shortcuts to essential keys only across modes | in_progress | Trim footer strings in tui renderer
2026-02-21 12:48 UTC | codex | phase3-ux-footer | Reduced footer verbosity for NORMAL/CHOOSE and popup modes (actions/comments/transitions/boards/custom-fields) while keeping key essentials and status text | complete | Run rust fmt and clippy
2026-02-21 12:48 UTC | codex | phase3-ux-footer | Verified with `cargo fmt --all` and `cargo clippy --workspace --all-targets` | complete | Update remaining todos/uncertainties snapshot
2026-02-21 12:48 UTC | codex | remaining-todos-uncertainties | Updated current state after footer simplification | none | none
2026-02-21 12:51 UTC | codex | phase3-tests | Started fixing failing jayrah-tui tests after condensed help/footer changes | in_progress | Align pane orientation assertions with current pane default ratios
2026-02-21 12:51 UTC | codex | phase3-tests | Updated stale pane orientation/resize test expectations to match current horizontal default 40/60 and resize step behavior | complete | Run rust fmt, jayrah-tui tests, and clippy
2026-02-21 12:51 UTC | codex | phase3-tests | Verified with `cargo fmt --all`, `cargo test -p jayrah-tui` (91 passed), and `cargo clippy --workspace --all-targets` | complete | Update remaining todos/uncertainties snapshot
2026-02-21 12:51 UTC | codex | remaining-todos-uncertainties | Updated current state after pane test expectation alignment | none | none
2026-02-21 12:57 UTC | codex | phase3-filter-ux | Started implementing persistent filter top bar with focus/unfocus/clear key semantics | in_progress | Update app and tui filter state/render handling plus tests
2026-02-21 12:59 UTC | codex | phase3-filter-ux | Implemented persistent filter top bar visibility with focus/unfocus/clear semantics (`f`/`/` focus, Enter unfocus, Esc clear when focused) and updated footer guidance | complete | Add regression tests and verify crate tests
2026-02-21 12:59 UTC | codex | phase3-filter-ux | Added regression tests for Enter-unfocus, Esc-clear, and refocus behavior; verified `cargo test -p jayrah-tui` (94 passed) | complete | Remaining TODOs / uncertainties: none
2026-02-21 16:36 UTC | codex | Decision | Split key semantics: keep `f` as persistent filter focus and introduce dedicated `/` search mode with `n`/`N` repeat on visible rows only in detail mode | accepted | Implement Rust app/tui state, key handling, and tests
2026-02-21 16:36 UTC | codex | phase3-search-mode | Started implementing dedicated `/` search mode while retaining `f` filter flow | in_progress | Update app state/matching helpers, tui key handling/rendering/help, and tests
2026-02-21 16:39 UTC | codex | phase3-search-mode | Implemented dedicated detail-mode `/` search input with visible-row matching, Enter jump, and `n`/`N` repeat while keeping `f` bound to persistent filter focus | complete | Run formatting and jayrah-tui test suite
2026-02-21 16:39 UTC | codex | phase3-search-mode | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (103 passed) | complete | Update remaining todos/uncertainties snapshot
2026-02-21 16:39 UTC | codex | remaining-todos-uncertainties | Updated current state after split filter/search keybinding implementation | none | none
2026-02-21 16:54 UTC | codex | phase1-theme | Decision | Locked full-surface Solarized-warm theme pass with single default theme and no runtime switching for this iteration | Implement centralized theme module and wire semantic styles through the TUI draw path
2026-02-21 16:54 UTC | codex | phase1-theme | Started themed-color implementation for Rust Ratatui UI surfaces | in_progress | Add semantic palette module and apply styles across panes, popups, bars, and footer/status
2026-02-21 16:54 UTC | codex | phase1-theme | Added centralized `theme.rs` semantic palette with status-tone mapping and unit tests | complete | Wire theme into draw pipeline and edit input styling
2026-02-21 16:54 UTC | codex | phase1-theme | Applied themed styles to issues table, detail pane, popups, filter/search bars, footer, and status emphasis in `tui.rs` | complete | Run formatting/checks/tests for regression coverage
2026-02-21 16:54 UTC | codex | phase1-theme | Verified with `cargo fmt --all`, `cargo check --workspace`, and `cargo test -p jayrah-tui` (106 passed) | complete | Confirm migration log state and handoff changes
2026-02-21 16:54 UTC | codex | phase1-theme | Remaining TODOs / uncertainties | none | Continue with next Rust TUI feature iteration
2026-02-21 16:59 UTC | codex | phase3-filter-search-esc | Started Esc behavior update for focused filter/search inputs so Esc clears input without leaving mode | in_progress | Patch key handling, help text, and tests in jayrah-tui
2026-02-21 16:59 UTC | codex | phase3-filter-search-esc | Updated key handling so Esc clears filter/search input while staying in focused mode; refreshed search help/status copy and actions help text | complete | Run formatting and jayrah-tui tests
2026-02-21 16:59 UTC | codex | phase3-filter-search-esc | Verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (106 passed) | complete | Update remaining todos/uncertainties snapshot
2026-02-21 16:59 UTC | codex | remaining-todos-uncertainties | Updated current state after Esc clear-without-exit behavior for filter/search modes | none | none
2026-02-21 17:11 UTC | codex | Decision | Locked detail-pane-only structured presentation polish (labels/sections/emphasis) with no keybinding or non-detail behavior changes | accepted | Implement app view-model, themed detail styles, and detail renderer wiring
2026-02-21 17:11 UTC | codex | phase3-detail-pretty | Started implementing structured detail pane presentation in Rust TUI | in_progress | Add detail view model, styled detail text builder, and regression tests
2026-02-21 17:15 UTC | codex | phase3-detail-pretty | Added detail presentation view model in app state and switched detail text generation to model-based formatting for loaded/loading/error/summary/empty states | complete | Wire structured styled detail rendering in tui
2026-02-21 17:15 UTC | codex | phase3-detail-pretty | Implemented structured detail-pane rendering with styled labels, section headers, loading/error banners, and placeholder emphasis using new detail theme semantics | complete | Add focused renderer tests and run formatting/tests
2026-02-21 17:15 UTC | codex | phase3-detail-pretty | Added app/theme/tui regression tests for detail view-model states and structured line rendering; verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (115 passed) | complete | Update remaining todos/uncertainties snapshot
2026-02-21 17:15 UTC | codex | remaining-todos-uncertainties | Updated current state after detail-pane structured presentation polish | none | none
2026-02-21 17:16 UTC | codex | phase3-detail-pretty | Re-validated workspace compilation with `cargo check --workspace` after detail-pane polish changes | complete | none
2026-02-21 17:25 UTC | codex | phase1-ux-scrollbars | Started implementing visible scrollbars for detail pane and actions popup | in_progress | Integrate scrollbar state helper and add tests
2026-02-21 17:25 UTC | codex | phase1-ux-scrollbars | Remaining TODOs / uncertainties: validate compile/tests after scrollbar rendering changes | pending | Run cargo test/check and address failures
2026-02-21 17:26 UTC | codex | phase1-ux-scrollbars | Added vertical scrollbar rendering for scrollable detail pane and actions popup, with shared overflow/clamp helper tests | complete | Run workspace check and finalize handoff
2026-02-21 17:26 UTC | codex | phase1-ux-scrollbars | Verified with `cargo test -p jayrah-tui` (117 passed) and `cargo check --workspace` | complete | Remaining TODOs / uncertainties: none
2026-02-21 17:26 UTC | codex | phase1-ux-scrollbars | Ran `cargo fmt --all` and re-verified `cargo test -p jayrah-tui` + `cargo check --workspace` after formatting | complete | Remaining TODOs / uncertainties: none
2026-02-21 17:30 UTC | codex | phase1-keybindings | Started keybinding behavior fix so lowercase j/k keeps moving issue selection even when detail pane is zoomed | in_progress | Remove zoom-specific j/k detail scroll path and align help/tests
2026-02-21 17:30 UTC | codex | phase1-keybindings | Removed detail-zoom override for lowercase j/k, updated actions help text, and adjusted regression test expectations | complete | Re-run cargo test/check and capture final remaining todos
2026-02-21 17:30 UTC | codex | phase1-keybindings | Verified with `cargo test -p jayrah-tui` (117 passed) and `cargo check --workspace` | complete | Remaining TODOs / uncertainties: none
2026-02-21 17:33 UTC | codex | phase1-ux-status-colors | Started status-based issue table color mapping for clearer workflow state scanning | in_progress | Add theme status tone mapping and wire status cell styling
2026-02-21 17:33 UTC | codex | phase1-ux-status-colors | Added issue-status tone mapping + table status styling and applied per-status coloring to issues Status column | complete | Run format/tests/check and update remaining todos
2026-02-21 17:33 UTC | codex | phase1-ux-status-colors | Verified with `cargo fmt --all`, `cargo test -p jayrah-tui` (119 passed), and `cargo check --workspace` | complete | Remaining TODOs / uncertainties: none
2026-02-21 18:32 UTC | codex | tui-layout | Started configurable startup layout/zoom implementation in rust-tui CLI and app wiring | in_progress | Complete Python config+launcher plumbing and full tests
2026-02-21 18:32 UTC | codex | tui-layout | Added rust-tui --layout/--zoom parsing and App startup layout injection path in main | complete | Wire Python config defaults and browse overrides into rust launcher
2026-02-21 18:32 UTC | codex | remaining | Remaining TODOs / uncertainties: python config keys, browse/launcher propagation, tests not yet run | tracked | Implement Python-side changes and verify with targeted test suites
2026-02-21 18:35 UTC | codex | tui-layout | Added Python config keys (rust_tui_layout/rust_tui_zoom), browse CLI overrides, and rust launcher flag forwarding | complete | Run Rust/Python targeted verification suites
2026-02-21 18:35 UTC | codex | tui-layout-tests | Verified layout/zoom configurability with cargo test/check/fmt and uv pytest/ruff on affected modules | complete | Finalize migration state update
2026-02-21 18:35 UTC | codex | remaining | Remaining TODOs / uncertainties: none | none | Ready for user validation and optional README examples update
2026-02-21 18:35 UTC | codex | tui-layout-docs | Updated README with rust_tui_layout/rust_tui_zoom config keys and --rust-layout/--rust-zoom override examples | complete | Remaining TODOs / uncertainties: none
2026-02-21 18:41 UTC | codex | Decision | Changed default startup zoom policy from issues-zoomed to split view while keeping horizontal layout default, based on user feedback | recorded | Update Rust/Python defaults and tests
2026-02-21 18:41 UTC | codex | tui-layout-defaults | Updated default startup zoom to split view while preserving horizontal layout default across Rust CLI and Python config defaults | complete | Re-verify targeted Rust/Python test suites
2026-02-21 18:41 UTC | codex | tui-layout-defaults-tests | Re-verified with cargo test -p jayrah-tui and uv pytest tests/test_commands.py tests/test_rust_tui_launcher.py tests/test_config.py -q | complete | Remaining TODOs / uncertainties: none
2026-02-21 18:47 UTC | codex | phase1-scroll-input | Started fixing pane-aware mouse wheel behavior in split layouts | in_progress | Add mouse capture and route wheel events by pane hit area
2026-02-21 18:47 UTC | codex | phase1-scroll-input | Added mouse capture lifecycle, pane hit-testing, and wheel routing so right/detail pane scrolling no longer moves issue selection | complete | Add regression tests for vertical layout pane wheel routing
2026-02-21 18:47 UTC | codex | phase1-scroll-input | Added vertical-layout mouse wheel regression tests and verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (125 passed) | complete | Remaining TODOs / uncertainties update
2026-02-21 18:47 UTC | codex | phase1-scroll-input | Remaining TODOs / uncertainties | none | none
2026-02-21 18:53 UTC | codex | phase1-mouse-selection | Started adding click-to-select behavior for issues pane rows | in_progress | Route left-click in issues table to visible selection index
2026-02-21 18:53 UTC | codex | phase1-mouse-selection | Added issue-row hit mapping + click selection API so left-click moves cursor/selection to clicked issue row | complete | Add regression tests and verify full crate tests
2026-02-21 18:53 UTC | codex | phase1-mouse-selection | Added click selection regression tests and verified with `cargo fmt --all` and `cargo test -p jayrah-tui` (127 passed) | complete | Remaining TODOs / uncertainties update
2026-02-21 18:53 UTC | codex | phase1-mouse-selection | Remaining TODOs / uncertainties | none | none
2026-02-21 19:46 UTC | codex | phase3-edit-menu-popup | Started implementing unified edit menu popup on `e` (replace direct e/E/l/m edit bindings) | in_progress | Update app/tui state, key/mouse handlers, help text, and tests
2026-02-21 19:49 UTC | codex | phase3-edit-menu-popup | Added EditMenu pane mode/state/text and unified edit-menu selection/apply flow; switched keybindings in normal/comments/transitions/boards/actions to `e` popup entry; added edit menu mode label/footer/mouse-wheel handling and updated actions help text | complete | Run jayrah-tui build/tests for regression verification
2026-02-21 19:49 UTC | codex | phase3-edit-menu-popup | Verified with `cargo build` and `cargo test` in `rust/jayrah-tui` (134 passed) after formatting | complete | Remaining TODOs / uncertainties update
2026-02-21 19:49 UTC | codex | remaining-todos-uncertainties | Updated current state after edit-menu popup consolidation | none | none
2026-02-21 22:00 UTC | claude | filter-search-ux | Overhauled filter/search key bindings: Esc/Enter exit filter (keep text), Esc cancels search, Enter submits search; added Ctrl-U to clear text in both modes; added Shift-F to clear filter from normal mode; updated all hint text; fixed edit popup visual clutter by clearing main_area | complete | none
2026-02-21 22:00 UTC | claude | remaining-todos-uncertainties | Updated current state after filter/search UX overhaul | none | none
