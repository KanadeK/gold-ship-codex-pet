"""Run the complete local release gate and preserve machine-readable evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@dataclass(frozen=True, slots=True)
class Gate:
    name: str
    command: list[str]


def _run(gate: Gate) -> dict[str, object]:
    print(f"\n[{gate.name}] {' '.join(gate.command)}", flush=True)
    result = subprocess.run(gate.command, cwd=ROOT, check=False)
    return {
        "name": gate.name,
        "command": gate.command,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=ROOT / "build" / "release-check.json")
    parser.add_argument("--skip-coverage", action="store_true")
    args = parser.parse_args()
    build = ROOT / "build"
    derby = build / "pet-derby"
    backdrop = build / "backdrop-audit"
    test_gates = (
        [Gate("pytest", [PYTHON, "-m", "pytest", "-q"])]
        if args.skip_coverage
        else [
            Gate(
                "coverage",
                [
                    PYTHON,
                    "-m",
                    "coverage",
                    "run",
                    "--branch",
                    "-m",
                    "pytest",
                    "-q",
                ],
            ),
            Gate(
                "coverage-report",
                [PYTHON, "-m", "coverage", "report", "--fail-under=90"],
            ),
        ]
    )
    gates = [
        Gate("ruff", [PYTHON, "-m", "ruff", "check", "src", "tests", "scripts"]),
        Gate("mypy", [PYTHON, "-m", "mypy", "src/golshi_pet", "scripts"]),
        *test_gates,
        Gate("secret-scan", [PYTHON, "scripts/secret_scan.py"]),
        Gate("web-static", [PYTHON, "scripts/check_web.py", "web"]),
        Gate(
            "pet-validate",
            [PYTHON, "-m", "golshi_pet", "validate", "pet", "--strict", "--json"],
        ),
        Gate(
            "pet-derby",
            [
                PYTHON,
                "-m",
                "golshi_pet",
                "derby",
                "pet",
                "--plan",
                "examples/gold-ship-chaos-race.json",
                "--strict",
                "--json-out",
                str(derby / "report.json"),
                "--html-out",
                str(derby / "report.html"),
                "--json",
            ],
        ),
        Gate(
            "backdrop-gauntlet",
            [
                PYTHON,
                "-m",
                "golshi_pet",
                "backdrop-audit",
                "pet",
                "--backgrounds",
                "examples/backgrounds.json",
                "--policy",
                "examples/backdrop-policy.json",
                "--output-dir",
                str(backdrop),
                "--json",
            ],
        ),
        Gate("release-build", [PYTHON, "scripts/build_release.py"]),
        Gate("wheel-smoke", [PYTHON, "scripts/package_smoke.py"]),
        Gate("site-build", [PYTHON, "scripts/build_site.py"]),
        Gate(
            "site-assets",
            [PYTHON, "scripts/check_web.py", "site", "--require-assets"],
        ),
    ]
    results: list[dict[str, object]] = []
    for gate in gates:
        result = _run(gate)
        results.append(result)
        if not result["ok"]:
            break
    payload = {
        "ok": bool(results) and all(result["ok"] for result in results),
        "gates": results,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
