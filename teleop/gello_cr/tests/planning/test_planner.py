import math
from dataclasses import replace

import numpy as np
import pytest

from gello_cr.trajectory import TrajectoryStore
from gello_cr.trajectory.planner import (
    JointMoveRequest,
    PlannerSettings,
    RobotModel,
    TcpMoveRequest,
    TcpPlanningMode,
    TcpPose,
    TrajectoryPlanner,
    Waypoint,
    WaypointRequest,
)


class CartesianKinematics:
    warnings = ()

    def __init__(self):
        self.seeds = []

    def forward(self, joint_rad):
        return TcpPose(tuple(joint_rad[:3]), tuple(joint_rad[3:]))

    def inverse(self, pose, seed_joint_rad=None):
        self.seeds.append(tuple(seed_joint_rad))
        q = pose.position_m + pose.orientation_rpy_rad
        return [tuple(v + 2 * math.pi for v in q), q]


def planner(kinematics=None, **model):
    return TrajectoryPlanner(RobotModel(**model), kinematics or CartesianKinematics())


def test_joint_quintic_limits_and_saved_metadata(tmp_path):
    p = planner(joint_limits_rad=((-2, 2),) * 6)
    result = p.plan(JointMoveRequest((0.4, -1, 0, 0, 0, 0), 0.3, 0.4), (0,) * 6)
    assert result.success, result.errors
    trajectory = result.trajectory
    q = np.array([f.robot_joint_command for f in trajectory.frames])
    t = np.array([f.timestamp for f in trajectory.frames])
    v = np.diff(q, axis=0) / np.diff(t)[:, None]
    a = np.diff(v, axis=0) / ((np.diff(t)[1:] + np.diff(t)[:-1]) / 2)[:, None]
    assert q[0].tolist() == [0] * 6
    assert q[-1].tolist() == [0.4, -1, 0, 0, 0, 0]
    assert np.max(abs(v)) <= 0.3 + 1e-8
    assert np.max(abs(a)) <= 0.4 + 1e-8
    assert np.max(abs(v[[0, -1]])) < 0.001
    store = TrajectoryStore(tmp_path)
    store.save(trajectory)
    restored = store.load(trajectory.metadata.trajectory_id)
    assert restored.metadata.source == "planner"
    assert restored.metadata.planning["planner_type"] == "joint_ptp"
    assert restored.frames == trajectory.frames


def test_tcp_ptp_selects_nearest_valid_fk_solution():
    kin = CartesianKinematics()
    result = planner(kin).plan(TcpMoveRequest(TcpPose((0.1, 0.2, 0.3), (0, 0, 0))), (0,) * 6)
    assert result.success, result.errors
    assert result.trajectory.frames[-1].robot_joint_command == (0.1, 0.2, 0.3, 0, 0, 0)
    assert kin.seeds == [(0,) * 6]


def test_linear_path_stays_straight_and_uses_previous_ik_seed():
    kin = CartesianKinematics()
    result = planner(kin).plan(
        TcpMoveRequest(TcpPose((0.04, 0.03, 0.02), (0, 0, 0)), TcpPlanningMode.LINEAR), (0,) * 6
    )
    assert result.success, result.errors
    q = np.array([f.robot_joint_command for f in result.trajectory.frames])
    direction = np.array([0.04, 0.03, 0.02])
    assert np.max(np.linalg.norm(np.cross(q[:, :3], direction), axis=1)) < 1e-10
    assert np.max(np.linalg.norm(np.diff(q[:, :3], axis=0), axis=1)) <= 0.002
    assert kin.seeds[1:] == [tuple(v) for v in q[1:-1]]


def test_mixed_waypoint_hold_has_strict_time_and_one_endpoint():
    result = planner().plan(
        WaypointRequest(
            (
                Waypoint(TcpPose((0.01, 0, 0), (0, 0, 0)), hold_time_s=0.5),
                Waypoint(
                    TcpPose((0.01, 0.01, 0), (0, 0, 0)), TcpPlanningMode.LINEAR, speed_scale=0.5
                ),
            )
        ),
        (0,) * 6,
    )
    assert result.success, result.errors
    frames = result.trajectory.frames
    assert all(b.timestamp > a.timestamp for a, b in zip(frames, frames[1:], strict=False))
    held = [f.timestamp for f in frames if f.robot_joint_command == (0.01, 0, 0, 0, 0, 0)]
    assert held[-1] - held[0] == pytest.approx(0.5)
    assert frames[-1].robot_joint_command == (0.01, 0.01, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("move_request", "code"),
    [
        (JointMoveRequest((3,) * 6), "JointLimitViolation"),
        (TcpMoveRequest(TcpPose((3, 0, 0), (0, 0, 0))), "TargetOutsideWorkspace"),
        (WaypointRequest(()), "InvalidWaypoint"),
        (JointMoveRequest((float("nan"),) * 6), "TrajectoryLimitViolation"),
    ],
)
def test_invalid_plans_have_specific_errors_and_no_partial_trajectory(move_request, code):
    result = planner(joint_limits_rad=((-2, 2),) * 6, workspace_limits_m=((-1, 1),) * 3).plan(
        move_request, (0,) * 6
    )
    assert not result.success
    assert result.trajectory is None
    assert result.errors[0].startswith(code)


def test_discontinuous_ik_rejected_before_any_trajectory_is_returned():
    kin = CartesianKinematics()
    kin.inverse = lambda pose, seed_joint_rad=None: [(2, 0, 0, 0, 0, 0)]
    result = planner(kin).plan(
        TcpMoveRequest(TcpPose((0.01, 0, 0), (0, 0, 0)), TcpPlanningMode.LINEAR), (0,) * 6
    )
    assert not result.success
    assert result.errors[0].startswith("DiscontinuousIK")


def test_wrong_ik_result_is_rejected_by_forward_check():
    kin = CartesianKinematics()
    kin.inverse = lambda pose, seed_joint_rad=None: [(0,) * 6]
    result = planner(kin).plan(TcpMoveRequest(TcpPose((0.1, 0, 0), (0, 0, 0))), (0,) * 6)
    assert not result.success
    assert result.errors[0].startswith("IKFailure")


def test_linear_rotation_uses_shortest_path_across_pi():
    result = planner().plan(
        TcpMoveRequest(TcpPose((0, 0, 0), (0, 0, math.radians(-179))), TcpPlanningMode.LINEAR),
        (0, 0, 0, 0, 0, math.radians(179)),
    )
    assert result.success, result.errors
    angles = [f.robot_joint_command[5] for f in result.trajectory.frames]
    assert max(angles) - min(angles) == pytest.approx(math.radians(2))


def test_unknown_absolute_bounds_are_visible_in_preview():
    result = planner().plan(JointMoveRequest((0,) * 6), (0,) * 6)
    assert result.success
    assert any("关节硬限位" in warning for warning in result.warnings)
    assert any("工作空间" in warning for warning in result.warnings)


def test_invalid_settings_and_rates_are_returned_as_planning_errors():
    result = planner().plan(JointMoveRequest((0.1,) * 6, -1, 1), (0,) * 6)
    assert not result.success
    with pytest.raises(ValueError):
        TrajectoryPlanner(
            RobotModel(), CartesianKinematics(), replace(PlannerSettings(), sample_hz=0)
        )
