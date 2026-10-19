from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = WORKSPACE_ROOT / "dataset" / "train"
LOG_ROOT = WORKSPACE_ROOT / "logs" / "trainui"
RUN_OPENPI = WORKSPACE_ROOT / "scripts" / "run_openpi.sh"
CHECKPOINT_ROOT = WORKSPACE_ROOT / "checkpoints"
