from teleop.gello_cr.tests.fakes.runtime import feedback, inverse_feedback, FakeNrcServoApi, FakeRoArm, FakeInverse3, FakeGello, FakeO6, FakeRobot
import json
import math
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.runtime import TeleopRuntime as TeleopEngine
from teleop.gello_cr.control.kinematics import GelloKinematics
from teleop.gello_cr.control.geometry import _quaternion_to_nrc_abc
from teleop.gello_cr.devices.gello import GelloFeedback
from teleop.gello_cr.devices.inverse3 import Inverse3Controller
from teleop.gello_cr.hardware.nrc_robot import NrcRobotSession as NrcRobotAdapter
from teleop.gello_cr.hardware.o6 import O6Config, O6Device
from teleop.gello_cr.motion import MotionSource
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.schema import IMAGE_KEYS, recording_schema
from teleop.gello_cr.recording.validation import validate_capture_frame
from teleop.gello_cr.recording.writers.lerobot_v3 import dataset_features as _dataset_features
from teleop.gello_cr.trajectory import ReplayOptions, TrajectoryFrame, make_trajectory






class Inverse3ControllerTests(unittest.TestCase):
    class FakeWebSocket:
        def __init__(self, frames):
            self.frames = [json.dumps(frame) for frame in frames]
            self.sent = []
            self.closed = threading.Event()

        def recv(self):
            if self.frames:
                return self.frames.pop(0)
            self.closed.wait(1.0)
            raise RuntimeError("socket closed")

        def send(self, payload):
            self.sent.append(payload)

        def close(self):
            self.closed.set()

    @staticmethod
    def frame(with_grip=True, x=0.1):
        frame = {
            "inverse3": [
                {
                    "device_id": "06DA",
                    "config": {"basis": {"permutation": "XYZ"}},
                    "state": {
                        "cursor_position": {"x": x, "y": 0.2, "z": 0.3},
                        "control_mode": "idle",
                        "body_orientation": {
                            "w": 0.7,
                            "x": 0.7,
                            "y": 0.0,
                            "z": 0.0,
                        },
                    },
                    "status": {
                        "calibrated": True,
                        "power_supply": True,
                        "ready": True,
                        "started": True,
                        "in_use": False,
                    },
                }
            ],
            "verse_grip": [],
            "wireless_verse_grip": [],
        }
        if with_grip:
            frame["wireless_verse_grip"] = [
                {
                    "device_id": "VG01",
                    "config": {"basis": {"permutation": "XYZ"}},
                    "state": {
                        "orientation": {
                            "w": 1.0,
                            "x": 0.0,
                            "y": 0.0,
                            "z": 0.0,
                        },
                        "buttons": {"a": False, "b": True, "c": False},
                    },
                    "status": {
                        "connected": True,
                        "awake": True,
                        "ready": True,
                    },
                }
            ]
        return frame

    def test_readonly_probe_stream_uses_grip_orientation_not_body_orientation(self):
        socket = self.FakeWebSocket([self.frame(), self.frame(x=0.11)])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            device_id="06DA",
            feedback_hz=20.0,
            websocket_factory=lambda _uri, _timeout: socket,
        )

        latest = controller.connect(timeout=0.5)
        self.assertEqual(latest.xyz, (110.0, 200.0, 300.0))
        self.assertEqual(latest.orientation_wxyz, (1.0, 0.0, 0.0, 0.0))
        self.assertEqual(latest.buttons, (False, True, False))
        first_probe = json.loads(socket.sent[0])
        self.assertEqual(
            first_probe["inverse3"][0]["commands"], {"probe_position": {}}
        )
        self.assertEqual(
            first_probe["wireless_verse_grip"][0]["commands"],
            {"probe_orientation": {}},
        )
        self.assertNotIn("session", first_probe)
        self.assertNotIn("set_cursor", socket.sent[0])
        controller.close()

    def test_missing_versegrip_allows_xyz_probe_but_not_fake_orientation(self):
        frame = self.frame(with_grip=False)
        socket = self.FakeWebSocket([frame, frame])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            websocket_factory=lambda _uri, _timeout: socket,
        )

        latest = controller.connect(timeout=0.5)

        self.assertEqual(latest.xyz, (100.0, 200.0, 300.0))
        self.assertIsNone(latest.orientation_wxyz)
        probe = json.loads(socket.sent[0])
        self.assertEqual(
            probe["inverse3"][0]["commands"], {"probe_position": {}}
        )
        self.assertNotIn("verse_grip", probe)
        self.assertNotIn("wireless_verse_grip", probe)
        controller.close()

    def test_busy_inverse3_fails_before_any_command(self):
        frame = self.frame()
        frame["inverse3"][0]["status"]["in_use"] = True
        frame["inverse3"][0]["state"]["control_mode"] = "force"
        socket = self.FakeWebSocket([frame])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            websocket_factory=lambda _uri, _timeout: socket,
        )

        with self.assertRaisesRegex(RuntimeError, "其他 Haply 控制会话"):
            controller.connect(timeout=0.5)
        self.assertEqual(socket.sent, [])

    def test_multiple_or_sleeping_grips_are_rejected(self):
        multiple = self.frame()
        second = json.loads(json.dumps(multiple["wireless_verse_grip"][0]))
        second["device_id"] = "VG02"
        multiple["wireless_verse_grip"].append(second)
        socket = self.FakeWebSocket([multiple])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            websocket_factory=lambda _uri, _timeout: socket,
        )
        with self.assertRaisesRegex(RuntimeError, "多个 VerseGrip"):
            controller.connect(timeout=0.5)
        self.assertEqual(socket.sent, [])

        sleeping = self.frame()
        sleeping["wireless_verse_grip"][0]["status"]["awake"] = False
        socket = self.FakeWebSocket([sleeping])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            websocket_factory=lambda _uri, _timeout: socket,
        )
        with self.assertRaisesRegex(RuntimeError, "awake"):
            controller.connect(timeout=0.5)
        self.assertEqual(socket.sent, [])

    def test_unexpected_basis_is_rejected_without_reconfiguration(self):
        frame = self.frame()
        frame["inverse3"][0]["config"]["basis"]["permutation"] = "XZ-Y"
        socket = self.FakeWebSocket([frame])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            basis="XYZ",
            websocket_factory=lambda _uri, _timeout: socket,
        )

        with self.assertRaisesRegex(RuntimeError, "basis=XZ-Y"):
            controller.connect(timeout=0.5)
        self.assertEqual(socket.sent, [])

        frame = self.frame()
        frame["wireless_verse_grip"][0]["config"]["basis"][
            "permutation"
        ] = "XZ-Y"
        socket = self.FakeWebSocket([frame])
        controller = Inverse3Controller(
            "ws://127.0.0.1:10001",
            basis="XYZ",
            websocket_factory=lambda _uri, _timeout: socket,
        )
        with self.assertRaisesRegex(RuntimeError, "VerseGrip 会话 basis=XZ-Y"):
            controller.connect(timeout=0.5)
        self.assertEqual(socket.sent, [])

    def test_relative_quaternion_converts_to_nrc_intrinsic_xyz_radians(self):
        quaternion = (
            0.9833474432563559,
            0.03427079855048211,
            -0.10602051106179562,
            0.14357217502739192,
        )
        a, b, c = _quaternion_to_nrc_abc(quaternion)
        self.assertAlmostEqual(a, 0.1, places=7)
        self.assertAlmostEqual(b, -0.2, places=7)
        self.assertAlmostEqual(c, 0.3, places=7)




