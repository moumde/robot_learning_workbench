# CR3 TCP PTP / waypoint recording

`record_rectangle_v21.py` makes the CR3 draw a small TCP rectangle and records
the actual joint/TCP feedback as a video-free LeRobot v2.1 dataset. The O6 hand
is read for the dataset but no O6 motion command is sent.

The default behavior is a 50 mm × 50 mm rectangle in the TCP's current XY
plane, with the current TCP orientation held fixed. The first corner is the
current TCP pose at the moment the robot is connected.

Preview without hardware:

```bash
python ptp/record_rectangle_v21.py \
  --preview-only \
  --start-pose 350 0 250 0 1.57 0 0
```

Record from the current robot pose. The explicit flag is required before any
real motion:

```bash
./scripts/run_nrc.sh python ptp/record_rectangle_v21.py \
  --confirm-motion
```

Useful options:

```text
--width-mm 40 --height-mm 40
--segment-duration-s 2.0 --dwell-s 0.5
--plane xy|xz|yz
--direction ccw|cw
--output-dir /absolute/path/to/output
--overwrite
```

The default output is:

```text
dataset/replay/ptp_rectangle_v21/
```

The main LeRobot fields remain compatible with the current replay tool:

```text
observation.state = [actual CR3 joints, actual O6 state]
action            = [target CR3 joints, constant O6 state]
```

Additional fields contain `observation.tcp_pose`, `target.tcp_pose`, and
`waypoint_index`. No camera videos are written.
