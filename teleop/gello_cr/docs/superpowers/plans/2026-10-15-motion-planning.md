# Point / Waypoint Motion Planning Implementation Plan

> Execute inline with superpowers:executing-plans. Preserve the existing P0–P6 work; do not commit or operate real hardware.

**Goal:** Joint PTP, TCP PTP/Linear and mixed Waypoint planning with preview, explicit execution and measured target completion.
**Architecture:** Pure planners output the P3 Trajectory model. An application service owns preview and runs the existing TrajectoryPlayer under a POINT_MOVE lease. NRC unit conversion stays in a kinematics adapter; Qt only submits commands and renders snapshots.
**Tech Stack:** Python 3.12, NumPy, existing quaternion helpers, PySide6, pytest.
**Spec:** /home/ubuntu/.codex/attachments/047e1cd6-e746-4c2d-b867-baad2d651000/已粘贴的文本.txt

## Constraints
- Internal rad / m / s; existing NRC intrinsic XYZ orientation convention is preserved.
- No supplied hardware absolute bounds: reuse optional motion joint/workspace bounds and expose missing bounds in preview.
- Configured operating speed/acceleration limits, quintic timing, quaternion SLERP. No collision detection or new dependency.
- No hardware actuation in verification; focused functional tests, no hash/smoke framework.

## Review focus
- Multi-solution and discontinuous IK: nearest valid solution, FK residual check, explicit failure.
- Rotations across ±pi: shortest quaternion path and rotation-distance reached check.
- Edited/stale previews: explicit plan ID, actual starting joint check; no automatic transition.
- STOP/HOME/ESTOP during execution or reached wait: lease cancellation, no stale success or workflow completion.
- Partial waypoint failure: no executable partial result; hold timestamps strictly increase and zero waypoint endpoint velocity.

## Tasks
- [x] Core types/model/config, quintic Joint PTP, TCP PTP/Linear, mixed Waypoint/hold, validation and persisted planning metadata. Add focused offline tests then run tests/planning.
- [x] NRC kinematics adapter, stable joint/TCP reached policy, POINT_MOVE application service and shared-player execution. Test real coordinator/executor with fake robot, STOP/preempt/timeout/stale preview.
- [x] Command/state/presenter integration, point/waypoint panel, read current, preview, save/execute/stop. Test UI unit conversion and command routing; inspect offline screenshot.
- [x] Document configuration, absent bounds and physical acceptance limits. Run focused lint and full regression once with the existing V2.1/V3 test environments.

## Verification

- `tests/planning`: 34 passed; fake kinematics, real MotionCoordinator/Executor and synthetic robot feedback only.
- Full SDK-inclusive suite: **683 passed, 0 skipped, 68.76 s** using `/tmp/gello-cr-refactor-venv/bin/python`, `GELLO_TEST_V21_PYTHON=/tmp/gello-v21-test-env/bin/python`, `GELLO_TEST_V3_PYTHON=/tmp/gello-v3-test-env/bin/python`.
- New planning/player/model files pass Ruff; changed application integration files pass scoped F checks. `compileall src` and `git diff --check` passed.
- Offscreen UI inspected at `/tmp/gello-p7-planning-ui.png`; fixed the old fixed Tab height so the waypoint editor and preview do not overlap, preserving the fixed stop/HOME header.
- Planner boundary search found no NRC command, GUI or dataset-format dependency.

## Physical acceptance still pending

No real hardware was connected or moved. The NRC adapter's single-solution, unseeded IK limitation is visible in preview and documented. No absolute joint/workspace bounds were invented. Physical Joint PTP/TCP PTP/Linear/Waypoint acceptance, controller IK branch behavior, measured straight-line deviation and final pose tolerances still need the on-site sequence in the supplied spec. Collision checking is unavailable.
