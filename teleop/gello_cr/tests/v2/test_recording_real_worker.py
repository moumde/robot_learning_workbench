"""Full recorder -> Unix IPC -> real LeRobot/MP4 -> validation, synthetic inputs."""
import sys
import os
import time
from pathlib import Path
import json

import numpy as np
import pytest

WORKER_PYTHON = os.environ.get('GELLO_TEST_V3_PYTHON', sys.executable)
if 'GELLO_TEST_V3_PYTHON' not in os.environ:
    pytest.importorskip('lerobot.datasets.lerobot_dataset')
pytest.importorskip('av')

from types import SimpleNamespace
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.schema import IMAGE_KEYS
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.recording.writers.lerobot_v3 import LeRobotV3Writer
from teleop.gello_cr.recording.validate_dataset import validate_dataset


@pytest.mark.parametrize("mode,state_dim", [("tcp", 18), ("joint", 12)])
def test_real_worker_success_failure_discard_and_finalize(tmp_path, monkeypatch, mode, state_dim):
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setenv('HF_DATASETS_OFFLINE', '1')
    image = np.full((224,224,3), 90, dtype=np.uint8)
    def sample():
        ts = time.monotonic()
        return CaptureFrame(ts, (0.,)*state_dim, (0.,)*12, {key: image for key in IMAGE_KEYS},
            metadata={"recording_mode": mode, "quality": {"wrist_timestamp": ts,
                "base_timestamp": ts, "wrist_age_s": 0., "base_age_s": 0., "camera_skew_s": 0.}})
    recorder = RecordingSession(SimpleNamespace(capture=sample),
        lambda: LeRobotV3Writer(WORKER_PYTHON, 'local/offline-test'), event_callback=lambda *args: None)
    counts = []
    for outcome in ('success', 'failure', 'discard'):
        recorder.start_episode('synthetic offline test', str(tmp_path), metadata={'synthetic': True})
        deadline = time.monotonic() + 10
        while recorder.snapshot()['buffered_frames'] < 3:
            assert not recorder.snapshot()['error']
            assert time.monotonic() < deadline
            time.sleep(.01)
        recorder.stop_episode()
        count = recorder.snapshot()['buffered_frames']
        assert count >= 3 and not recorder.snapshot()['episode_active']
        assert recorder.snapshot()['saved_episodes'] == len(counts)
        if outcome == 'discard':
            recorder.discard_episode()
        else:
            recorder.save_episode(outcome)
            counts.append(count)
        assert recorder.snapshot()['buffered_frames'] == 0
    root = recorder.snapshot()['root']
    recorder.close()
    recorder.close()
    result = validate_dataset(root)
    assert result['episodes'] == 2
    assert result['frames'] == sum(counts)
    assert not recorder.snapshot()['session_active']


def test_native_resolution_and_switch_root_without_restarting(tmp_path):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, ::4] = 255

    def sample():
        ts = time.monotonic()
        return CaptureFrame(ts, (0.,)*18, (0.,)*12, {key: image for key in IMAGE_KEYS},
            metadata={"quality": {"wrist_timestamp": ts, "base_timestamp": ts,
                                  "wrist_age_s": 0., "base_age_s": 0., "camera_skew_s": 0.}})

    recorder = RecordingSession(SimpleNamespace(capture=sample),
        lambda: LeRobotV3Writer(WORKER_PYTHON, 'local/native'),
        event_callback=lambda *args: None, image_size=(480,640))
    roots = []
    try:
        for parent in (tmp_path / 'first folder', tmp_path / 'second folder'):
            recorder.start_episode('native recording', str(parent))
            deadline = time.monotonic() + 15
            while recorder.snapshot()['buffered_frames'] < 3:
                assert not recorder.snapshot()['error']
                assert time.monotonic() < deadline
                time.sleep(.01)
            recorder.stop_episode()
            recorder.save_episode('success')
            root = Path(recorder.snapshot()['root'])
            assert root.parent == parent
            roots.append(root)
        recorder.close()
        for root in roots:
            assert validate_dataset(root)['valid']
            info = json.loads((root / 'meta/info.json').read_text())
            assert info['features']['observation.images.base_0_rgb']['shape'] == [480, 640, 3]
    finally:
        if recorder.snapshot()['episode_active']:
            recorder.stop_episode()
        if recorder.snapshot()['buffered_frames']:
            recorder.discard_episode()
        recorder.close()
