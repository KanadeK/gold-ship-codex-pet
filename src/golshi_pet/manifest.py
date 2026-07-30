"""Codex pet manifest loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reporting import AuditReport
from .util import resolve_within

REQUIRED_FIELDS: dict[str, type[object]] = {
    "id": str,
    "displayName": str,
    "description": str,
    "spriteVersionNumber": int,
    "spritesheetPath": str,
}


def load_manifest(pet_dir: Path, report: AuditReport) -> tuple[dict[str, Any], Path | None]:
    manifest_path = pet_dir / "pet.json"
    if not manifest_path.is_file():
        report.add("manifest.missing", "error", "pet.json is missing", path=str(manifest_path))
        return {}, None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.add("manifest.invalid_json", "error", f"pet.json cannot be read: {exc}")
        return {}, None
    if not isinstance(raw, dict):
        report.add("manifest.not_object", "error", "pet.json must contain a JSON object")
        return {}, None

    manifest: dict[str, Any] = raw
    for field_name, field_type in REQUIRED_FIELDS.items():
        value = manifest.get(field_name)
        if not isinstance(value, field_type) or (
            isinstance(value, str) and not value.strip()
        ):
            report.add(
                "manifest.field",
                "error",
                f"{field_name} has the wrong type or is empty",
                field=field_name,
            )
    if manifest.get("spriteVersionNumber") != 2:
        report.add(
            "manifest.version",
            "error",
            "spriteVersionNumber must be 2 for an 8x11 atlas",
            actual=manifest.get("spriteVersionNumber"),
        )
    pet_id = manifest.get("id")
    if isinstance(pet_id, str) and (
        pet_id != pet_id.lower()
        or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in pet_id)
        or pet_id.startswith("-")
        or pet_id.endswith("-")
        or "--" in pet_id
    ):
        report.add(
            "manifest.id",
            "error",
            "id must be a lowercase kebab-case slug",
            actual=pet_id,
        )

    spritesheet_path: Path | None = None
    relative = manifest.get("spritesheetPath")
    if isinstance(relative, str):
        try:
            spritesheet_path = resolve_within(pet_dir, relative)
        except ValueError as exc:
            report.add("manifest.sprite_path", "error", str(exc), actual=relative)
        else:
            if not spritesheet_path.is_file():
                report.add(
                    "atlas.missing",
                    "error",
                    "spritesheetPath does not point to a file",
                    path=str(spritesheet_path),
                )
    return manifest, spritesheet_path
