#!/usr/bin/env python3
"""Regenerate Qt Python bindings from the editable Designer forms.

Run with the UI environment: python scripts/generate_ui.py
The .ui files are the source of truth; never edit ui/generated/ui_*.py.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ui_root = Path(__file__).resolve().parents[1] / "src/gello_cr/ui"
    compiler = Path(sys.executable).with_name("pyside6-uic")
    if not compiler.is_file():
        found = shutil.which("pyside6-uic")
        if found is None:
            raise SystemExit("Install the ui extra to provide pyside6-uic.")
        compiler = Path(found)
    generated = ui_root / "generated"
    generated.mkdir(exist_ok=True)
    for form in sorted((ui_root / "forms").rglob("*.ui")):
        output = generated / f"ui_{form.stem}.py"
        subprocess.run([str(compiler), str(form), "-o", str(output)], check=True)
        output.write_text(output.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
        print(f"Generated {output.relative_to(ui_root.parent.parent.parent)}")


if __name__ == "__main__":
    main()
