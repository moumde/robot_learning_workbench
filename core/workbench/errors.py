"""Domain error roots. Public domain modules re-export their existing names."""


class WorkbenchError(RuntimeError):
    """An operational workbench failure."""


class HardwareError(WorkbenchError):
    """Device communication or lifecycle failure."""


class MotionError(WorkbenchError):
    """Motion execution, safety or arbitration failure."""


class TeleopError(WorkbenchError):
    """Teleoperation cannot start or continue."""


class TrajectoryError(WorkbenchError):
    """Trajectory recording, storage or playback failure."""


class RecordingError(WorkbenchError):
    """Capture, dataset writer or recovery failure."""


class PlanningError(WorkbenchError, ValueError):
    """A motion request cannot produce an executable trajectory."""
