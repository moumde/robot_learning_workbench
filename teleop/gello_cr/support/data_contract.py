"""Canonical TCP and absolute-joint robot-learning field layouts."""

STATE_DIM = 18
ACTION_DIM = 12
FPS = 20
IMAGE_SIZE = (224, 224)
CAMERA_KEYS = ("base_rgb", "wrist_rgb", "roi_rgb")

STATE_FIELDS = (
    "cr5.j1.rad",
    "cr5.j2.rad",
    "cr5.j3.rad",
    "cr5.j4.rad",
    "cr5.j5.rad",
    "cr5.j6.rad",
    "cr5.tcp.x.m",
    "cr5.tcp.y.m",
    "cr5.tcp.z.m",
    "cr5.tcp.roll.rad",
    "cr5.tcp.pitch.rad",
    "cr5.tcp.yaw.rad",
    "o6.thumb_flex.position",
    "o6.thumb_yaw.position",
    "o6.index_flex.position",
    "o6.middle_flex.position",
    "o6.ring_flex.position",
    "o6.little_flex.position",
)

ACTION_FIELDS = (
    "cr5.delta_tcp.x.m",
    "cr5.delta_tcp.y.m",
    "cr5.delta_tcp.z.m",
    "cr5.delta_tcp.roll.rad",
    "cr5.delta_tcp.pitch.rad",
    "cr5.delta_tcp.yaw.rad",
    "o6.thumb_flex.command",
    "o6.thumb_yaw.command",
    "o6.index_flex.command",
    "o6.middle_flex.command",
    "o6.ring_flex.command",
    "o6.little_flex.command",
)

assert len(STATE_FIELDS) == STATE_DIM
assert len(ACTION_FIELDS) == ACTION_DIM


JOINT_STATE_FIELDS = tuple(f"cr3.q{i}.rad" for i in range(1, 7)) + STATE_FIELDS[12:]
JOINT_ACTION_FIELDS = tuple(f"cr3.target_q{i}.rad" for i in range(1, 7)) + ACTION_FIELDS[6:]


def recording_fields(mode="tcp"):
    """TCP retains the legacy contract; joint actions are absolute sent targets."""
    if mode == "tcp":
        return STATE_FIELDS, ACTION_FIELDS
    if mode == "joint":
        return JOINT_STATE_FIELDS, JOINT_ACTION_FIELDS
    raise ValueError(f"Unknown recording mode: {mode}")
