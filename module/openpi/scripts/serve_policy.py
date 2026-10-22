import dataclasses
import enum
import logging
import socket

import tyro

from openpi.policies import policy as _policy
from openpi.policies import policy_config as _policy_config
from openpi.serving import websocket_policy_server
import openpi.shared.download as _download
from openpi.training import config as _config


class EnvMode(enum.Enum):
    """Supported environments."""

    ALOHA = "aloha"
    ALOHA_SIM = "aloha_sim"
    DROID = "droid"
    LIBERO = "libero"


@dataclasses.dataclass
class Checkpoint:
    """Load a policy from a trained checkpoint."""

    # Training config name (e.g., "pi0_aloha_sim").
    config: str
    # Checkpoint directory (e.g., "checkpoints/pi0_aloha_sim/exp/10000").
    dir: str


@dataclasses.dataclass
class Default:
    """Use the default policy for the given environment."""


@dataclasses.dataclass
class Args:
    """Arguments for the serve_policy script."""

    # Environment to serve the policy for. This is only used when serving default policies.
    env: EnvMode = EnvMode.ALOHA_SIM

    # If provided, will be used in case the "prompt" key is not present in the data, or if the model doesn't have a default
    # prompt.
    default_prompt: str | None = None

    # Port to serve the policy on.
    port: int = 8000
    # Record the policy's behavior for debugging.
    record: bool = False

    # Specifies how to load the policy. If not provided, the default policy for the environment will be used.
    policy: Checkpoint | Default = dataclasses.field(default_factory=Default)


# Default checkpoints that should be used for each environment.
DEFAULT_CHECKPOINT: dict[EnvMode, Checkpoint] = {
    EnvMode.ALOHA: Checkpoint(
        config="pi05_aloha",
        dir="gs://openpi-assets/checkpoints/pi05_base",
    ),
    EnvMode.ALOHA_SIM: Checkpoint(
        config="pi0_aloha_sim",
        dir="gs://openpi-assets/checkpoints/pi0_aloha_sim",
    ),
    EnvMode.DROID: Checkpoint(
        config="pi05_droid",
        dir="gs://openpi-assets/checkpoints/pi05_droid",
    ),
    EnvMode.LIBERO: Checkpoint(
        config="pi05_libero",
        dir="gs://openpi-assets/checkpoints/pi05_libero",
    ),
}


def _resolve_checkpoint_asset_id(checkpoint_dir: str, configured_asset_id: str | None) -> str | None:
    """Resolve the normalization asset id stored in a selected checkpoint.

    Prefer the TrainConfig's asset id when it exists in the checkpoint. If it
    does not, use the id from the checkpoint when exactly one stats file is
    present. Keep the configured id when no checkpoint stats are available so
    the existing project-assets fallback continues to work.
    """
    local_checkpoint = _download.maybe_download(checkpoint_dir)
    assets_dir = local_checkpoint / "assets"
    if configured_asset_id is not None:
        configured_stats = assets_dir / configured_asset_id / "norm_stats.json"
        if configured_stats.is_file():
            return configured_asset_id

    candidates = sorted(assets_dir.rglob("norm_stats.json")) if assets_dir.is_dir() else []
    if len(candidates) == 1:
        resolved = candidates[0].parent.relative_to(assets_dir).as_posix()
        if resolved != configured_asset_id:
            logging.info(
                "Checkpoint asset_id %r differs from TrainConfig asset_id %r; using checkpoint asset_id %r.",
                resolved,
                configured_asset_id,
                resolved,
            )
        return resolved

    if len(candidates) > 1:
        available = [path.parent.relative_to(assets_dir).as_posix() for path in candidates]
        raise ValueError(
            f"Checkpoint {local_checkpoint} contains multiple norm_stats.json files {available}, "
            f"and configured asset_id {configured_asset_id!r} does not match any of them."
        )

    return configured_asset_id


def _with_asset_id(train_config: _config.TrainConfig, asset_id: str) -> _config.TrainConfig:
    """Return a runtime TrainConfig copy using the checkpoint's asset id."""
    data_factory = train_config.data
    assets_config = getattr(data_factory, "assets", None)
    if not dataclasses.is_dataclass(data_factory) or not dataclasses.is_dataclass(assets_config):
        raise ValueError(
            f"Cannot apply checkpoint asset_id {asset_id!r} to data config "
            f"{type(data_factory).__name__}: expected a dataclass assets field."
        )
    if "asset_id" not in {field.name for field in dataclasses.fields(assets_config)}:
        raise ValueError(f"Data config {type(data_factory).__name__} has no assets.asset_id field.")

    updated_assets = dataclasses.replace(assets_config, asset_id=asset_id)
    updated_data = dataclasses.replace(data_factory, assets=updated_assets)
    return dataclasses.replace(train_config, data=updated_data)


def create_default_policy(env: EnvMode, *, default_prompt: str | None = None) -> _policy.Policy:
    """Create a default policy for the given environment."""
    if checkpoint := DEFAULT_CHECKPOINT.get(env):
        return _policy_config.create_trained_policy(
            _config.get_config(checkpoint.config), checkpoint.dir, default_prompt=default_prompt
        )
    raise ValueError(f"Unsupported environment mode: {env}")


def create_policy(args: Args) -> _policy.Policy:
    """Create a policy from the given arguments."""
    match args.policy:
        case Checkpoint():
            train_config = _config.get_config(args.policy.config)
            data_factory = train_config.data
            assets_config = getattr(data_factory, "assets", None)
            configured_asset_id = getattr(assets_config, "asset_id", None)
            if not isinstance(configured_asset_id, str) or not configured_asset_id:
                repo_id = getattr(data_factory, "repo_id", None)
                configured_asset_id = repo_id if isinstance(repo_id, str) and repo_id else None
            checkpoint_asset_id = _resolve_checkpoint_asset_id(args.policy.dir, configured_asset_id)
            if checkpoint_asset_id is not None and checkpoint_asset_id != configured_asset_id:
                train_config = _with_asset_id(train_config, checkpoint_asset_id)
            return _policy_config.create_trained_policy(
                train_config, args.policy.dir, default_prompt=args.default_prompt
            )
        case Default():
            return create_default_policy(args.env, default_prompt=args.default_prompt)


def main(args: Args) -> None:
    policy = create_policy(args)
    policy_metadata = policy.metadata

    # Record the policy's behavior.
    if args.record:
        policy = _policy.PolicyRecorder(policy, "policy_records")

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    logging.info("Creating server (host: %s, ip: %s)", hostname, local_ip)

    server = websocket_policy_server.WebsocketPolicyServer(
        policy=policy,
        host="0.0.0.0",
        port=args.port,
        metadata=policy_metadata,
    )
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, force=True)
    main(tyro.cli(Args))
