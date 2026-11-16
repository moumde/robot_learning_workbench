"""Construct view-model command availability without importing Qt."""

from teleop.gello_cr.app.service import ApplicationSnapshot
from teleop.gello_cr.app.view_model import build_application_view_model


def command_availability(state, *, episode_active, episode_pending):
    app = ApplicationSnapshot(state, state, 0, "")
    recorder = {"episode_active": episode_active, "buffered_frames": 1 if episode_pending else 0}
    return build_application_view_model(app, {}, recorder).actions
