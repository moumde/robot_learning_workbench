# v1 Stabilization Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in the existing shared workspace. Preserve P0–P8 changes; no commits, tags, publishing or hardware operation.

**Goal:** Complete P9's code and documentation preparation for v1.0, leaving physical release acceptance explicit.

**Architecture:** Keep one production HMI and the existing Motion / Trajectory / Recording boundaries. Reduce the application runtime by extracting cohesive services; retain actively configured alternative master adapters with documented support, rather than deleting working device support by filename.

**Tech Stack:** Python 3.12, PySide6, NumPy, pytest, Ruff, independent dataset workers.

**Spec:** User-provided P9 “Legacy Removal, Stabilization and v1.0 Release Preparation”.

## Global Constraints

- Offline startup; motion requires explicit user commands.
- Preserve calibration, HOME poses, existing recordings and legacy trajectory input files.
- No invented joint or workspace limits. No file-hash or smoke-test infrastructure.
- Reversible refactoring in the current workspace is authorized by the user's continuous implementation request.

## Review Focus

- Shutdown while sampling: stop sampling before releasing feedback devices; retain pending data.
- STOP racing replay completion: completion workers must be owned and drained without lock inversion.
- Camera discovery during shutdown: bounded join and visible failure, no abandoned unreferenced jobs.
- Relative output paths: resolve consistently against the one configuration file.
- Diagnostic collection offline: never connect devices, import SDKs, or infer successful hardware acceptance.

### Task 1: Audit and remove migration residue

- [x] Record DELETE / MOVE / KEEP / WRAPPER decisions in `docs/legacy_audit.md`.
- [x] Move root tests and shared fakes under `tests/`; move synthetic preview and saved legacy inputs out of production/config paths.
- [x] Remove obsolete shortcut definitions and duplicate UI enablement policy; command availability remains authoritative.

### Task 2: Application services and lifecycle

- [x] Extract trajectory management, capture snapshot, hand actions, and HOME orchestration from `app/runtime.py` into focused application services; retain the current facade and remove unused A/B/C/D execution APIs.
- [x] Replace detached jobs with owned background job groups; drain completion jobs after command dispatch closes.
- [x] Order shutdown: stop capture / motion, close cameras and masters / hand, power down and disconnect robot, close workers. Preserve retry-on-failure.
- [x] Run existing runtime, command, shutdown and recording regressions; add focused lifecycle tests only where behavior changes.

### Task 3: Configuration, logging, errors and identity

- [x] Rename active config to `config/workbench.json`, update all formal consumers, resolve output paths centrally, validate profile and poll rates.
- [x] Add common domain error roots while preserving existing public exception imports.
- [x] Add standard `workbench.*` logging for lifecycle and domain events, version 1.0.0 and hardware-free diagnostics.
- [x] Test invalid config and diagnostics with fake devices; use UTC metadata timestamps.

### Task 4: Release documentation and CI

- [x] Rewrite README and architecture / dataset / hardware / configuration / migration docs and changelog.
- [x] Add one-time legacy trajectory migration tool using the existing adapter and store.
- [x] Add offline CI with compileall, pytest, Ruff and diff checks; label hardware tests explicitly.
- [x] Run focused checks then full regression with both official LeRobot environments. Record actual results and remaining physical acceptance / performance measurements in `docs/release_v1.md`.

## Execution notes

Initial baseline: 695 offline tests passed after P8. No hardware acceptance performed. Existing alternative RoArm / Inverse3 adapters and configured GELLO control modes are referenced runtime functionality, not dead files. Review removal choices using actual imports/callers.


## 2026-10-16 continuation and final evidence

Continued P9 in the existing shared workspace, preserving uncommitted implementation and calibrated configuration.

- Fixed HOME busy-state exclusion, producer/resource shutdown ordering, camera bridge retention on timeout, and discovery cleanup that previously bypassed safe shutdown. Retry remains bounded and pending data is retained.
- Fixed configuration-relative dataset/SDK paths and finite positive feedback/control rates. Fake configuration providers now implement the unified deployment-data interface.
- Added all release documents and completed the legacy migration CLI verification for four historical JSON inputs, using temporary output only.
- Final full official V2.1/V3/HDF5 regression: 721 passed, no skips, 71.51s. Compile, Ruff lint/format and diff checks passed.
- Ruling: producer stop failure prevents dependent device/Worker disposal; replaced the old unsafe continue-disposal expectation with retention/retry coverage. Independent cleanup still proceeds after producers are confirmed stopped.
- Ruling: preserve calibration/HOME, configured alternative masters and existing datasets; do not fabricate absolute limits or physical acceptance.
- Physical release acceptance and measurements remain unchecked in docs/release_v1.md. No commit, push, tag or hardware operation performed.

## 2026-10-17 structure review and branch delivery

The user explicitly requested an overall structural review, fixes and push to a new GitHub branch. This supersedes the earlier no-commit/no-push working constraint for this delivery. The target is `codex/workbench-structure-cleanup-20261017` on the existing origin repository; no merge or version tag is requested.
