import math
import time


from teleop.gello_cr.devices.gello import GelloFeedback
from teleop.devices.inverse3 import Inverse3Feedback
from teleop.devices.roarm import RoArmFeedback


def feedback(x=100.0, y=200.0, z=300.0, b=0.1, s=0.2, e=0.3, t=0.8):
    return RoArmFeedback(
        timestamp=time.monotonic(),
        x=x,
        y=y,
        z=z,
        b=b,
        s=s,
        e=e,
        t=t,
        torques=(0.0, 0.0, 0.0, 0.0),
    )


def inverse_feedback(x=100.0, y=200.0, z=300.0, orientation=(1.0, 0.0, 0.0, 0.0)):
    return Inverse3Feedback(
        timestamp=time.monotonic(),
        x=x,
        y=y,
        z=z,
        orientation_wxyz=orientation,
        inverse3_device_id="06DA",
        grip_device_id="VG01",
        grip_type="wireless_verse_grip",
        buttons=(False, False, False),
    )


class FakeNrcServoApi:
    def __init__(self, state=0):
        self.state = int(state)
        self.mode = 0
        self.calls = []
        self.clear_state_after_call = 3
        self.poweron_result = 0
        self.connection_status = {11: 0, 22: 0}
        self.running_states = [0]

    def get_connection_status(self, socket_fd):
        self.calls.append(("get_connection_status", socket_fd))
        return self.connection_status[socket_fd]

    def get_servo_state_robot(self, socket_fd, robot_num, _status):
        self.calls.append(("get_servo_state_robot", socket_fd, robot_num))
        return (0, self.state)

    def get_current_mode_robot(self, socket_fd, robot_num, _mode):
        self.calls.append(("get_current_mode_robot", socket_fd, robot_num))
        return (0, self.mode)

    def set_current_mode_robot(self, socket_fd, robot_num, mode):
        self.calls.append(("set_current_mode_robot", socket_fd, robot_num, mode))
        self.mode = int(mode)
        return 0

    def get_robot_running_state_robot(self, socket_fd, robot_num, _status):
        self.calls.append(("get_robot_running_state_robot", socket_fd, robot_num))
        if len(self.running_states) > 1:
            state = self.running_states.pop(0)
        else:
            state = self.running_states[0]
        return (0, state)

    def clear_error_robot(self, socket_fd, robot_num):
        self.calls.append(("clear_error_robot", socket_fd, robot_num))
        if self.state == 2:
            self.state = int(self.clear_state_after_call)
        return 0

    def set_servo_state_robot(self, socket_fd, robot_num, state):
        self.calls.append(("set_servo_state_robot", socket_fd, robot_num, state))
        if self.state not in (0, 1) or int(state) != 1:
            return -4
        self.state = 1
        return 0

    def set_servo_poweron_robot(self, socket_fd, robot_num):
        self.calls.append(("set_servo_poweron_robot", socket_fd, robot_num))
        if self.poweron_result != 0:
            return self.poweron_result
        if self.state != 1:
            return -4
        self.state = 3
        return 0

    def set_servo_poweroff_robot(self, socket_fd, robot_num):
        self.calls.append(("set_servo_poweroff_robot", socket_fd, robot_num))
        if self.state != 3:
            return -4
        self.state = 1
        return 0


class FakeRoArm:
    def __init__(self):
        self.value = feedback()
        self.error = ""
        self.connected = True
        self.released = False
        self.held = False

    def latest(self):
        return self.value

    def release_torque(self):
        self.released = True

    def hold_current(self):
        self.held = True

    def move_joints(self, joints, duration_s=3.0):
        self.value = feedback(
            self.value.x,
            self.value.y,
            self.value.z,
            *[float(value) for value in joints],
        )

    def close(self, hold=True):
        self.connected = False


