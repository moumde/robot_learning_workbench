"""Lease-bound compatibility view for an external policy deployment adapter.

The deployment receives read access and guarded native-unit commands, without
the NRC API object, socket descriptors, or an unguarded device/session handle.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from .coordinator import MotionLease
from .types import JointTarget, MotionPreempted, TcpTarget


class PolicyMotionRobot:
    def __init__(self, robot: Callable[[], Any]) -> None:
        self._robot = robot
        self._lease: MotionLease | None = None

    def bind(self, lease: MotionLease) -> None:
        if self._lease is not None:
            raise RuntimeError("Policy motion view is already bound")
        self._lease = lease

    def lease(self) -> MotionLease:
        if self._lease is None:
            raise MotionPreempted("Policy has not acquired motion control")
        self._lease.check()
        return self._lease

    def _session(self) -> Any:
        session = self._robot()
        if session is None:
            raise MotionPreempted("Robot session is disconnected")
        return session

    @property
    def motion_mode(self) -> str:
        return self._session().motion_mode

    @property
    def movej_period_s(self) -> float:
        return self._session().movej_period_s

    @property
    def servoj_open(self) -> bool:
        return self._session().servoj_open

    @property
    def controller_job_warning(self) -> str:
        return self._session().controller_job_warning

    def joint_position(self):
        return self._session().joint_position()

    def tcp_position(self):
        return self._session().tcp_position()

    def servo_state(self):
        return self._session().servo_state()

    def running_state(self):
        return self._session().running_state()

    def inverse_kinematics(self, tcp):
        return self._session().inverse_kinematics(tcp)

    def forward_kinematics(self, joints):
        return self._session().forward_kinematics(joints)

    def clear_movej_busy_if_stopped(self):
        self.lease()
        return self._session().clear_movej_busy_if_stopped()

    def open_servoj(self, vmax, amax, jmax):
        return self.lease().open_servo(vmax, amax, jmax)

    def send_servoj(self, joints):
        return self.lease().servo_joint(JointTarget.from_degrees(joints))

    def movej(self, joints, velocity, acc, dec):
        return self.lease().move_joint(JointTarget.from_degrees(joints), velocity, acc, dec)

    def movel(self, tcp, velocity, acc, dec):
        return self.lease().move_tcp(TcpTarget.from_native(tcp), velocity, acc, dec)

    def stop_motion(self):
        if self._lease is not None:
            self._lease.stop()

    def stop_servoj(self):
        self.stop_motion()


class _PolicyHand:
    def __init__(self, hand: Any, robot: PolicyMotionRobot) -> None:
        self._hand = hand
        self._robot = robot

    @property
    def connected(self):
        return self._hand.connected

    @property
    def error(self):
        return self._hand.error

    @property
    def last_sent_target(self):
        return self._hand.last_sent_target

    def latest(self):
        return self._hand.latest()

    def set_target(self, target):
        self._robot.lease()
        return self._hand.set_target(target)

    def set_profile(self, speed, torque):
        self._robot.lease()
        return self._hand.set_profile(speed, torque)

    def hold_current(self):
        lease = self._robot._lease
        if lease is not None and lease.active:
            return self._hand.hold_current()


class PolicyRuntimeView:
    """Expose only the runtime capabilities needed by the policy bridge."""

    def __init__(self, runtime: Any) -> None:
        engine = runtime.teleop_engine
        self.robot = PolicyMotionRobot(lambda: engine.robot)
        hand = _PolicyHand(runtime.o6_controller, self.robot)
        self.store = runtime.store
        self.gello_controller = runtime.gello_controller
        self.master_controller = runtime.master_controller
        self.o6_controller = hand
        self.sample_source = runtime.sample_source
        self.teleop_engine = SimpleNamespace(
            robot=self.robot,
            o6=hand,
            roarm=runtime.master_controller,
            store=runtime.store,
            snapshot=engine.snapshot,
            dataset_sample=engine.dataset_sample,
            _set_dataset_target_tcp=engine._set_dataset_target_tcp,
            _set_dataset_target_joints=engine._set_dataset_target_joints,
        )
        # Older deploy adapters read these session paths. Both remain guarded.
        self.cr3a_lifecycle = SimpleNamespace(
            session=self.robot,
            device=SimpleNamespace(session=self.robot),
        )

    def bind(self, lease: MotionLease) -> None:
        self.robot.bind(lease)