class NrcRobotAdapterTests(unittest.TestCase):
    def test_power_on_from_stopped_runs_ready_then_poweron(self):
        api = FakeNrcServoApi(state=0)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.power_on(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (0, 3))
        self.assertIn(("set_servo_state_robot", 11, 1, 1), api.calls)
        self.assertIn(("set_servo_poweron_robot", 11, 1), api.calls)
        self.assertLess(
            api.calls.index(("set_servo_state_robot", 11, 1, 1)),
            api.calls.index(("set_servo_poweron_robot", 11, 1)),
        )

    def test_power_on_from_alarm_clears_and_releases_before_ready(self):
        api = FakeNrcServoApi(state=2)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.power_on(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (2, 3))
        self.assertEqual(
            [call[0] for call in api.calls],
            [
                "get_connection_status",
                "get_servo_state_robot",
                "clear_error_robot",
                "get_servo_state_robot",
                "set_servo_poweroff_robot",
                "get_servo_state_robot",
                "set_servo_state_robot",
                "get_servo_state_robot",
                "get_current_mode_robot",
                "get_servo_state_robot",
                "set_current_mode_robot",
                "get_current_mode_robot",
                "set_servo_poweron_robot",
                "get_servo_state_robot",
            ],
        )

    def test_power_on_from_alarm_already_stopped_runs_full_sequence(self):
        api = FakeNrcServoApi(state=2)
        api.clear_state_after_call = 0
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.power_on(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (2, 3))
        expected = [
            ("clear_error_robot", 11, 1),
            ("set_servo_poweroff_robot", 11, 1),
            ("set_servo_state_robot", 11, 1, 1),
            ("set_servo_poweron_robot", 11, 1),
        ]
        positions = [api.calls.index(call) for call in expected]
        self.assertEqual(positions, sorted(positions))

    def test_power_on_stops_when_alarm_remains_after_clear(self):
        api = FakeNrcServoApi(state=2)
        api.clear_state_after_call = 2
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        with self.assertRaisesRegex(RuntimeError, "清错后仍处于报警状态"):
            adapter.power_on(timeout=0.2)

        self.assertNotIn(("set_servo_poweroff_robot", 11, 1), api.calls)
        self.assertNotIn(("set_servo_poweron_robot", 11, 1), api.calls)

    def test_power_on_stops_when_6001_is_disconnected(self):
        api = FakeNrcServoApi(state=2)
        api.connection_status[11] = -2
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        with self.assertRaisesRegex(RuntimeError, "6001 示教端口未连接"):
            adapter.power_on(timeout=0.2)

        self.assertNotIn(("get_servo_state_robot", 11, 1), api.calls)
        self.assertNotIn(("clear_error_robot", 11, 1), api.calls)

    def test_power_on_reports_nrc_result_meaning(self):
        api = FakeNrcServoApi(state=1)
        api.poweron_result = -1
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        with self.assertRaisesRegex(RuntimeError, "接收控制柜响应失败"):
            adapter.power_on(timeout=0.2)

    def test_clear_servo_error_uses_command_port_and_robot_number(self):
        api = FakeNrcServoApi(state=2)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.clear_servo_error(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (2, 3))
        self.assertIn(("clear_error_robot", 11, 1), api.calls)
        self.assertIn(("set_servo_poweroff_robot", 11, 1), api.calls)
        self.assertNotIn(("clear_error_robot", 22, 1), api.calls)
        self.assertLess(
            api.calls.index(("clear_error_robot", 11, 1)),
            api.calls.index(("set_servo_poweroff_robot", 11, 1)),
        )
        self.assertIn(("set_servo_state_robot", 11, 1, 1), api.calls)
        self.assertIn(("set_servo_poweron_robot", 11, 1), api.calls)

    def test_clear_servo_error_accepts_poweroff_when_already_stopped(self):
        api = FakeNrcServoApi(state=2)
        api.clear_state_after_call = 0
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.clear_servo_error(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (2, 3))
        self.assertIn(("set_servo_poweroff_robot", 11, 1), api.calls)
        self.assertIn("伺服已经处于下电状态", transition.actions)

    def test_power_off_verifies_ready_state(self):
        api = FakeNrcServoApi(state=3)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        transition = adapter.power_off(timeout=0.2)

        self.assertEqual((transition.initial_state, transition.final_state), (3, 1))

    def test_wait_connections_ready_checks_both_ports(self):
        api = FakeNrcServoApi(state=0)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        adapter.wait_connections_ready(timeout=0.2)

        self.assertIn(("get_connection_status", 11), api.calls)
        self.assertIn(("get_connection_status", 22), api.calls)

    def test_connection_statuses_reports_both_ports(self):
        api = FakeNrcServoApi(state=0)
        api.connection_status = {11: 0, 22: -2}
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        self.assertEqual(adapter.connection_statuses(), {"6001": 0, "7000": -2})
        self.assertFalse(adapter.connections_ready())

    def test_wait_motion_stopped_requires_stable_nonmoving_state(self):
        api = FakeNrcServoApi(state=3)
        api.running_states = [2, 0, 0, 0]
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)

        stopped = adapter.wait_until_motion_stopped(timeout=0.5)

        self.assertTrue(stopped)
        running_calls = [
            call
            for call in api.calls
            if call[0] == "get_robot_running_state_robot"
        ]
        self.assertEqual(len(running_calls), 4)
        self.assertTrue(all(call[2] == 1 for call in running_calls))


