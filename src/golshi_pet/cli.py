"""Command-line interface for Gold Ship and Pet Derby QA."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .archive import create_bundle, verify_bundle
from .atlas import validate_pet_dir
from .backdrop import audit_backdrops
from .constants import VERSION
from .derby import run_derby
from .html_report import write_derby_html
from .install import doctor_pet, install_bundle, install_pet, rollback_pet, uninstall_pet
from .util import write_json


def _emit(value: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print("PASS" if value.get("ok") else "FAIL")
    for key in ("action", "subject", "output", "bundle", "target", "backup", "sha256"):
        if value.get(key) is not None:
            print(f"{key}: {value[key]}")
    counts = value.get("counts")
    if counts:
        print(
            f"findings: {counts.get('error', 0)} error, "
            f"{counts.get('warning', 0)} warning, {counts.get('info', 0)} info"
        )
    for item in value.get("findings", []):
        print(f"[{item['severity']}] {item['code']}: {item['message']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="golshi-pet",
        description="Gold Ship Codex v2 pet operations and seeded Pet Derby QA",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a Codex pet directory")
    validate.add_argument("pet_dir", type=Path)
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true", dest="as_json")

    derby = subparsers.add_parser("derby", help="run seeded transition and continuity QA")
    derby.add_argument("pet_dir", type=Path)
    derby.add_argument("--plan", type=Path)
    derby.add_argument("--seed", type=int)
    derby.add_argument("--steps", type=int)
    derby.add_argument("--strict", action="store_true")
    derby.add_argument("--json", action="store_true", dest="as_json")
    derby.add_argument("--json-out", type=Path)
    derby.add_argument("--html-out", type=Path)

    backdrop = subparsers.add_parser(
        "backdrop-audit",
        help="measure every active cell against representative desktop backgrounds",
    )
    backdrop.add_argument("pet_dir", type=Path)
    backdrop.add_argument("--backgrounds", type=Path, required=True)
    backdrop.add_argument("--policy", type=Path, required=True)
    backdrop.add_argument("--output-dir", type=Path, required=True)
    backdrop.add_argument("--json", action="store_true", dest="as_json")

    install = subparsers.add_parser(
        "install",
        help="transactionally install a validated pet directory or .codex-pet bundle",
    )
    install.add_argument("pet_dir", type=Path)
    install.add_argument("--codex-home", type=Path)
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true", dest="as_json")

    doctor = subparsers.add_parser("doctor", help="compare source and installed package")
    doctor.add_argument("pet_dir", type=Path)
    doctor.add_argument("--codex-home", type=Path)
    doctor.add_argument("--json", action="store_true", dest="as_json")

    uninstall = subparsers.add_parser("uninstall", help="move an installed pet to a backup")
    uninstall.add_argument("--pet-id", default="gold-ship")
    uninstall.add_argument("--codex-home", type=Path)
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true", dest="as_json")

    rollback = subparsers.add_parser("rollback", help="restore the newest valid backup")
    rollback.add_argument("--pet-id", default="gold-ship")
    rollback.add_argument("--codex-home", type=Path)
    rollback.add_argument("--dry-run", action="store_true")
    rollback.add_argument("--json", action="store_true", dest="as_json")

    pack = subparsers.add_parser("pack", help="create a deterministic .codex-pet archive")
    pack.add_argument("pet_dir", type=Path)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--json", action="store_true", dest="as_json")

    verify = subparsers.add_parser("verify-bundle", help="verify a .codex-pet archive safely")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "validate":
        return validate_pet_dir(args.pet_dir, strict=args.strict).to_dict()
    if args.command == "derby":
        report = run_derby(
            args.pet_dir,
            plan_path=args.plan,
            seed_override=args.seed,
            steps_override=args.steps,
            strict=args.strict,
        )
        value = report.to_dict()
        if args.json_out:
            write_json(args.json_out, value)
        if args.html_out and value["metrics"].get("atlas_sha256"):
            manifest = value["metrics"].get("validation", {}).get("metrics", {}).get("manifest")
            if not manifest:
                validation = validate_pet_dir(args.pet_dir)
                manifest = validation.metrics["manifest"]
            atlas = args.pet_dir.resolve() / str(manifest["spritesheetPath"])
            write_derby_html(value, atlas, args.html_out)
            value["html_report"] = str(args.html_out.resolve())
        return value
    if args.command == "backdrop-audit":
        return audit_backdrops(
            args.pet_dir,
            backgrounds_path=args.backgrounds,
            policy_path=args.policy,
            output_dir=args.output_dir,
        ).to_dict()
    if args.command == "install":
        install_source = args.pet_dir.resolve()
        if install_source.is_file():
            return install_bundle(
                install_source,
                codex_home=args.codex_home,
                dry_run=args.dry_run,
            )
        return install_pet(
            install_source,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
    if args.command == "doctor":
        return doctor_pet(args.pet_dir, codex_home=args.codex_home)
    if args.command == "uninstall":
        return uninstall_pet(
            args.pet_id,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
    if args.command == "rollback":
        return rollback_pet(
            args.pet_id,
            codex_home=args.codex_home,
            dry_run=args.dry_run,
        )
    if args.command == "pack":
        return create_bundle(args.pet_dir, args.output)
    if args.command == "verify-bundle":
        return verify_bundle(args.bundle)
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        value = _run(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        value = {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }
        _emit(value, as_json=getattr(args, "as_json", False))
        return 2
    _emit(value, as_json=getattr(args, "as_json", False))
    return 0 if value.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
