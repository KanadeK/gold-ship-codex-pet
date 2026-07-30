from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from golshi_pet.cli import main


def test_cli_validate_and_derby_json(
    pet_factory: Callable[..., Path], capsys: object
) -> None:
    pet = pet_factory()
    assert main(["validate", str(pet), "--strict", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["derby", str(pet), "--steps", "64", "--strict", "--json"]) == 0
    assert '"sequence_sha256"' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_cli_returns_two_for_bad_input(tmp_path: Path, capsys: object) -> None:
    assert main(["validate", str(tmp_path / "missing"), "--json"]) == 1
    assert '"ok": false' in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["derby", str(tmp_path), "--steps", "1", "--json"]) == 2
    assert '"error": "ValueError"' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_cli_full_operational_workflow(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
    capsys: object,
) -> None:
    pet = pet_factory()
    derby_json = tmp_path / "derby.json"
    derby_html = tmp_path / "derby.html"
    assert (
        main(
            [
                "derby",
                str(pet),
                "--steps",
                "64",
                "--strict",
                "--json-out",
                str(derby_json),
                "--html-out",
                str(derby_html),
            ]
        )
        == 0
    )
    assert "PASS" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert derby_json.is_file()
    assert "Pet Derby QA" in derby_html.read_text(encoding="utf-8")

    backgrounds = tmp_path / "backgrounds.json"
    policy = tmp_path / "policy.json"
    backgrounds.write_text(
        json.dumps(
            {"backgrounds": [{"id": "ink", "name": "Ink", "color": "#000000"}]}
        ),
        encoding="utf-8",
    )
    policy.write_text(
        json.dumps(
            {
                "scales": [0.5],
                "min_edge_contrast_p10": 1.0,
                "max_low_contrast_fraction": 1.0,
                "low_contrast_ratio": 1.0,
                "alpha_threshold": 32,
            }
        ),
        encoding="utf-8",
    )
    audit_dir = tmp_path / "audit"
    assert (
        main(
            [
                "backdrop-audit",
                str(pet),
                "--backgrounds",
                str(backgrounds),
                "--policy",
                str(policy),
                "--output-dir",
                str(audit_dir),
                "--json",
            ]
        )
        == 0
    )
    assert '"measurement_count"' in capsys.readouterr().out  # type: ignore[attr-defined]

    bundle = tmp_path / "gold-ship.codex-pet"
    assert main(["pack", str(pet), "--output", str(bundle), "--json"]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["verify-bundle", str(bundle), "--json"]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]

    codex_home = tmp_path / "codex-home"
    assert (
        main(
            [
                "install",
                str(bundle),
                "--codex-home",
                str(codex_home),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]
    assert (
        main(["install", str(pet), "--codex-home", str(codex_home), "--json"])
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]
    assert (
        main(["doctor", str(pet), "--codex-home", str(codex_home), "--json"])
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]
    assert (
        main(
            [
                "uninstall",
                "--pet-id",
                "gold-ship",
                "--codex-home",
                str(codex_home),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]
    assert (
        main(
            [
                "rollback",
                "--pet-id",
                "gold-ship",
                "--codex-home",
                str(codex_home),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()  # type: ignore[attr-defined]


def test_cli_reports_runtime_error(tmp_path: Path, capsys: object) -> None:
    missing = tmp_path / "missing.codex-pet"
    assert main(["verify-bundle", str(missing), "--json"]) == 2
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"ok": false' in output
    assert '"error": "FileNotFoundError"' in output
