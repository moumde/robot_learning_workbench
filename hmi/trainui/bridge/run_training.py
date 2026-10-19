from __future__ import annotations

import argparse
import json
import traceback

from scripts import train as openpi_train

from hmi.trainui.bridge.config_adapter import build_train_config


def _emit(event: dict) -> None:
    print("TRAINUI_EVENT=" + json.dumps(event, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-json", required=True)
    args = parser.parse_args()

    raw = json.loads(args.spec_json)
    if not isinstance(raw, dict):
        raise ValueError("spec-json 必须是 JSON object")

    config = build_train_config(raw)
    _emit({
        "type": "training_start",
        "config_name": config.name,
        "dataset_id": raw["dataset_id"],
        "exp_name": config.exp_name,
        "checkpoint_dir": str(config.checkpoint_dir),
    })

    try:
        openpi_train.main(config)
    except KeyboardInterrupt:
        _emit({"type": "training_interrupted"})
        return 130
    except Exception as exc:
        _emit({"type": "training_failed", "message": str(exc)})
        traceback.print_exc()
        return 1

    _emit({"type": "training_finished"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
