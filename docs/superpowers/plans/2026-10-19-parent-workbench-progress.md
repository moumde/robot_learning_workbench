# Parent workbench migration progress

Plan: docs/superpowers/plans/2026-10-19-parent-workbench.md

All five implementation tasks completed in the existing integration workspace and branch. Existing uncommitted HOME/feedback-recovery fixes were preserved. No training, policy inference or deployment implementation changes were made.

## Implementation

- Canonical Qt UI, Designer forms, generated bindings and QSS live in hmi/collection.
- Shared application state, runtime, motion, trajectory and Recorder live in core/workbench.
- Robot, camera and O6 adaptation/communication live in core/hardware. CR3A delegates to one parent CR3Interface; cameras share one parent CR3O6CameraInterface.
- GELLO input, mapping, calibration and follow strategy remain in teleop/gello_cr. Legacy imports alias the canonical modules and preserve enum/class identity and monkeypatch behavior.
- Parent pyproject owns installation and resources. Nested pyproject removed; parent and legacy entry points both run from /tmp after parent editable installation.
- All eight Designer bindings regenerated. Parent replay bridge imports canonical trajectory code directly.

## Verified fixes

- Initial feedback failure cannot report robot connected while partial resources await cleanup.
- Partial disconnect is retryable; connection status requires both owned SDK channels, even if the SDK accepts a missing descriptor.
- Slow camera connection cannot lock UI snapshots; status reads use service caches. Real sampling timestamps are retained.
- Offline lifecycle tests now explicitly release the parent-owned endpoint lock.

## Final evidence — 2026-10-19

- Complete production-environment offline suite: 991 passed in 86.85 s, including actual LeRobot V2.1/V3 and HDF5 writes/readback and interrupted-data recovery. Log: /tmp/parent-framework-final-991.log.
- Final canonical-module Ruff checks, launcher shell syntax and git diff --check passed.
- Scoped read-only final review found no new actionable defects; wheel installation and physical hardware were not independently validated.
- Parent-composition end-to-end simulation: 300.004 s healthy recording; three Episodes with 2,001 frames each, 6,003 total, approximately 19.995 FPS. Total scenario time 363.660 s.
- Actual parent Robot/Camera ownership asserted; simulated source approximately 100 Hz and each camera approximately 30 Hz. Qt heartbeat p95 21.547 ms, maximum 48.432 ms; no unhandled errors or surviving application workers.
- Exercised discard, GELLO/camera/robot/O6 failures, software emergency stop, explicit fault recovery and reconnect. Recovery does not restart following automatically.
- Three formats finalized and read back: V2.1 six Episodes/6,126 frames; HDF5 one/61; V3 one/61. Existing quality/review flags retained. Camera hardware dropped frames remain unknown.
- Post-run parent trajectory bridge loaded 2,001 frames; saved O6 feedback and open/closed targets were verified.
- Report: logs/parent-framework-stability-20261019/report.json; screenshots beside the report. Only hardware signals were simulated, with data isolated under that report directory.

No commit or GitHub publication was performed for this migration. Real SDK transport, motion and physical emergency-stop validation remain outside this offline run.