class FakeInverse3:
    master_type = "inverse3"
    passive = True

    def __init__(self, value=None):
        self.value = value or inverse_feedback()
        self.error = ""
        self.connected = True

    def latest(self):
        return self.value

    def close(self, hold=False):
        self.connected = False


class FakeGello:
    master_type = "gello"
    passive = True

    def __init__(self):
        self.value = GelloFeedback(time.monotonic(), (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        self.error = ""
        self.connected = True

    def latest(self):
        return self.value

    def close(self, hold=False):
        del hold
        self.connected = False


class FakeO6:
    def __init__(self):
        self.position = (253, 253, 253, 253, 253, 253)
        self.fault = (0, 0, 0, 0, 0, 0)
        self.error = ""
        self.phase = ""
        self.connected = True
        self.targets = []
        self.recoveries = []
        self.profiles = []

    @property
    def last_sent_target(self):
        return self.targets[-1] if self.targets else None

    def latest(self):
        return self.position, self.fault, time.monotonic()

    def set_target(self, target):
        self.position = tuple(int(value) for value in target)
        self.targets.append(self.position)

    def set_profile(self, speed, torque):
        self.profiles.append((tuple(speed), tuple(torque)))

    def wait_until_position(self, target, tolerance=6, timeout=15.0, stop_event=None):
        if stop_event is not None and stop_event.is_set():
            return False
        return max(abs(a - b) for a, b in zip(self.position, target)) <= tolerance

    def hold_current(self):
        self.set_target(self.position)

    def recover_motor(self, motor_number, speed, torque, timeout=4.0, stop_event=None):
        index = int(motor_number) - 1
        before_fault = self.fault
        after_fault = list(self.fault)
        after_fault[index] = 0
        self.fault = tuple(after_fault)
        self.recoveries.append((motor_number, speed, torque))
        names = (
            "大拇指弯曲",
            "大拇指侧摆",
            "食指弯曲",
            "中指弯曲",
            "无名指弯曲",
            "小拇指弯曲",
        )
        return {
            "motor_number": motor_number,
            "motor_name": names[index],
            "position_before": self.position[index],
            "position_after": self.position[index],
            "fault_before": before_fault,
            "fault_after": self.fault,
        }

    def close(self):
        self.connected = False


class FakeRobot:
    def __init__(self):
        self.tcp = [500.0, 10.0, 300.0, 1.1, 2.2, 3.3, 0.0]
        self.joints = [0.0] * 7
        self.ik_targets = []
        self.servoj_open = False
        self.servoj_events = []
        self.servoj_targets = []
        self.movej_targets = []
        self.motion_stop_waits = 0
        self.stopped = False
        self.controller_job_warning = ""

    def servo_state(self):
        return 3

    def current_mode(self):
        return 1

    def tcp_position(self):
        return list(self.tcp)

    def joint_position(self):
        return list(self.joints)

    def open_servoj(self, vmax, amax, jmax):
        self.servoj_events.append("open")
        self.servoj_open = True

    def stop_servoj(self):
        self.servoj_events.append("stop")
        self.servoj_open = False

    def inverse_kinematics(self, target):
        self.ik_targets.append(list(target))
        return [0.0] * 7

    def forward_kinematics(self, joints):
        # A minimal deterministic wrist model is enough to verify that replay
        # generates a non-stale rotational delta action.
        target = list(self.tcp)
        target[3] += math.radians(float(joints[5]))
        return target

    def send_servoj(self, joints):
        self.servoj_events.append("send")
        self.joints = list(joints)
        self.servoj_targets.append(list(joints))

    def clear_movej_busy_if_stopped(self):
        return True

    def movej(self, joints, velocity, acc, dec):
        self.joints = list(joints)
        self.movej_targets.append(list(joints))

    def wait_until_motion_stopped(self, timeout, stop_event=None, stable_samples=3):
        self.motion_stop_waits += 1
        return stop_event is None or not stop_event.is_set()

    def stop_motion(self):
        self.stopped = True
        self.stop_servoj()
