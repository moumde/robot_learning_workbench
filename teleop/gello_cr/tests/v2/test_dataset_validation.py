"""Real local Parquet/video fixture; no hardware and no Hub access."""
import json

import numpy as np
import pytest

pq = pytest.importorskip('pyarrow.parquet')
av = pytest.importorskip('av')

from gello_cr.recording.writers.lerobot_v3 import dataset_features, LEROBOT_IMAGE_FEATURE_KEYS
from gello_cr.recording.validate_dataset import validate_dataset


@pytest.fixture
def dataset(tmp_path):
    import pandas as pd
    import pyarrow as pa
    root = tmp_path / 'data-set'
    (root / 'meta/collection').mkdir(parents=True)
    (root / 'meta/episodes/chunk-000').mkdir(parents=True)
    (root / 'data/chunk-000').mkdir(parents=True)
    info = {'codebase_version': 'v3.0', 'fps': 20, 'total_frames': 3,
            'total_episodes': 1, 'features': dataset_features(224, 224),
            'video_path': 'videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4'}
    (root / 'meta/info.json').write_text(json.dumps(info))
    rows = [{'index': i, 'episode_index': 0, 'frame_index': i, 'timestamp': i/20,
             'task_index': 0, 'observation.state': [0.0]*18, 'action': [0.0]*12}
            for i in range(3)]
    pq.write_table(pa.Table.from_pylist(rows), root / 'data/chunk-000/file-000.parquet')
    tasks = pd.DataFrame({'task_index': [0]}, index=['synthetic offline test'])
    pq.write_table(pa.Table.from_pandas(tasks), root / 'meta/tasks.parquet')
    episode = {'episode_index': 0, 'length': 3}
    for key in LEROBOT_IMAGE_FEATURE_KEYS:
        path = root / info['video_path'].format(video_key=key, chunk_index=0, file_index=0)
        path.parent.mkdir(parents=True)
        with av.open(str(path), mode='w') as output:
            stream = output.add_stream('libx264', rate=20)
            stream.width = stream.height = 224
            stream.pix_fmt = 'yuv420p'
            for i in range(3):
                frame = av.VideoFrame.from_ndarray(np.full((224,224,3), i*40, dtype=np.uint8), format='rgb24')
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
        episode.update({f'videos/{key}/chunk_index': 0, f'videos/{key}/file_index': 0,
                        f'videos/{key}/from_timestamp': 0., f'videos/{key}/to_timestamp': 3/20})
    pq.write_table(pa.Table.from_pylist([episode]), root / 'meta/episodes/chunk-000/file-000.parquet')
    samples = [{'timestamp': 100+i/20, 'quality': {'wrist_timestamp': 100+i/20,
                'base_timestamp': 100+i/20, 'wrist_age_s': 0., 'base_age_s': 0., 'camera_skew_s': 0.}}
               for i in range(3)]
    (root / 'meta/collection/episode_000000.json').write_text(json.dumps({
        'episode_index': 0, 'frame_count': 3, 'outcome': 'success', 'context': {},
        'image_streams': dict(zip(('Base RGB', 'Wrist RGB', 'Base ROI'), LEROBOT_IMAGE_FEATURE_KEYS)),
        'task': 'synthetic offline test', 'quality': {'needs_review': False}, 'samples': samples}))
    return root


def test_reads_every_video_and_checks_all_frames(dataset):
    result = validate_dataset(dataset)
    assert result['valid'] and result['frames'] == 3 and result['videos'] == 3


@pytest.mark.parametrize('damage', ['nan', 'dimension', 'timestamp', 'count', 'task', 'video',
                                   'camera_skew', 'sample_count', 'metadata'])
def test_rejects_corrupted_dataset(dataset, damage):
    import pyarrow as pa
    path = dataset / 'data/chunk-000/file-000.parquet'
    rows = pq.read_table(path).to_pylist()
    if damage == 'nan': rows[0]['action'][0] = float('nan')
    if damage == 'dimension': rows[0]['observation.state'] = [0.0]
    if damage == 'timestamp': rows[1]['timestamp'] = -1
    if damage == 'task': rows[0]['task_index'] = 99
    if damage == 'count': rows.pop()
    pq.write_table(pa.Table.from_pylist(rows), path)
    if damage == 'video': next((dataset / 'videos').rglob('*.mp4')).write_bytes(b'broken')
    if damage in ('camera_skew', 'sample_count', 'metadata'):
        sidecar = dataset / 'meta/collection/episode_000000.json'
        data = json.loads(sidecar.read_text())
        if damage == 'camera_skew': data['samples'][0]['quality']['camera_skew_s'] = 1.0
        if damage == 'sample_count': data['samples'].pop()
        if damage == 'metadata': del data['context']
        sidecar.write_text(json.dumps(data))
    with pytest.raises((ValueError, KeyError, av.error.FFmpegError)):
        validate_dataset(dataset)
