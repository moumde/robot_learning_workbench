"""Mode selection and composition of the existing motion editors; no device I/O."""

from PySide6.QtWidgets import QWidget

from teleop.gello_cr.core.state_machine import WorkflowState

from .generated.ui_motion_workspace import Ui_MotionWorkspace
from .planning_panel import PlanningPanel
from .trajectory_panel import TrajectoryPanel


class MotionWorkspace(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._ui = Ui_MotionWorkspace()
        self._ui.setupUi(self)
        self.library_host = self._ui.motion_library_host
        self.mode_hint = self._ui.motion_mode_hint
        self.mode_buttons = {
            "record": self._ui.motion_record_mode_button,
            "replay": self._ui.motion_replay_mode_button,
            "plan": self._ui.motion_plan_mode_button,
        }
        self.trajectory_panel = TrajectoryPanel(submit, self._ui.motion_trajectory_host)
        self.planning_panel = PlanningPanel(submit, self._ui.motion_planning_host)
        self.library_host.layout().addWidget(self.trajectory_panel.library_panel)
        self._ui.motion_trajectory_host.layout().addWidget(self.trajectory_panel)
        self._ui.motion_planning_host.layout().addWidget(self.planning_panel)
        self._ui.motion_splitter.setStretchFactor(0, 0)
        self._ui.motion_splitter.setStretchFactor(1, 1)
        self._ui.motion_splitter.setSizes([240, 900])
        self.mode = "replay"
        self._locked_mode = None
        for mode, button in self.mode_buttons.items():
            button.clicked.connect(lambda checked=False, selected=mode: self.set_mode(selected))
        self.trajectory_panel.saved_list.itemClicked.connect(lambda _: self.set_mode("replay"))
        self.trajectory_panel.saved_list.itemActivated.connect(lambda _: self.set_mode("replay"))
        self._show_mode("replay")

    def set_mode(self, mode):
        if mode not in self.mode_buttons:
            raise ValueError(f"Unknown motion mode: {mode}")
        if self._locked_mode is not None and mode != self._locked_mode:
            return False
        self._show_mode(mode)
        return True

    def _show_mode(self, mode):
        self.mode = mode
        self.mode_buttons[mode].setChecked(True)
        if mode == "plan":
            self._ui.motion_editor_stack.setCurrentWidget(self._ui.motion_planning_host)
        else:
            self.trajectory_panel.set_mode(mode)
            self._ui.motion_editor_stack.setCurrentWidget(self._ui.motion_trajectory_host)
        self.mode_hint.setText(
            {
                "record": "开始记录将启动遥操；停止并保存后保持停止。",
                "replay": "从左侧选轨迹，预览后明确开始回放。",
                "plan": "编辑目标或路点，生成规划后再执行；保存后可在左侧轨迹库查看。",
            }[mode]
        )

    def render(self, trajectory, planning, view, readiness, busy=False):
        unsaved = bool(
            trajectory.get("recording")
            or trajectory.get("pending")
            or trajectory.get("frame_count")
        )
        active = (
            "record"
            if unsaved
            else "replay"
            if trajectory.get("playing") or view.workflow_state is WorkflowState.REPLAY_RUNNING
            else "plan"
            if planning.get("running") or view.workflow_state is WorkflowState.POINT_MOVE_RUNNING
            else None
        )
        self._locked_mode = active or (self.mode if busy else None)
        if active is not None and active != self.mode:
            self._show_mode(active)
        for mode, button in self.mode_buttons.items():
            button.setEnabled(self._locked_mode is None or mode == self.mode)
        self.trajectory_panel.render(trajectory, view, readiness, busy)
        self.planning_panel.render(planning, view, busy)
        self.trajectory_panel.library_panel.setEnabled(not busy and active is None)
        if unsaved:
            self.mode_hint.setText(
                "轨迹记录尚未处理；请停止并保存、重试保存或取消记录后再切换模式。"
            )
        elif active is not None:
            self.mode_hint.setText("当前运动正在执行；停止或完成后可切换模式。")
        else:
            self._show_mode(self.mode)
