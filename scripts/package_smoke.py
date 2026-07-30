"""Install the built wheel in an isolated environment and exercise its CLI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")


def smoke(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="golshi-wheel-") as temporary:
        environment_root = Path(temporary) / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment_root)
        python = (
            environment_root / "Scripts" / "python.exe"
            if os.name == "nt"
            else environment_root / "bin" / "python"
        )
        environment = {**os.environ, "PIP_NO_INDEX": "1", "PYTHONUTF8": "1"}
        _run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheel.resolve())],
            environment=environment,
        )
        _run([str(python), "-m", "golshi_pet", "--version"], environment=environment)
        _run(
            [
                str(python),
                "-m",
                "golshi_pet",
                "validate",
                str(ROOT / "pet"),
                "--strict",
                "--json",
            ],
            environment=environment,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    wheels = sorted(args.dist.glob("gold_ship_codex_pet-*.whl"))
    if len(wheels) != 1:
        print(f"FAIL: expected one wheel, found {len(wheels)}", file=sys.stderr)
        return 1
    try:
        smoke(wheels[0])
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: isolated wheel smoke test passed for {wheels[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
