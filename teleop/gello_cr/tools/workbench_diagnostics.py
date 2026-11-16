"""Print deployment diagnostics without constructing a runtime or loading SDKs."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from teleop.gello_cr.bootstrap.composition import REPO_ROOT, IntegratedConfigStore
from teleop.gello_cr.support.diagnostics import diagnostic_report


def main():
    root = REPO_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=root / "config/teleop/gello_cr.json")
    parser.add_argument("--hardware-config", type=Path)
    args = parser.parse_args()
    config = IntegratedConfigStore.from_file(args.config, hardware_config=args.hardware_config)
    print(
        json.dumps(diagnostic_report(config.deployment_data(), root), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
