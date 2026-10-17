# Interrupted dataset recovery and merge implementation plan

**Goal:** Resume interrupted capture in a new segment and publish a validated dataset from the batch, retaining original segments.
**Spec:** User attachment `e198a1ee-34d5-470e-8745-3dd87991c0c6/已粘贴的文本.txt`.
**Architecture:** BatchManager orchestrates a single RecordingSession. SegmentWriter persists canonical frame packets before acknowledging samples, alongside each format's normal output. Recovery reads those journals instead of repairing interrupted SDK files. Separate mergers rebuild the same format with the existing writers, validate, then publish by rename inside the output filesystem.

## Constraints

- Keep sampling, motion, capture semantics and the P5 worker protocol unchanged.
- Resume always creates a new segment. Batch-wide episode IDs have an explicit final-index mapping.
- Partial records require an explicit discard/failure decision. No automatic video/parquet repair or success inference.
- Compare only the schema/profile compatibility required by the spec; no file checksum framework.
- Do not delete original segments, even after merge or logical batch discard.
- Keep expensive SDK operations off the UI and robot control threads.

## Tasks

- [x] Add atomic manifests, batch locks, typed batch/segment status and canonical frame journals. Check persistence and live-lock exclusion.
- [x] Add SegmentWriter and generic explicit-open/release hooks to RecordingSession. Add BatchManager, heartbeat, global episode allocation and segment lifecycle.
- [x] Add read-only recovery scanning, profile compatibility checks, new-segment resume and explicit partial resolutions.
- [x] Add merger protocol/factory, three writer-backed rebuilders, source validation, provenance, final validation and atomic publication/retry.
- [x] Wire runtime composition and application commands; add recovery/partial controls and batch information to the UI.
- [x] Test hard process-group termination, recovery and merge for all three real formats, episode-boundary recovery, mismatch rejection and interrupted publication. Run full regression and update documentation.

## Review focus

Preserve saved V3 episodes even when the original Parquet footer was not closed. Keep partial episodes out until explicitly resolved. Reject changed capture profiles. Exclude live batches using OS locks. Retain a failed merge as an unpublished temporary result and support retry after a crash around publication.

## Validation completed

- Full offline regression with both external SDK environments: 647 passed in 61.87s, no skips.
- Added the explicit episode-boundary hard-kill case after that run; all four process-group crash cases passed in 33.58s (V2.1 partial discard, V3 partial failure, HDF5 partial failure, HDF5 interruption between saved episodes).
- Verified new-segment resume, batch-wide IDs and final remapping, mismatch rejection, retained source segments, publication failures before/after rename, partial decisions and zero-frame I/O failure handling.
- Related Ruff checks, source compilation, whitespace checks and offscreen recovery UI inspection passed.
- Physical power-cut tests, CR3/O6/camera integration, OpenPI training and sustained real control-load acceptance remain for the hardware site. The automated kill tests operate only on synthetic capture subprocesses and their SDK workers.
