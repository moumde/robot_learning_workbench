# Multi-format dataset writers implementation plan

**Goal:** Record the same CaptureFrames as LeRobot V2.1, V3 or HDF5.
**Architecture:** Keep capture and sampling unchanged. Reuse WorkerClient and its packet protocol, with a shared writer client and independent backend services. LeRobot files come from the official SDK; HDF5 commits pending groups.
**Spec:** User attachment `0ff4812f-3f4c-4e7c-97cc-d53d113a26d0/已粘贴的文本.txt`.

## Constraints

- V3 remains the default and retains its feature mapping and encoding settings.
- No hardware actions, recovery, merge, upload or format conversion.
- Format selection stays outside capture, sampling, motion and trajectory code.
- Focused functional tests; no hash matching or smoke-test framework.
- Existing uncommitted work stays in this workspace.

## Tasks

- [x] Add DatasetFormat, writer configuration and capabilities; extract shared worker client mapping without changing V3 payload semantics. Test factory dispatch and existing V3 behavior.
- [x] Implement HDF5 worker with extendible datasets, pending/save/discard, metadata and raw structured fields. Test real file reopening, multiple outcomes and discard.
- [x] Implement V2.1 through the official v0.3.3 SDK in its own Python environment, with session/episode sidecars and aggregate statistics. Check version before creating files.
- [x] Add common validation reports, V2.1/HDF5 validators and a wrapper around the existing V3 validator. Run validation after finalize in the worker.
- [x] Add application format selection, explicit create/finalize commands and UI locking. Preserve default start-episode workflow. Test command routing and locking.
- [x] Compare the same synthetic frames through real available writers/readers, run relevant regression tests, update runtime/dependency documentation.

## Review focus

Check that discard never creates a committed episode, failed saves retain the pending episode, missing raw fields preserve sample alignment, selecting a format cannot mutate an open dataset, and SDK version mismatch cannot create the wrong LeRobot format.

## Validation completed

- Full offline suite with both external SDK environments: 628 passed in 29.76s, no skips.
- Real 100-frame comparison: official V2.1/V3 readers and validators, HDF5 reopening, success/failure/discard, state/action/capture-time equivalence, image counts and decoding all passed.
- Existing trajectory adapter read both actual LeRobot outputs without changes; no robot replay was executed.
- V2.1 used LeRobot 0.3.3; V3 used official 0.6.2 source; both used PyAV 15.1.0. LeRobot remains absent from the operator test Python.
- Related Ruff checks, source compilation, diff whitespace checks and offscreen UI inspection passed.
- Physical robot/camera capture, OpenPI deployment and sustained control-load acceptance remain for the hardware site. Recovery/merge remain P6.
