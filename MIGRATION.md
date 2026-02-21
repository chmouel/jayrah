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
   - Stage 2: warn on fallback and surface migration hints
   - Stage 3: set rust as recommended/default backend path

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
- [ ] Browse issues
- [ ] Filter/search issues
- [ ] Issue detail pane
- [ ] Reload issues
- [ ] Open issue in browser
- [ ] Choose mode return key
- [ ] View comments
- [ ] Add comment
- [ ] Edit labels
- [ ] Edit components
- [ ] Transition issue
- [ ] Edit title/description
- [ ] Edit custom fields
- [ ] Board switcher
- [ ] Actions/help palette parity

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
