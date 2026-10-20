
from __future__ import annotations

from pathlib import Path
from teleop.gello_cr.tests.fakes.paths import implementation_path

from teleop.gello_cr.bootstrap.runtime_factory import (
    ConcreteRuntimeFactory,
    RuntimeConstructors,
    RuntimeFactoryPaths,
)


CFG = {
    'master': {'type': 'gello'},
    'robot': {
        'ip': '192.168.1.245',
        'command_port': 6001,
        'servo_port': 7000,
        'robot_num': 1,
        'movej_velocity': 10.0,
        'movej_acc': 20.0,
        'movej_dec': 20.0,
        'movej_period_s': 0.1,
        'movej_low_latency': False,
        'servoj_vmax': 80.0,
        'servoj_amax': 200.0,
        'servoj_jmax': 150.0,
    },
    'roarm': {'port': 'ro', 'baudrate': 1, 'feedback_hz': 20.0},
    'inverse3': {
        'uri': 'ws://x', 'device_id': '', 'grip_device_id': '',
        'feedback_hz': 20.0, 'basis': 'XYZ',
    },
    'gello': {
        'port': 'ge', 'software_root': '/tmp/gello',
        'joint_ids': [1,2,3,4,5,6], 'joint_offsets': [0]*6,
        'joint_signs': [1]*6, 'gripper_config': [7, 1, 2],
        'baudrate': 57600, 'feedback_hz': 100.0,
        'feedback_timeout_s': 0.5,
    },
    'o6': {'port': 'o6', 'hand_id': 39, 'baudrate': 115200},
    'dataset': {
        'worker_python': '/tmp/python', 'repo_prefix': 'local/test',
        'fps': 20, 'image_size': [224,224],
        'wrist_camera_serial': 'wrist', 'base_camera_serial': 'base',
        'base_roi_norm': [0.1, 0.1, 0.9, 0.9],
        'camera_max_age_s': 0.5, 'camera_max_skew_s': 0.1,
    },
}


from teleop.gello_cr.app.config_store import TeleopConfigStore, DEFAULT_CONFIG, _deep_merge


class Store(TeleopConfigStore):
    def __init__(self, path):
        self.path = path
        self.data = _deep_merge(DEFAULT_CONFIG, CFG)


class Passive:
    connected = False
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Engine:
    def __init__(self, store, master, o6):
        self.store = store
        self.roarm = master
        self.o6 = o6
        self.events = type('Events', (), {'put': lambda self, value: None})()
        self.attached = []
    def dataset_sample(self): return {'quality': {}}
    def attach_robot(self, session): self.attached.append(session)
    def detach_robot(self, session, reason): return True


class Recorder(Passive):
    def snapshot(self): return {}


class Camera(Passive):
    pass


class Cr3a(Passive):
    connected = False


def constructors():
    return RuntimeConstructors(
        TeleopConfigStore=Store,
        RoArmSerialController=Passive,
        Inverse3Controller=Passive,
        GelloController=Passive,
        O6Controller=Passive,
        TeleopRuntime=Engine,
        RecordingSession=Recorder,
        Cr3aDevice=Cr3a,
        RealSenseRgbDevice=Camera,
    )


def test_factory_builds_gello_runtime_without_connecting_hardware(tmp_path) -> None:
    paths = RuntimeFactoryPaths(
        repo_root=tmp_path,
        config_path=tmp_path / 'config.json',
        linker_hand_sdk_root=tmp_path / 'hand',
        nrc_sdk_root=None,
    )
    runtime = ConcreteRuntimeFactory(
        paths,
        constructors=constructors(),
    ).build()

    assert runtime.master_controller is runtime.gello_controller
    assert runtime.roarm_controller is None
    assert runtime.inverse3_controller is None
    assert runtime.teleop_engine.attached == []
    assert runtime.cr3a_lifecycle.device is None
    assert runtime.cr3a_lifecycle.session is None
    assert runtime.camera_devices["wrist"].config.serial == "wrist"
    assert runtime.camera_devices["base"].config.serial == "base"