class O6DeviceRecoveryTests(unittest.TestCase):
    def test_timed_out_recovery_marks_queued_request_cancelled(self):
        class AliveThread:
            def is_alive(self):
                return True

        controller = O6Device(O6Config(port="/dev/unused", sdk_root="/unused"))
        controller._thread = AliveThread()

        with self.assertRaisesRegex(TimeoutError, "恢复命令超时"):
            controller.recover_motor(3, 20, 30, timeout=0.01)

        request = controller._recovery_requests.get_nowait()
        self.assertTrue(request.cancelled.is_set())

        class Hand:
            def __init__(self):
                self.writes = []

            def get_state(self):
                return [100] * 6

            def get_fault(self):
                return [0] * 6

            def __getattr__(self, name):
                if name.startswith("set_"):
                    return lambda value: self.writes.append((name, value))
                raise AttributeError(name)

        hand = Hand()
        controller._process_recovery(hand, request)

        self.assertEqual(hand.writes, [])


class LeRobotRecorderContractTests(unittest.TestCase):
    def test_openpi_state_and_action_shapes_are_enforced(self):
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        frame = CaptureFrame(time.monotonic(), (0.,)*18, (0.,)*12,
                             {key: image for key in IMAGE_KEYS})
        validate_capture_frame(frame, recording_schema("tcp"))
        features = _dataset_features(224, 224)
        self.assertEqual(features["observation.state"]["shape"], (18,))
        self.assertEqual(features["action"]["shape"], (12,))
        self.assertEqual(
            features["action"]["names"][:6],
            [
                "cr5.delta_tcp.x.m",
                "cr5.delta_tcp.y.m",
                "cr5.delta_tcp.z.m",
                "cr5.delta_tcp.roll.rad",
                "cr5.delta_tcp.pitch.rad",
                "cr5.delta_tcp.yaw.rad",
            ],
        )












class TeleopEngineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = TeleopConfigStore(Path(self.tempdir.name) / "teleop.json")
        self.store.data["trajectory"] = {"root": str(Path(self.tempdir.name) / "trajectories")}
        self.store.data["teleop"].update(
            {
                "scale_xyz": [2.0, 2.0, 2.0],
                "max_delta_xyz_mm": [100.0, 100.0, 100.0],
                "max_tcp_speed_mm_s": 10000.0,
                "period_s": 0.01,
            }
        )
        self.store.data["replay"].update(
            {
                "servoj_period_s": 0.01,
                "mode_switch_settle_s": 0.0,
            }
        )
        self.master = FakeRoArm()
        self.hand = FakeO6()
        self.robot = FakeRobot()
        self.engine = TeleopEngine(self.store, self.master, self.hand)
        self.engine.attach_robot(self.robot)

    def tearDown(self):
        self.engine.shutdown(close_devices=False)
        self.tempdir.cleanup()

    def _save_replay(self, name="demo", *, first=None, final=None, duration=.1, joint_mask=None):
        first = first if first is not None else [0.] * 7
        final = final if final is not None else [0.] * 5 + [1., 0.]
        value = make_trajectory(name, [
            TrajectoryFrame(0., robot_joint_state=tuple(math.radians(q) for q in first[:6]),
                            hand_state=(220.,)*6),
            TrajectoryFrame(duration, robot_joint_state=tuple(math.radians(q) for q in final[:6]),
                            hand_state=(180.,)*6),
        ], joint_mask=joint_mask)
        self.engine.trajectory_store.save(value)
        self.engine.list_trajectories()
        return value

    def test_xyz_delta_is_scaled_and_rpy_is_locked(self):
        self.engine.start_follow()
        self.master.value = feedback(x=110.0, y=195.0, z=302.0, t=3.1447)
        time.sleep(0.08)
        self.engine.stop_follow("test")

        target = self.robot.ik_targets[-1]
        self.assertAlmostEqual(target[0], 520.0, places=3)
        self.assertAlmostEqual(target[1], 0.0, places=3)
        self.assertAlmostEqual(target[2], 304.0, places=3)
        self.assertEqual(target[3:7], [1.1, 2.2, 3.3, 0.0])
        self.assertEqual(self.hand.targets[-1], (90, 99, 50, 50, 50, 50))
        self.assertTrue(self.master.released)
        self.assertTrue(self.master.held)

    def test_gello_xyz_j6_tcp_ik_mode_uses_fk_and_maps_tcp_c(self):
        gello = FakeGello()
        self.master.connected = False
        self.engine.set_master(gello)
        self.store.data["gello"]["control_mode"] = "tcp_6d"
        urdf = Path(__file__).resolve().parents[3] / (
            "vendor/gello/gello/factr/urdf/"
            "yam_active_gello/robot.urdf"
        )
        self.store.data["gello"]["kinematics_urdf"] = os.path.relpath(
            urdf, self.store.path.parent
        )
        self.store.data["gello"]["startup_settle_s"] = 0.0
        self.store.data["robot"]["safety_max_command_speed_rad_s"] = 100.0
        self.store.data["robot"]["safety_max_tracking_error_rad"] = 10.0
        self.store.data["teleop"]["max_master_jump_mm"] = 1000.0
        self.store.data["teleop"]["max_tcp_speed_mm_s"] = 10000.0

        self.engine.start_follow()
        time.sleep(0.08)
        gello.value = GelloFeedback(
            time.monotonic(), (0.12, 0.0, 0.0, 0.0, 0.0, 0.10, 0.0)
        )
        deadline = time.monotonic() + 0.8
        while not self.robot.ik_targets and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(self.robot.ik_targets)
        target = self.robot.ik_targets[-1]
        self.assertNotEqual(target[:3], [500.0, 10.0, 300.0])
        self.assertGreater(
            sum(abs(value - reference) for value, reference in zip(target[3:6], [1.1, 2.2, 3.3])),
            1e-6,
        )
        self.assertTrue(self.robot.servoj_targets)
        self.assertAlmostEqual(self.robot.servoj_targets[-1][5], 0.0, places=6)
        self.assertTrue(
            np.isfinite(
                GelloKinematics(
                    self.store.path.parent / self.store.data["gello"]["kinematics_urdf"]
                )
                .position(gello.value.arm_joints_rad)
            ).all()
        )
        self.engine.stop_follow("test")

    def test_gello_joint_mode_maps_relative_joint_targets(self):
        gello = FakeGello()
        self.master.connected = False
        self.engine.set_master(gello)
        self.store.data["gello"]["control_mode"] = "joint"
        self.store.data["gello"]["startup_settle_s"] = 0.0
        self.store.data["robot"]["safety_max_command_speed_rad_s"] = 100.0
        self.store.data["robot"]["safety_max_tracking_error_rad"] = 10.0

        self.engine.start_follow()
        time.sleep(0.08)
        gello.value = GelloFeedback(
            time.monotonic(), (0.10, -0.20, 0.05, 0.0, 0.0, 0.15, 0.0)
        )
        expected = [math.degrees(value) for value in gello.value.arm_joints_rad]
        deadline = time.monotonic() + 0.8
        while (
            not any(
                abs(target[0] - expected[0]) < 1e-6
                for target in self.robot.servoj_targets
            )
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        target = next(
            target
            for target in self.robot.servoj_targets
            if abs(target[0] - expected[0]) < 1e-6
        )
        for actual, wanted in zip(target[:6], expected):
            self.assertAlmostEqual(actual, wanted, places=6)
        self.assertEqual(target[6], 0.0)
        self.engine.stop_follow("test")

    def test_gello_follow_opens_servoj_before_first_command(self):
        gello = FakeGello()
        self.master.connected = False
        self.engine.set_master(gello)
        self.store.data["gello"]["control_mode"] = "joint"
        self.store.data["gello"]["startup_settle_s"] = 0.0
        self.store.data["robot"]["safety_max_command_speed_rad_s"] = 100.0
        self.store.data["robot"]["safety_max_tracking_error_rad"] = 10.0

        self.engine.start_follow()
        deadline = time.monotonic() + 0.8
        while "send" not in self.robot.servoj_events and time.monotonic() < deadline:
            time.sleep(0.005)

        self.assertIn("send", self.robot.servoj_events)
        self.assertLess(
            self.robot.servoj_events.index("open"),
            self.robot.servoj_events.index("send"),
        )
        self.engine.stop_follow("test")

    def test_inverse3_follow_updates_xyz_and_abc_in_native_radians(self):
        q_origin = (
            0.7071067811865476,
            0.0,
            0.0,
            0.7071067811865475,
        )
        q_current = (
            0.5938107868374524,
            -0.050734708264935056,
            -0.09920093636838305,
            0.7968525039405936,
        )
        inverse = FakeInverse3(inverse_feedback(orientation=q_origin))
        self.master.connected = False
        self.engine.set_master(inverse)
        self.store.data["teleop"].update(
            {
                "scale_rpy": [1.0, 1.0, 1.0],
                "max_delta_rpy_rad": [1.0, 1.0, 1.0],
                "max_tcp_angular_speed_rad_s": 100.0,
                "max_master_angular_jump_rad": 1.0,
            }
        )
        self.robot.tcp = [500.0, 10.0, 300.0, 3.10, -3.10, 3.05, 0.0]

        self.engine.start_follow()
        inverse.value = inverse_feedback(
            x=110.0,
            y=195.0,
            z=302.0,
            orientation=q_current,
        )
        expected = [
            520.0,
            0.0,
            304.0,
            -3.069890964451087,
            -2.8896455007655124,
            -2.938663011008991,
            0.0,
        ]
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if self.robot.ik_targets and all(
                math.isclose(actual, wanted, abs_tol=1e-6)
                for actual, wanted in zip(self.robot.ik_targets[-1], expected)
            ):
                break
            time.sleep(0.005)
        self.engine.stop_follow("test")

        for actual, wanted in zip(self.robot.ik_targets[-1], expected):
            self.assertAlmostEqual(actual, wanted, places=6)
        self.assertEqual(self.hand.targets, [])

    def test_inverse3_without_grip_cannot_start_six_d_follow(self):
        inverse = FakeInverse3(inverse_feedback(orientation=None))
        self.master.connected = False
        self.engine.set_master(inverse)

        with self.assertRaisesRegex(RuntimeError, "VerseGrip"):
            self.engine.start_follow()

        self.assertFalse(self.robot.servoj_open)
        self.assertEqual(self.engine.state, "idle")

    def test_joint_dataset_records_feedback_and_sent_absolute_targets_in_radians(self):
        self.store.data["dataset"]["recording_mode"] = "joint"
        self.store.data["gello"]["control_mode"] = "joint"
        self.master.master_type = "gello"
        self.engine._set_state("following")
        now = time.monotonic()
        actual = [0, 90, -90, 180, -180, 45]
        target = [10, 100, -80, 190, -170, 55, 0]
        self.engine._gello_telemetry = {
            "sent_count": 1, "feedback_at": now, "command_at": now,
            "tracking_error_deg": 10, "actual_deg": actual,
            "target_full_deg": target,
        }
        sample = self.engine.dataset_sample()
        self.assertEqual(sample["recording_mode"], "joint")
        self.assertEqual(len(sample["observation_state"]), 12)
        for result, degrees in zip(sample["observation_state"][:6], actual):
            self.assertAlmostEqual(result, math.radians(degrees))
        for result, degrees in zip(sample["action"][:6], target):
            self.assertAlmostEqual(result, math.radians(degrees))
        self.engine._set_state("idle")
        with self.assertRaisesRegex(RuntimeError, "已下发目标"):
            self.engine.dataset_sample()

    def test_joint_dataset_records_home_target_during_home_motion(self):
        self.store.data["dataset"]["recording_mode"] = "joint"
        self.engine._set_state("preset")
        self.engine._set_dataset_target_joints([10, 20, 30, 40, 50, 60, 0])
        self.robot.joints = [1, 2, 3, 4, 5, 6, 0]

        sample = self.engine.dataset_sample()

        self.assertEqual(sample["recording_mode"], "joint")
        for result, degrees in zip(sample["observation_state"][:6], [1, 2, 3, 4, 5, 6]):
            self.assertAlmostEqual(result, math.radians(degrees))
        for result, degrees in zip(sample["action"][:6], [10, 20, 30, 40, 50, 60]):
            self.assertAlmostEqual(result, math.radians(degrees))

    def test_dataset_tcp_rpy_uses_native_rad_and_shortest_delta(self):
        self.robot.tcp = [500.0, 10.0, 300.0, 3.10, -3.10, 0.25, 0.0]
        self.engine._set_dataset_target_tcp(
            [500.0, 10.0, 300.0, -3.10, 3.10, 0.35, 0.0]
        )
        self.engine._set_state("following")

        sample = self.engine.dataset_sample()

        self.assertEqual(sample["observation_state"][9:12], [3.10, -3.10, 0.25])
        expected_delta = [
            0.08318530717958605,
            -0.08318530717958694,
            0.1,
        ]
        for actual, wanted in zip(sample["action"][3:6], expected_delta):
            self.assertAlmostEqual(actual, wanted, places=9)
        self.engine._set_state("idle")

    def test_xyz_scale_change_rebases_without_target_jump(self):
        self.engine.start_follow()
        self.master.value = feedback(x=110.0)
        deadline = time.monotonic() + 0.5
        while (
            not self.robot.ik_targets
            or not math.isclose(self.robot.ik_targets[-1][0], 520.0, abs_tol=0.01)
        ) and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertAlmostEqual(self.robot.ik_targets[-1][0], 520.0, places=2)

        self.store.update_runtime({"teleop": {"scale_xyz": [4.0, 2.0, 2.0]}})
        time.sleep(0.04)
        self.assertAlmostEqual(self.robot.ik_targets[-1][0], 520.0, places=2)

        self.master.value = feedback(x=111.0)
        deadline = time.monotonic() + 0.5
        while not math.isclose(
            self.robot.ik_targets[-1][0], 524.0, abs_tol=0.01
        ) and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertAlmostEqual(self.robot.ik_targets[-1][0], 524.0, places=2)
        self.engine.stop_follow("test")

    def test_relative_limit_causes_fault_and_stops_servoj(self):
        self.store.data["teleop"]["max_delta_xyz_mm"] = [5.0, 5.0, 5.0]
        self.engine.start_follow()
        self.master.value = feedback(x=104.0)
        deadline = time.monotonic() + 1.0
        while self.engine.state != "fault" and time.monotonic() < deadline:
            time.sleep(0.01)

        self.assertEqual(self.engine.state, "fault")
        self.assertIn("X 相对位移", self.engine.last_error)
        # The fault latch is published before producer cleanup completes.
        self.engine._follow_thread.join(timeout=1.0)
        self.assertFalse(self.engine._follow_thread.is_alive())
        self.assertFalse(self.robot.servoj_open)
        self.assertTrue(self.master.held)

    def test_software_estop_during_follow_start_cannot_publish_following(self):
        def open_then_estop(vmax, amax, jmax):
            self.robot.servoj_open = True
            self.engine.emergency_stop("启动阶段测试急停")

        self.robot.open_servoj = open_then_estop

        with self.assertRaisesRegex(RuntimeError, "启动已被软件紧急停止"):
            self.engine.start_follow()

        self.assertEqual(self.engine.state, "fault")
        self.assertFalse(self.robot.servoj_open)
        self.assertIsNone(self.engine._follow_thread)

    def test_shutdown_cancels_inflight_master_connection(self):
        connect_started = threading.Event()
        connect_released = threading.Event()

        class SlowMaster(FakeRoArm):
            def __init__(self):
                super().__init__()
                self.connected = False

            def connect(self):
                connect_started.set()
                connect_released.wait(1.0)
                self.connected = True
                return self.value

            def close(self, hold=True):
                del hold
                self.connected = False
                connect_released.set()

        slow_master = SlowMaster()
        engine = TeleopEngine(self.store, slow_master, self.hand)
        failures = []

        def connect_devices():
            try:
                engine.connect_devices()
            except Exception as exc:
                failures.append(str(exc))

        thread = threading.Thread(target=connect_devices)
        thread.start()
        self.assertTrue(connect_started.wait(0.5))
        engine.shutdown()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertFalse(slow_master.connected)
        self.assertEqual(engine.state, "closed")
        self.assertTrue(any("退出" in failure for failure in failures))

    def test_shutdown_cancels_inflight_follow_start(self):
        servo_check_started = threading.Event()
        servo_check_released = threading.Event()
        failures = []

        def blocking_servo_state():
            servo_check_started.set()
            servo_check_released.wait(1.0)
            return 3

        self.robot.servo_state = blocking_servo_state

        def start_follow():
            try:
                self.engine.start_follow()
            except Exception as exc:
                failures.append(str(exc))

        thread = threading.Thread(target=start_follow)
        thread.start()
        self.assertTrue(servo_check_started.wait(0.5))
        self.engine.shutdown()
        servo_check_released.set()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual(self.engine.state, "closed")
        self.assertFalse(self.robot.servoj_open)
        self.assertTrue(any("退出" in failure for failure in failures))







    def test_home_motion_state_rejects_a_second_xyz_follow_start(self):
        self.engine._set_state("preset")

        with self.assertRaisesRegex(RuntimeError, "其他运动正在执行"):
            self.engine.start_follow()

        self.assertEqual(self.engine.state, "preset")
        self.assertFalse(self.robot.servoj_open)

    def test_stop_follow_timeout_never_publishes_idle(self):
        class StuckThread:
            def join(self, timeout=None):
                return None

            def is_alive(self):
                return True

        self.engine._follow_thread = StuckThread()
        self.engine._set_state("following")

        with self.assertRaisesRegex(TimeoutError, "未能在 2 秒内停止"):
            self.engine.stop_follow("test")

        self.assertEqual(self.engine.state, "fault")
        self.engine._follow_thread = None



    def test_robot_disconnect_detaches_adapter_and_stops_follow(self):
        self.engine.start_follow()

        detached = self.engine.detach_robot(self.robot, "6001=-2, 7000=0")
        thread = self.engine._follow_thread
        if thread is not None:
            thread.join(timeout=0.5)

        self.assertTrue(detached)
        self.assertIsNone(self.engine.robot)
        self.assertEqual(self.engine.state, "fault")
        self.assertIn("CR5 连接断开", self.engine.last_error)
        self.assertTrue(self.master.held)

    def test_home_is_a_dedicated_persistent_preset(self):
        saved = self.engine.save_home()
        self.assertIn("HOME", self.store.data["presets"])
        self.assertEqual(saved["robot_tcp"], self.robot.tcp)

    def test_home_needs_only_enabled_robot(self):
        self.engine.save_home()
        target = self.robot.joints.copy()
        self.robot.joints = [20.0] * 7
        self.master.connected = False
        self.hand.connected = False
        self.engine.return_home()
        self.assertTrue(self.robot.stopped)
        self.assertEqual(self.robot.movej_targets, [target])
        self.assertEqual(self.engine.state, "idle")
        self.assertIsNone(self.engine._home_thread)
        self.assertEqual(self.hand.targets, [])

    def test_home_also_returns_o6_when_connected(self):
        self.engine.save_home()
        target = self.robot.joints.copy()
        home_o6 = tuple(self.store.data["o6"]["actions"][self.store.data["o6"]["open_action"]])
        self.robot.joints = [20.0] * 7
        self.hand.set_target((0, 0, 0, 0, 0, 0))
        self.engine.return_home()
        self.assertEqual(self.robot.movej_targets, [target])
        self.assertEqual(self.hand.targets[-1], home_o6)
        self.assertEqual(self.hand.position, home_o6)
        self.assertEqual(self.engine.state, "idle")

    def test_home_returns_o6_and_clears_manual_override(self):
        self.engine.save_home()
        home_o6 = tuple(self.store.data["o6"]["actions"][self.store.data["o6"]["open_action"]])
        self.engine.execute_o6_action("抓取")
        self.assertTrue(self.engine.o6_manual_override)
        self.engine.return_home()
        self.assertEqual(self.hand.position, home_o6)
        self.assertFalse(self.engine.o6_manual_override)
        self.assertEqual(self.engine.state, "idle")

    def test_home_preempts_running_replay_and_stays_stopped(self):
        self.engine.save_home()
        self.engine._set_state("replay")
        lease = self.engine.motion.acquire(MotionSource.REPLAY)
        self.engine.return_home()
        self.assertFalse(lease.active)
        self.assertEqual(len(self.robot.movej_targets), 1)
        self.assertEqual(self.engine.state, "idle")
        self.assertIsNone(self.engine.motion.current_owner)
        self.assertTrue(self.engine._follow_stop.is_set())

    def test_home_stop_during_servo_check_prevents_move(self):
        self.engine.save_home()

        def servo_state():
            self.engine.emergency_stop("test stop during status check")
            return 3

        self.robot.servo_state = servo_state
        with self.assertRaisesRegex(RuntimeError, "已被停止|idle"):
            self.engine.return_home()
        self.assertEqual(self.robot.movej_targets, [])
        self.assertEqual(self.engine.state, "fault")

    def test_home_never_enables_connected_robot(self):
        self.engine.save_home()
        self.robot.servo_state = lambda: 0
        enabled = []
        self.robot.power_on = lambda: enabled.append(True)
        with self.assertRaisesRegex(RuntimeError, "使能"):
            self.engine.return_home()
        self.assertEqual(enabled, [])
        self.assertEqual(self.robot.movej_targets, [])
        self.assertEqual(self.engine.state, "idle")

    def test_home_rejects_real_nrc_ready_state_before_waiting_for_stop(self):
        self.engine.save_home()
        api = FakeNrcServoApi(state=1)
        adapter = NrcRobotAdapter(api, command_fd=11, servo_fd=22, robot_num=1)
        self.engine.attach_robot(adapter)
        try:
            with self.assertRaisesRegex(RuntimeError, "使能"):
                self.engine.return_home()
            self.assertEqual(self.engine.state, "idle")
            commands = [call[0] for call in api.calls]
            self.assertNotIn("set_servo_poweron_robot", commands)
            self.assertNotIn("get_robot_running_state_robot", commands)
        finally:
            self.engine.attach_robot(self.robot)

    def test_home_cannot_overlap_another_home_or_follow(self):
        self.engine.save_home()
        value = self._save_replay()
        move = self.robot.movej

        def during_move(*args):
            with self.assertRaisesRegex(RuntimeError, "HOME 回位正在执行"):
                self.engine.return_home()
            with self.assertRaisesRegex(RuntimeError, "HOME 回位正在执行"):
                self.engine.start_follow()
            with self.assertRaisesRegex(RuntimeError, "不允许轨迹回放"):
                self.engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions())
            move(*args)

        self.robot.movej = during_move
        self.engine.return_home()
        self.assertEqual(len(self.robot.movej_targets), 1)

    def test_home_stop_confirmation_failure_latches_fault(self):
        self.engine.save_home()
        confirmations = iter([True, False])
        self.robot.wait_until_motion_stopped = lambda *a, **kw: next(confirmations)
        with self.assertRaisesRegex(RuntimeError, "停止未确认"):
            self.engine.return_home()
        self.assertEqual(len(self.robot.movej_targets), 1)
        self.assertEqual(self.engine.state, "fault")
        self.assertIsNone(self.engine.motion.current_owner)

    def test_home_preserves_active_and_pending_episode(self):
        self.engine.save_home()
        for episode in (
            {"episode_active": True}, {"episode_pending": True, "buffered_frames": 3},
        ):
            self.engine.set_recording_snapshot(lambda episode=episode: episode)
            before = dict(episode)
            self.engine.return_home()
            self.assertEqual(episode, before)
            self.assertEqual(self.engine.state, "idle")
        self.assertEqual(len(self.robot.movej_targets), 2)

    def test_home_does_not_publish_recording_actions(self):
        self.store.data["dataset"]["recording_mode"] = "joint"
        self.engine.save_home()
        self.engine.return_home()
        self.assertIsNone(self.engine._dataset_target_joints_deg)
        self.assertIsNone(self.engine._dataset_target_tcp_controller)

    def test_home_missing_target_never_moves(self):
        with self.assertRaisesRegex(RuntimeError, "尚未保存"):
            self.engine.return_home()
        self.assertEqual(self.robot.movej_targets, [])

    def test_home_returns_o6_control_to_m5_after_quick_action(self):
        self.engine.save_home()
        self.engine.execute_o6_action("抓取")
        self.assertTrue(self.engine.o6_manual_override)

        self.engine.return_home()

        self.assertIsNone(self.engine._home_thread)
        self.assertEqual(self.engine.state, "idle")
        self.assertFalse(self.engine.o6_manual_override)
        self.engine.start_follow()
        self.master.value = feedback(t=3.1447)
        time.sleep(0.05)
        self.assertEqual(self.hand.targets[-1], (90, 99, 50, 50, 50, 50))

    def test_o6_motor_three_recovery_uses_its_profile_and_clears_fault_state(self):
        self.hand.fault = (0, 0, 1, 0, 0, 0)
        self.engine._set_state("fault", "O6 故障")

        result = self.engine.recover_o6_motor(3)

        self.assertEqual(self.hand.recoveries, [(3, 20, 30)])
        self.assertEqual(result["motor_name"], "食指弯曲")
        self.assertEqual(self.hand.fault, (0, 0, 0, 0, 0, 0))
        self.assertEqual(self.engine.state, "idle")

    def test_o6_recovery_refuses_overtemperature_fault(self):
        self.hand.fault = (0, 0, 2, 0, 0, 0)

        with self.assertRaisesRegex(RuntimeError, "温度过高"):
            self.engine.recover_o6_motor(3)

        self.assertEqual(self.hand.recoveries, [])

    def test_o6_recovery_cannot_overwrite_software_estop(self):
        entered = threading.Event()

        def wait_for_estop(
            motor_number, speed, torque, timeout=4.0, stop_event=None
        ):
            entered.set()
            while stop_event is not None and not stop_event.wait(0.005):
                pass
            raise RuntimeError("恢复已停止")

        self.hand.recover_motor = wait_for_estop
        errors = []

        def recover():
            try:
                self.engine.recover_o6_motor(3)
            except Exception as exc:
                errors.append(str(exc))

        thread = threading.Thread(target=recover)
        thread.start()
        self.assertTrue(entered.wait(0.5))
        self.engine.emergency_stop("测试急停")
        thread.join(timeout=0.5)

        self.assertFalse(thread.is_alive())
        self.assertTrue(errors)
        self.assertEqual(self.engine.state, "fault")

    def test_o6_quick_action_uses_configured_target_and_profile(self):
        target = self.engine.execute_o6_action("中指")

        self.assertEqual(target, (91, 132, 0, 250, 0, 0))
        self.assertEqual(self.hand.targets[-1], target)
        self.assertEqual(self.hand.profiles[-1], ((20,) * 6, (30,) * 6))
        self.assertEqual(self.engine.state, "idle")
        self.assertTrue(self.engine.o6_manual_override)

    def test_o6_quick_action_rejects_unknown_name(self):
        with self.assertRaisesRegex(ValueError, "未配置 O6 快捷动作"):
            self.engine.execute_o6_action("不存在")

    def test_software_estop_cancels_o6_quick_action(self):
        errors = []
        waiting_for_arrival = threading.Event()

        def wait_for_estop(target, tolerance=6, timeout=15.0, stop_event=None):
            waiting_for_arrival.set()
            if stop_event is not None:
                stop_event.wait(timeout)
            return False

        self.hand.wait_until_position = wait_for_estop

        def run_action():
            try:
                self.engine.execute_o6_action("抓取")
            except Exception as exc:
                errors.append(str(exc))

        thread = threading.Thread(target=run_action)
        thread.start()
        try:
            self.assertTrue(waiting_for_arrival.wait(0.5))
            self.assertIn(tuple(self.store.data["o6"]["actions"]["抓取"]), self.hand.targets)
            self.engine.emergency_stop("测试急停")
            thread.join(timeout=0.5)
        finally:
            self.engine._hand_action_stop.set()
            thread.join(timeout=0.5)

        self.assertFalse(thread.is_alive())
        self.assertTrue(any("软件紧急停止" in message for message in errors))
        self.assertEqual(self.engine.state, "fault")

    def test_software_estop_cancels_o6_quick_action_before_target_dispatch(self):
        action_announced = threading.Event()
        finish_announcement = threading.Event()
        errors = []
        initial_position = self.hand.position
        grasp = tuple(self.store.data["o6"]["actions"]["抓取"])
        original_event = self.engine.hand_actions._event

        def pause_at_announcement(level, message):
            original_event(level, message)
            if "开始执行 O6 快捷动作" in message:
                action_announced.set()
                if not finish_announcement.wait(1.0):
                    raise TimeoutError("test did not release the hand action announcement")

        self.engine.hand_actions._event = pause_at_announcement

        def run_action():
            try:
                self.engine.execute_o6_action("抓取")
            except Exception as exc:
                errors.append(str(exc))

        thread = threading.Thread(target=run_action)
        thread.start()
        try:
            self.assertTrue(action_announced.wait(0.5))
            self.assertTrue(self.engine.o6_action_active)
            self.engine.emergency_stop("测试启动中急停")
            finish_announcement.set()
            thread.join(timeout=0.5)
        finally:
            finish_announcement.set()
            self.engine._hand_action_stop.set()
            thread.join(timeout=0.5)
            self.engine.hand_actions._event = original_event

        self.assertFalse(thread.is_alive())
        self.assertTrue(any("停止" in message for message in errors))
        self.assertNotIn(grasp, self.hand.targets)
        self.assertEqual(self.hand.profiles, [])
        self.assertTrue(self.hand.targets)
        self.assertTrue(all(target == initial_position for target in self.hand.targets))
        self.assertFalse(self.engine.o6_action_active)
        self.assertEqual(self.engine.state, "fault")


    def test_trajectory_record_and_replay_synchronizes_arm_and_hand(self):
        self.store.data["replay"]["max_joint_speed_deg_s"] = 10000.0
        # Capture deliberately supplied hand feedback while the new coupled
        # follow session runs; manual hand override keeps M5 from replacing it.
        self.engine._o6_manual_override = True
        first_hand = (200, 201, 202, 203, 204, 205)
        final_hand = (120, 121, 122, 123, 124, 125)
        sampled_final = threading.Event()
        sample = self.engine.trajectory_source.sample

        def observed_sample():
            frame = sample()
            if frame.hand_state == final_hand:
                sampled_final.set()
            return frame

        self.engine.trajectory_source.sample = observed_sample
        self.hand.position = first_hand
        self.engine.start_trajectory_recording("synchronized demo")
        self.robot.joints = [2., 3., 4., 5., 6., 7., 0.]
        self.hand.position = final_hand
        self.assertTrue(sampled_final.wait(1.))
        metadata = self.engine.stop_trajectory_recording()
        path = self.engine.save_trajectory()
        value = self.engine.trajectory_store.load(metadata.trajectory_id)

        self.assertTrue((path / "trajectory.parquet").is_file())
        self.assertGreaterEqual(len(value.frames), 2)
        self.assertEqual(value.frames[-1].hand_state, final_hand)
        self.assertEqual(self.engine.snapshot()["trajectory"]["items"][0]["trajectory_id"],
                         metadata.trajectory_id)
        self.hand.targets.clear()
        self.robot.joints = [0.] * 7
        self.engine.replay_trajectory(metadata.trajectory_id, ReplayOptions())
        self.engine._replay_thread.join(1.)

        self.assertFalse(self.engine.replaying)
        self.assertEqual(self.engine.state, "idle")
        self.assertTrue(self.robot.servoj_targets)
        self.assertEqual(self.hand.targets[-1], final_hand)

    def test_named_trajectories_use_independent_ids_and_storage(self):
        values = [self._save_replay(f"demo {i}", final=[0.] * 5 + [float(i), 0.])
                  for i in (1, 2, 3)]
        self.assertEqual(len({v.metadata.trajectory_id for v in values}), 3)
        for i, value in enumerate(values, 1):
            loaded = self.engine.trajectory_store.load(value.metadata.trajectory_id)
            self.assertEqual(loaded.name, f"demo {i}")
            self.assertAlmostEqual(loaded.frames[-1].robot_joint_state[5], math.radians(i))
        self.assertEqual(len(self.engine.snapshot()["trajectory"]["items"]), 3)

        self.engine.replay_trajectory(values[-1].metadata.trajectory_id, ReplayOptions())
        self.engine._replay_thread.join(1.)
        self.assertFalse(self.engine.replaying)
        self.assertAlmostEqual(self.robot.servoj_targets[-1][5], 3.)
        self.assertEqual(self.hand.targets[-1], (180,) * 6)

    def test_cancelled_trajectory_worker_never_sends_servoj(self):
        value = self._save_replay()
        lease = self.engine.motion.acquire(MotionSource.REPLAY)
        self.engine.motion.cancel_all("test stop")
        self.engine._set_state("fault", "测试急停")
        self.engine._play_trajectory_worker(value, ReplayOptions(), lease,
                                            self.engine.stop_generation, None)

        self.assertEqual(self.robot.servoj_targets, [])
        self.assertEqual(self.engine.state, "fault")

    def test_trajectory_replay_keeps_dataset_sampling_and_holds_unselected_joints(self):
        value = self._save_replay(
            first=[90.] * 5 + [15., 0.], final=[80.] * 5 + [25., 0.], duration=.15,
            joint_mask=(False,) * 5 + (True,),
        )
        self.robot.joints = [1., 2., 3., 4., 5., 6., 0.]
        self.engine._set_dataset_target_tcp(self.robot.tcp_position())
        self.engine._set_state("following")
        self.engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions())
        samples = []
        deadline = time.monotonic() + 1.
        while self.engine.replaying and time.monotonic() < deadline:
            try:
                samples.append(self.engine.dataset_sample())
            except RuntimeError:
                if self.engine.replaying:
                    raise
            time.sleep(.005)
        self.engine._replay_thread.join(1.)

        self.assertFalse(self.engine.replaying)
        self.assertEqual(self.engine.state, "idle")
        self.assertTrue(samples)
        self.assertTrue(all(len(sample["observation_state"]) == 18 for sample in samples))
        self.assertTrue(all(len(sample["action"]) == 12 for sample in samples))
        self.assertTrue(any(sample["action"][3] > 0. for sample in samples))
        self.assertTrue(all(math.isclose(sample["observation_state"][0], math.radians(1.))
                            for sample in samples))
        self.assertTrue(all(math.isclose(sample["observation_state"][6], .5)
                            for sample in samples))
        self.assertAlmostEqual(self.robot.servoj_targets[0][5], 6.)
        self.assertAlmostEqual(self.robot.servoj_targets[-1][5], 16.)
        self.assertTrue(all(np.allclose(target[:5], [1., 2., 3., 4., 5.])
                            for target in self.robot.servoj_targets))

    def test_trajectory_replay_preempts_xyz_follow_and_finishes_idle(self):
        value = self._save_replay(first=[0.] * 5 + [10., 0.],
                                  final=[0.] * 5 + [20., 0.],
                                  joint_mask=(False,) * 5 + (True,))
        self.engine.start_follow()
        self.engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions())
        self.engine._replay_thread.join(1.)

        self.assertFalse(self.engine.replaying)
        self.assertEqual(self.engine.state, "idle")
        self.assertFalse(self.engine._follow_thread.is_alive())
        self.assertIsNone(self.engine.motion.current_owner)
        self.assertEqual(self.hand.position, (180,) * 6)
        self.assertAlmostEqual(self.robot.servoj_targets[-1][5], 10.)

    def test_relative_replay_from_preset_does_not_jump_to_recorded_origin(self):
        self.store.data["motion"] = {"max_command_delta_rad": math.radians(90.)}
        self.store.data["replay"]["max_joint_speed_deg_s"] = 10000.
        value = self._save_replay(
            first=[2.17, -7.75, -7.64, 30.58, -1.75, -173.40, 0.],
            final=[2.17, -7.75, -7.64, 30.58, -1.75, 9.10, 0.], duration=.05,
            joint_mask=(False,) * 5 + (True,),
        )
        preset_joints = [2.96, -16.54, -22.42, 97.59, -4.59, -5.75, 0.]
        self.robot.joints = list(preset_joints)
        self.engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions())
        self.engine._replay_thread.join(1.)

        self.assertFalse(self.engine.replaying)
        self.assertEqual(self.engine.state, "idle")
        self.assertEqual(self.robot.movej_targets, [])
        self.assertAlmostEqual(self.robot.servoj_targets[0][5], -5.75, places=3)
        self.assertAlmostEqual(self.robot.servoj_targets[-1][5], -5.75 + 182.5, places=3)
        self.assertTrue(all(np.allclose(target[:5], preset_joints[:5])
                            for target in self.robot.servoj_targets))

    def test_old_arm_only_recording_imports_without_modifying_source(self):
        path = Path(self.tempdir.name) / "old_arm.json"
        path.write_text(json.dumps({"version": 1, "frames": [
            {"t": 0., "robot_joints_deg": [0.] * 7},
            {"t": .1, "robot_joints_deg": [1.] * 6 + [0.]},
        ]}), encoding="utf-8")
        destination = self.engine.import_trajectory(path)
        value = self.engine.trajectory_store.load(destination.name)
        self.assertIsNone(value.metadata.hand_type)
        self.assertIsNone(value.frames[0].hand_state)

        self.engine.replay_trajectory(value.metadata.trajectory_id, ReplayOptions(hand_enabled=False))
        self.engine._replay_thread.join(1.)
        self.assertFalse(self.engine.replaying)
        self.assertEqual(self.engine.state, "idle")
        self.assertAlmostEqual(self.robot.servoj_targets[-1][0], 1.)
        self.assertEqual(json.loads(path.read_text())["version"], 1)


if __name__ == "__main__":
    unittest.main()
