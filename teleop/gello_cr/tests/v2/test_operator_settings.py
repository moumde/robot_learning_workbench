"""Configuration persistence and actual offscreen settings interactions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.settings import OperatorSettings

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "teleop.json"
    path.write_bytes((ROOT / "config/teleop/gello_cr.json").read_bytes())
    return OperatorSettings(path, TeleopConfigStore)


def test_save_round_trip_preserves_unedited_config_and_running_store(settings):
    running = TeleopConfigStore(settings.path)
    before = copy.deepcopy(running.data)
    original_bytes = settings.path.read_bytes()
    candidate = copy.deepcopy(settings.data)
    candidate["robot"]["servoj_vmax"] = 45.0
    candidate["dataset"]["fps"] = 15
    candidate["dataset"]["recording_mode"] = "joint"
    settings.save(candidate)
    reloaded = TeleopConfigStore(settings.path).data
    assert reloaded == candidate
    assert running.data == before
    assert settings.path.with_suffix(".json.bak").read_bytes() == original_bytes
    assert reloaded["presets"] == before["presets"]
    assert reloaded["gello"]["joint_offsets"] == before["gello"]["joint_offsets"]


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("robot", "servoj_vmax", float("nan")),
        ("robot", "servoj_amax", 0),
        ("robot", "safety_max_command_step_rad", -1),
        ("robot", "safety_speed_violation_cycles", 1.5),
        ("robot", "command_port", 65536),
        ("gello", "joint_scale", 1.6),
        ("dataset", "fps", 0),
        ("dataset", "recording_mode", "invalid"),
        ("dataset", "camera_max_age_s", float("inf")),
        ("dataset", "base_roi_norm", [0.7, 0.1, 0.3, 0.9]),
        ("o6", "speed", [256] * 6),
        ("o6", "closed_action", "missing"),
    ],
)
def test_invalid_input_does_not_touch_disk_or_draft(settings, section, key, value):
    original = settings.path.read_bytes()
    before = copy.deepcopy(settings.data)
    candidate = copy.deepcopy(settings.data)
    candidate[section][key] = value
    with pytest.raises(ValueError):
        settings.save(candidate)
    assert settings.path.read_bytes() == original
    assert settings.data == before
    assert not settings.path.with_suffix(".json.bak").exists()


def test_external_edit_is_not_overwritten(settings):
    external = settings.path.read_bytes() + b"\n"
    settings.path.write_bytes(external)
    with pytest.raises(RuntimeError, match="其他程序"):
        settings.save(settings.data)
    assert settings.path.read_bytes() == external
    assert not settings.path.with_suffix(".json.bak").exists()


def test_failed_atomic_replace_preserves_original(settings, monkeypatch):
    original = settings.path.read_bytes()
    before = copy.deepcopy(settings.data)
    candidate = copy.deepcopy(before)
    candidate["robot"]["servoj_vmax"] = 30

    def fail(*args):
        raise OSError("disk write refused")

    monkeypatch.setattr("teleop.gello_cr.app.config_store.os.replace", fail)
    with pytest.raises(OSError, match="disk write refused"):
        settings.save(candidate)
    assert settings.path.read_bytes() == original
    assert settings.data == before


def test_deleted_default_action_does_not_reappear_on_restart(settings):
    candidate = copy.deepcopy(settings.data)
    del candidate["o6"]["actions"]["中指"]
    candidate["o6"]["actions"]["自定义"] = [20, 30, 40, 50, 60, 70]
    candidate["o6"]["closed_action"] = "自定义"
    settings.save(candidate)
    assert TeleopConfigStore(settings.path).data["o6"] == candidate["o6"]


@pytest.fixture
def dialog(settings):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from teleop.gello_cr.ui.settings_dialog import OperatorSettingsDialog

    app = QApplication.instance() or QApplication([])
    widget = OperatorSettingsDialog(settings)
    widget.show()
    app.processEvents()
    yield widget, app
    widget.hide()
    widget.deleteLater()
    app.processEvents()


def test_dialog_does_not_change_any_values_when_untouched(dialog):
    widget, _ = dialog
    assert widget._candidate() == widget.settings.data


def test_camera_window_selection_round_trips_and_preserves_unselected_settings(dialog):
    widget, app = dialog
    name, serial, mode, roi = widget.camera_editors[2]
    name.setText("操作区特写")
    serial.setEditText("new-camera")
    mode.setCurrentIndex(mode.findData("camera"))
    assert not any(edit.isEnabled() for edit in roi)
    mode.setCurrentIndex(mode.findData("roi"))
    assert all(edit.isEnabled() for edit in roi)
    for edit, value in zip(roi, (0.1, 0.2, 0.8, 0.9), strict=True):
        edit.setText(str(value))
    widget._show_cameras([{"serial": "new-camera", "name": "D435"}], "")
    assert serial.currentText() == "new-camera · D435"
    widget._save()
    app.processEvents()
    assert widget.saved
    stored = TeleopConfigStore(widget.settings.path).data
    assert stored["dataset"]["camera_streams"][2] == {
        "name": "操作区特写",
        "serial": "new-camera",
        "mode": "roi",
        "roi_norm": [0.1, 0.2, 0.8, 0.9],
    }
    assert stored["dataset"]["image_size"] == [480, 640]
    assert stored["robot"] == widget.settings.data["robot"]


def test_invalid_roi_in_selected_window_is_not_saved(dialog):
    widget, _ = dialog
    before = widget.settings.path.read_bytes()
    _, _, mode, roi = widget.camera_editors[2]
    mode.setCurrentIndex(mode.findData("roi"))
    roi[0].setText("0.9")
    roi[2].setText("0.1")
    widget._save()
    assert not widget.saved
    assert "ROI" in widget.error_label.text()
    assert widget.settings.path.read_bytes() == before


def test_action_selection_save_reaches_both_runtime_mapping_modes(dialog):
    from PySide6.QtWidgets import QDialogButtonBox

    widget, app = dialog
    widget._new_action()
    row = widget.actions_table.rowCount() - 1
    widget.actions_table.item(row, 0).setText("小物体抓取")
    target = [21, 31, 41, 51, 61, 71]
    for column, value in enumerate(target, 1):
        widget.actions_table.cellWidget(row, column).setValue(value)
    widget.closed_action.setCurrentText("小物体抓取")
    widget.buttons.button(QDialogButtonBox.Save).click()
    app.processEvents()
    assert widget.saved
    config = TeleopConfigStore(widget.settings.path).data
    assert config["o6"]["closed_action"] == "小物体抓取"
    assert config["o6"]["actions"]["小物体抓取"] == target
    assert config["o6"]["closed"] == target
    from teleop.gello_cr.control.hand_mapping import binary_o6_action, interpolate_o6_target

    assert binary_o6_action(1, closed_action=config["o6"]["closed_action"]) == "小物体抓取"
    assert interpolate_o6_target(1, config["o6"]["open"], config["o6"]["closed"]) == tuple(target)


def test_invalid_form_stays_open_with_error_and_no_save(dialog):
    widget, _ = dialog
    original = widget.settings.path.read_bytes()
    widget.editors["planning.default_speed_scale"][0].setText("nan")
    widget._save()
    assert widget.isVisible() and not widget.saved
    assert "有限数" in widget.error_label.text()
    assert widget.settings.path.read_bytes() == original


def test_duplicate_action_names_are_rejected(dialog):
    widget, _ = dialog
    widget._new_action()
    widget.actions_table.item(widget.actions_table.rowCount() - 1, 0).setText("抓取")
    with pytest.raises(ValueError, match="重复"):
        widget._candidate()


def test_cancel_modified_draft_requires_explicit_discard(dialog, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    widget, _ = dialog
    original = widget.settings.path.read_bytes()
    widget.editors["planning.default_speed_scale"][0].setText("0.4")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Cancel)
    widget.reject()
    assert widget.isVisible()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Discard)
    widget.reject()
    assert not widget.isVisible()
    assert widget.settings.path.read_bytes() == original


def test_saving_new_session_reads_parameters_without_hardware(settings):
    from teleop.gello_cr.bootstrap.operator_app import build_operator_application

    candidate = copy.deepcopy(settings.data)
    candidate["robot"]["servoj_vmax"] = 45.0
    candidate["dataset"]["fps"] = 15
    candidate["dataset"]["recording_mode"] = "joint"
    settings.save(candidate)
    from teleop.gello_cr.bootstrap.runtime_factory import ConcreteRuntimeFactory, RuntimeFactoryPaths

    factory = ConcreteRuntimeFactory(
        RuntimeFactoryPaths.from_repo(settings.path.parent, config_path=settings.path)
    )
    operator = build_operator_application(settings.path.parent, factory=factory)
    try:
        assert operator.runtime.cr3a_lifecycle._robot_config().servoj_vmax == 45
        assert operator.runtime.store.data["dataset"]["fps"] == 15
        assert operator.runtime.cr3a_lifecycle.device is None
        assert not operator.cameras.running
    finally:
        operator.close()


def test_header_settings_save_requires_restart_and_emits_no_commands(settings):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    from teleop.gello_cr.app import ApplicationService
    from teleop.gello_cr.ui.command_port import CallbackCommandPort
    from teleop.gello_cr.ui.main_window import OperatorMainWindow
    from teleop.gello_cr.ui.presenter import OperatorUiPresenter

    app = QApplication.instance() or QApplication([])
    requests = []
    presenter = OperatorUiPresenter(
        ApplicationService(),
        runtime_snapshot=lambda: {},
        recorder_snapshot=lambda: {},
    )
    window = OperatorMainWindow(
        presenter,
        CallbackCommandPort(requests.append),
        settings_factory=lambda: settings,
    )
    window.show()
    app.processEvents()

    try:
        window.navigation.setCurrentRow(5)
        app.processEvents()
        editor = window.settings_editor
        assert editor.isEnabled() and not editor.isWindow()
        editor.editors["planning.default_speed_scale"][0].setText("0.4")
        editor.buttons.button(QDialogButtonBox.Save).click()
        assert not window.collection.connect_button.isEnabled()
        assert not window.collection.start_cameras_button.isEnabled()
        assert "重新启动" in window.state_headline.text()
        assert requests == []
        assert TeleopConfigStore(settings.path).data["planning"]["default_speed_scale"] == 0.4
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize(
    "state,readiness,recording",
    [
        ("CONNECTED", {}, {}),
        ("ROBOT_ENABLED", {}, {}),
        ("TELEOP_RUNNING", {}, {}),
        ("OFFLINE", {"cameras_running": True}, {}),
        ("OFFLINE", {"master_connected": True}, {}),
        ("OFFLINE", {"o6_connected": True}, {}),
        ("OFFLINE", {}, {"episode_active": True}),
        ("OFFLINE", {}, {"buffered_frames": 1}),
    ],
)
def test_settings_disabled_when_devices_or_episode_are_active(
    settings, state, readiness, recording
):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from teleop.gello_cr.app import ApplicationService
    from teleop.gello_cr.core.state_machine import WorkflowState, WorkflowStateMachine
    from teleop.gello_cr.ui.command_port import CallbackCommandPort
    from teleop.gello_cr.ui.main_window import OperatorMainWindow
    from teleop.gello_cr.ui.presenter import OperatorUiPresenter

    app = QApplication.instance() or QApplication([])
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState[state]))
    requests = []
    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {},
        recorder_snapshot=lambda: recording,
        readiness_snapshot=lambda: readiness,
    )
    window = OperatorMainWindow(
        presenter,
        CallbackCommandPort(requests.append),
        settings_factory=lambda: settings,
    )
    try:
        window.navigation.setCurrentRow(5)
        app.processEvents()
        assert window.settings_editor is not None and not window.settings_editor.isEnabled()
        assert requests == []
    finally:
        recording.clear()
        window.close()
        app.processEvents()


@pytest.mark.parametrize("fraction,action", [(0.0, "自定义张开"), (1.0, "自定义闭合")])
def test_running_joint_loop_dispatches_saved_action_to_fake_hand(
    settings, monkeypatch, fraction, action
):
    import threading
    import time

    from teleop.gello_cr.app.runtime import TeleopRuntime as TeleopEngine
    from teleop.gello_cr.devices.gello import GelloFeedback
    from teleop.gello_cr.tests.fakes.runtime import FakeGello, FakeO6, FakeRobot

    candidate = copy.deepcopy(settings.data)
    candidate["gello"]["startup_settle_s"] = 0
    candidate["o6"]["actions"]["自定义张开"] = [210, 211, 212, 213, 214, 215]
    candidate["o6"]["actions"]["自定义闭合"] = [31, 32, 33, 34, 35, 36]
    candidate["o6"]["open_action"] = "自定义张开"
    candidate["o6"]["closed_action"] = "自定义闭合"
    settings.save(candidate)
    gello = FakeGello()
    gello.value = GelloFeedback(time.monotonic(), (0, 0, 0, 0, 0, 0, fraction))
    hand = FakeO6()
    expected = tuple(candidate["o6"]["actions"][action])
    dispatched = threading.Event()
    set_target = hand.set_target

    def record_target(target):
        set_target(target)
        if tuple(target) == expected:
            dispatched.set()

    monkeypatch.setattr(hand, "set_target", record_target)
    engine = TeleopEngine(TeleopConfigStore(settings.path), gello, hand)
    engine.attach_robot(FakeRobot())
    try:
        engine.start_follow()
        assert dispatched.wait(1), engine.last_error
        assert expected in hand.targets
    finally:
        engine.stop_follow("offline test complete")


def test_recording_mode_selector_round_trip(dialog, settings):
    dialog, _app = dialog
    dialog.recording_mode.setCurrentIndex(dialog.recording_mode.findData("joint"))
    settings.save(dialog._candidate())
    assert TeleopConfigStore(settings.path).data["dataset"]["recording_mode"] == "joint"
    dialog.recording_mode.setCurrentIndex(dialog.recording_mode.findData("tcp"))
    settings.save(dialog._candidate())
    assert TeleopConfigStore(settings.path).data["dataset"]["recording_mode"] == "tcp"


@pytest.fixture
def profile_settings(settings, tmp_path):
    from teleop.gello_cr.app.settings import camera_streams

    profile = tmp_path / "hardware.toml"
    profile.write_text('[robot]\nip = "10.0.0.8"\n')

    class ProfileStore(TeleopConfigStore):
        read_only_paths = frozenset(
            {
                "robot.ip",
                "robot.servoj_vmax",
                "o6.port",
                "dataset.image_size",
                "dataset.camera_streams",
            }
        )
        hardware_profile_path = profile

        def __init__(self, path):
            super().__init__(path)
            self.data["robot"]["ip"] = "10.0.0.8"
            self.data["robot"]["servoj_vmax"] = [20.0] * 7
            self.data["dataset"]["camera_streams"] = [
                {
                    "name": stream.name,
                    "serial": stream.serial,
                    "mode": stream.mode,
                    "roi_norm": list(stream.roi_norm),
                }
                for stream in camera_streams(self.data["dataset"])
            ]

    return OperatorSettings(settings.path, ProfileStore), profile


@pytest.mark.parametrize(
    "path,change",
    [
        ("robot.ip", lambda data: data["robot"].__setitem__("ip", "10.0.0.9")),
        ("dataset.image_size", lambda data: data["dataset"].__setitem__("image_size", [240, 320])),
        (
            "dataset.camera_streams",
            lambda data: data["dataset"]["camera_streams"][0].__setitem__("serial", "replacement"),
        ),
        (
            "dataset.camera_streams",
            lambda data: data["dataset"]["camera_streams"][2].__setitem__(
                "roi_norm", [0.1, 0.1, 0.8, 0.8]
            ),
        ),
        ("dataset.camera_streams", lambda data: data["dataset"].pop("camera_streams")),
        ("robot.servoj_vmax", lambda data: data["robot"]["servoj_vmax"].__setitem__(6, 10.0)),
    ],
)
def test_hardware_owned_values_cannot_be_changed_programmatically(profile_settings, path, change):
    settings, profile = profile_settings
    original, hardware = settings.path.read_bytes(), profile.read_bytes()
    # Scripts may mutate the public draft directly, bypassing read-only widgets.
    candidate = settings.data
    change(candidate)

    with pytest.raises(ValueError, match=path):
        settings.save(candidate)

    assert settings.path.read_bytes() == original
    assert profile.read_bytes() == hardware
    assert not settings.path.with_suffix(".json.bak").exists()


def test_profile_draft_can_save_fps_calibration_and_safety_without_writing_hardware(
    profile_settings,
):
    settings, profile = profile_settings
    hardware = profile.read_bytes()
    candidate = copy.deepcopy(settings.data)
    candidate["dataset"]["fps"] = 15
    candidate["gello"]["joint_scale"] = 1.1
    candidate["robot"]["safety_max_command_speed_rad_s"] = 35
    settings.save(candidate)

    reloaded = OperatorSettings(settings.path, settings._store_factory)
    assert reloaded.hardware_profile_path == profile
    assert reloaded.data["robot"]["servoj_vmax"] == [20.0] * 7
    assert reloaded.data["dataset"]["fps"] == 15
    assert reloaded.data["gello"]["joint_scale"] == 1.1
    assert reloaded.data["robot"]["safety_max_command_speed_rad_s"] == 35
    assert profile.read_bytes() == hardware


def test_profile_fields_are_read_only_and_ui_save_rejects_programmatic_override(profile_settings):
    from PySide6.QtWidgets import QApplication

    from teleop.gello_cr.ui.settings_dialog import OperatorSettingsDialog

    settings, profile = profile_settings
    original = settings.path.read_bytes()
    app = QApplication.instance() or QApplication([])
    widget = OperatorSettingsDialog(settings)
    widget.show()
    app.processEvents()
    try:
        for path in ("robot.ip", "o6.port", "dataset.image_size"):
            assert all(edit.isReadOnly() for edit in widget.editors[path])
            assert str(profile) in widget.editors[path][0].toolTip()
        for name, serial, mode, roi in widget.camera_editors:
            assert name.isReadOnly()
            assert not serial.isEnabled() and not mode.isEnabled()
            assert all(edit.isReadOnly() for edit in roi)
            assert str(profile) in serial.toolTip()
        for path in ("dataset.fps", "gello.joint_scale", "robot.safety_max_command_step_rad"):
            assert not any(edit.isReadOnly() for edit in widget.editors[path])
        widget.editors["robot.ip"][0].setText("10.0.0.9")
        widget._save()
        assert not widget.saved
        assert "robot.ip" in widget.error_label.text()
        assert str(profile) in widget.error_label.text()
        assert settings.path.read_bytes() == original
    finally:
        widget.hide()
        widget.close_jobs()
        widget.deleteLater()
        app.processEvents()
