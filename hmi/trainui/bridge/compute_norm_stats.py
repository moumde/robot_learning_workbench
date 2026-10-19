from __future__ import annotations

import argparse
import json

import numpy as np
import tqdm

import openpi.shared.normalize as normalize
from openpi.training import config as training_config
from scripts import compute_norm_stats as openpi_norm

from hmi.trainui.bridge.config_adapter import with_dataset


def _emit(event: dict) -> None:
    print("TRAINUI_EVENT=" + json.dumps(event, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-name", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    base_config = training_config.get_config(args.config_name)
    config = with_dataset(base_config, args.dataset_id)
    data_config = config.data.create(config.assets_dirs, config.model)

    if data_config.rlds_data_dir is not None:
        loader, num_batches = openpi_norm.create_rlds_dataloader(
            data_config,
            config.model.action_horizon,
            config.batch_size,
            args.max_frames,
        )
    else:
        loader, num_batches = openpi_norm.create_torch_dataloader(
            data_config,
            config.model.action_horizon,
            config.batch_size,
            config.model,
            config.num_workers,
            args.max_frames,
        )

    if num_batches <= 0:
        raise ValueError("数据量不足以形成一个 normalization batch；请检查数据集或 batch_size。")

    stats = {key: normalize.RunningStats() for key in ("state", "actions")}
    for batch in tqdm.tqdm(loader, total=num_batches, desc="Computing stats"):
        for key in stats:
            stats[key].update(np.asarray(batch[key]))

    norm_stats = {key: running.get_statistics() for key, running in stats.items()}
    asset_id = data_config.asset_id or data_config.repo_id
    output_path = config.assets_dirs / asset_id

    print(f"Writing stats to: {output_path}", flush=True)
    normalize.save(output_path, norm_stats)

    _emit({
        "type": "norm_stats_finished",
        "dataset_id": args.dataset_id,
        "output": str(output_path / "norm_stats.json"),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
