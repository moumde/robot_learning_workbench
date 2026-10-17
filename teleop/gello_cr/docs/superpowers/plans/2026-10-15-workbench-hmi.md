# Unified Robot Learning Workbench HMI Implementation Plan

**Goal:** One offline-capable HMI for collection, trajectories, planning, dataset management, diagnostics and settings.
**Spec:** /home/ubuntu/.codex/attachments/7f297ad8-f365-4dbc-8800-5a6f034dea90/已粘贴的文本.txt
**Execution:** Inline; preserve the shared P0–P7 work. Use existing commands, writer workers and safety lanes. No hardware actuation.

- [x] Replace the recording/motion workflow coupling with independent RecordingState and explicit RobotState/MotionState projections. Keep application command serialization; support Dataset capture during replay/point motion. Add a global motion STOP on the existing safety lane with stale-start cancellation.
- [x] Expose application-owned dataset catalog/validation and robot diagnostics; enrich camera cache snapshots with per-stream FPS/age/status. Keep filesystem, SDK and worker operations outside Qt callbacks.
- [x] Replace the crowded operator layout with six sidebar pages and persistent global STOP/ESTOP and status. Move existing trajectory/planning/recovery panels into pages, centralize enablement, retain existing DAgger behind an advanced collection section.
- [x] Embed the settings editor as a page, move camera discovery and shutdown tasks to application workers, hide low-level servo/communication parameters from ordinary editing. Add planning settings and task name/description separation.
- [x] Focused state/command/Qt checks, offline screenshots at normal and minimum sizes, full regression with both existing LeRobot SDK environments. Document on-site acceptance still pending.

## Review focus
- Replay/point completion and global STOP preserve a recording/pending Episode.
- STOP/ESTOP/HOME remain usable while planning/finalize/validation blocks the normal command lane.
- Page changes never dispatch hardware control or duplicate action buttons.
- Dataset listing reads metadata only and never claims an unvalidated dataset is VALID.
- Settings remain inspectable offline; failed discovery/save is inline, and active sessions cannot apply edits.

## Verification record

- Full SDK-inclusive offline regression: **695 passed, 0 skipped, 70.03 s**, using the existing `/tmp/gello-cr-refactor-venv`, `/tmp/gello-v21-test-env` and `/tmp/gello-v3-test-env` interpreters.
- HMI tests exercise independent replay/recording commands, recorder-driven pending state, STOP preemption/reassertion/failure, metadata-only catalog browsing, explicit validation, per-stream quality, six-page navigation and offline preview-only plans. The task-name/instruction HDF5 regression verifies actual save and merge.
- Ruff passed for the HMI, state machine, view models, application services and shared player/preview changes. Scoped F checks passed for runtime/config/recording integration. `compileall src` and `git diff --check` passed.
- Inspected synthetic offscreen screenshots: `/tmp/gello-p8-collection.png`, `/tmp/gello-p8-collection-min.png` (1180×820), `/tmp/gello-p8-datasets.png`, `/tmp/gello-p8-settings.png`.
- Fixed pixmap-driven preview growth discovered during visual inspection; global STOP, ESTOP, HOME and the status footer remain outside page scrolling.
- No new runtime dependency and no real hardware operation. The one production entry remains `scripts/run_operator.sh`; the separate preview module is explicitly a synthetic UI development tool.

## Acceptance limits

The supplied on-site workflow, real camera/serial disconnects and simultaneous physical Teleop + 20Hz recording + three-camera preview load remain unverified. Three preview slots display the configured sources (including existing ROI mappings); this work does not invent physical cameras or change the capture schema. TCP offline planning needs a real kinematics/model provider; only explicit-start Joint PTP is available offline and is marked non-executable until replanned after connection. Hardware Profile is read from the existing JSON configuration, with one configured controller/source rather than invented profile choices.
