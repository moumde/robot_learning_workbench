"""Training field layouts shared by capture and every dataset writer."""

from dataclasses import dataclass

from gello_cr.data_contract import recording_fields

IMAGE_KEYS = ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")


@dataclass(frozen=True, slots=True)
class RecordingSchema:
    name: str
    observation_fields: tuple[str, ...]
    action_fields: tuple[str, ...]
    image_keys: tuple[str, ...] = IMAGE_KEYS


def recording_schema(mode: str) -> RecordingSchema:
    state, action = recording_fields(mode)
    return RecordingSchema(mode, state, action)
