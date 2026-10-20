from __future__ import annotations

import json

from teleop.gello_cr.app.config_store import TeleopConfigStore


def test_relative_gello_urdf_is_resolved_from_config_directory(tmp_path, monkeypatch):
    config_dir = tmp_path / 'config'
    asset_dir = tmp_path / 'assets'
    other_dir = tmp_path / 'elsewhere'
    config_dir.mkdir()
    asset_dir.mkdir()
    other_dir.mkdir()
    (asset_dir / 'robot.urdf').write_text('<robot/>', encoding='utf-8')
    config_path = config_dir / 'teleop.json'
    config_path.write_text(
        json.dumps(
            {
                'gello': {
                    'control_mode': 'tcp_6d',
                    'kinematics_urdf': '../assets/robot.urdf',
                }
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.chdir(other_dir)

    store = TeleopConfigStore(config_path)

    assert store.resolve_path(store.data['gello']['kinematics_urdf']) == (
        asset_dir / 'robot.urdf'
    )