def test_factory_does_not_call_connect_power_or_start_by_source() -> None:
    source = implementation_path('teleop/gello_cr/bootstrap/runtime_factory.py').read_text(encoding='utf-8')
    build = source.split('    def build(self) -> ConcreteRuntime:', 1)[1]
    build = build.split('\n        return ConcreteRuntime(', 1)[0]

    for forbidden in (
        '.connect(', '.power_on(', '.start_follow(', '.start_episode('
    ):
        assert forbidden not in build


def test_factory_selects_master_from_config(tmp_path) -> None:
    paths = RuntimeFactoryPaths(
        repo_root=tmp_path,
        config_path=tmp_path / 'config.json',
        linker_hand_sdk_root=tmp_path / 'hand',
        nrc_sdk_root=None,
    )
    runtime = ConcreteRuntimeFactory(
        paths,
        constructors=constructors(),
    ).build()
    assert runtime.master_controller is runtime.gello_controller


def test_factory_resolves_relative_gello_source_from_config_directory(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / 'config' / 'teleop.json'
    monkeypatch.setitem(CFG['gello'], 'software_root', '../vendor/gello')
    paths = RuntimeFactoryPaths(
        repo_root=tmp_path,
        config_path=config_path,
        linker_hand_sdk_root=tmp_path / 'hand',
        nrc_sdk_root=None,
    )

    runtime = ConcreteRuntimeFactory(
        paths,
        constructors=constructors(),
    ).build()

    assert runtime.gello_controller.kwargs['software_root'] == str(
        (config_path.parent / '../vendor/gello').resolve()
    )


def test_factory_uses_explicit_data_python_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('GELLO_CR_DATA_PYTHON', '/tmp/lerobot-python')
    paths = RuntimeFactoryPaths(
        repo_root=tmp_path,
        config_path=tmp_path / 'config.json',
        linker_hand_sdk_root=tmp_path / 'hand',
        nrc_sdk_root=None,
    )

    runtime = ConcreteRuntimeFactory(
        paths,
        constructors=constructors(),
    ).build()

    assert runtime.recorder.session.kwargs['writer_factory']().worker_python == '/tmp/lerobot-python'


def test_runtime_exposes_application_lifecycle_callbacks(tmp_path) -> None:
    paths = RuntimeFactoryPaths(
        repo_root=tmp_path,
        config_path=tmp_path / 'config.json',
        linker_hand_sdk_root=tmp_path / 'hand',
        nrc_sdk_root=None,
    )
    runtime = ConcreteRuntimeFactory(
        paths,
        constructors=constructors(),
    ).build()
    callbacks = runtime.lifecycle

    assert callable(callbacks.connect)
    assert callable(callbacks.disconnect)
    assert callable(callbacks.power_on)
    assert callable(callbacks.power_off)
    assert callable(callbacks.reset_fault)
    assert callable(callbacks.reset_estop)


def test_runtime_keeps_devices_open_until_motion_producers_stop():
    from types import SimpleNamespace
    import pytest
    from teleop.gello_cr.bootstrap.runtime_factory import ConcreteRuntime

    stopped = False
    closed = []

    def stop_motion(**kwargs):
        if not stopped:
            raise TimeoutError("motion producer still running")

    runtime = ConcreteRuntime(
        paths=None, store=None, roarm_controller=None, inverse3_controller=None,
        gello_controller=SimpleNamespace(close=lambda **kw: closed.append("gello")),
        master_controller=None, o6_controller=SimpleNamespace(close=lambda: closed.append("o6")),
        teleop_engine=SimpleNamespace(shutdown=stop_motion), sample_source=None,
        recorder=None, camera_devices={},
        cr3a_lifecycle=SimpleNamespace(
            stop_feedback=lambda: None,
            shutdown_power=lambda: closed.append("power"),
            disconnect=lambda: closed.append("connection")),
    )
    with pytest.raises(ExceptionGroup, match="Runtime shutdown incomplete"):
        runtime.close()
    assert closed == []
    stopped = True
    runtime.close()
    assert closed == ["gello", "o6", "power", "connection"]
