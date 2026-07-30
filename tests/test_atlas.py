from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from golshi_pet.atlas import (
    _frame_change_ratio,
    _near_key_pixels,
    _touches_edge,
    validate_pet_dir,
)
from golshi_pet.constants import (
    ACTIVE_CELL_COUNT,
    CELL_HEIGHT,
    CELL_WIDTH,
    NEUTRAL_LOOK_FRAME,
    SPECIAL_CELL_COUNT,
    UNUSED_CELL_COUNT,
)


def finding_codes(report: object) -> set[str]:
    return {item.code for item in report.findings}  # type: ignore[attr-defined]


def test_valid_v2_pet_passes_strict(pet_factory: Callable[..., Path]) -> None:
    report = validate_pet_dir(pet_factory(), strict=True)
    assert report.ok, report.to_dict()
    assert report.metrics["active_cells_seen"] == ACTIVE_CELL_COUNT
    assert report.metrics["neutral_cells_seen"] == SPECIAL_CELL_COUNT
    assert report.metrics["unused_cells_seen"] == UNUSED_CELL_COUNT
    assert report.metrics["near_chroma_pixels"] == 0


def test_wrong_dimensions_fail(pet_factory: Callable[..., Path]) -> None:
    report = validate_pet_dir(pet_factory(size=(512, 512)), strict=True)
    assert not report.ok
    assert "atlas.dimensions" in finding_codes(report)


def test_empty_required_cell_fails(pet_factory: Callable[..., Path]) -> None:
    report = validate_pet_dir(pet_factory(empty_cell=(0, 0)), strict=True)
    assert not report.ok
    assert "cell.empty" in finding_codes(report)


def test_empty_neutral_look_frame_fails(pet_factory: Callable[..., Path]) -> None:
    report = validate_pet_dir(pet_factory(empty_cell=NEUTRAL_LOOK_FRAME), strict=True)
    assert not report.ok
    assert "cell.empty" in finding_codes(report)


def test_nonempty_unused_cell_fails(pet_factory: Callable[..., Path]) -> None:
    report = validate_pet_dir(pet_factory(dirty_unused=(0, 7)), strict=True)
    assert not report.ok
    assert "cell.unused_nonempty" in finding_codes(report)


def test_manifest_traversal_fails(pet_factory: Callable[..., Path]) -> None:
    root = pet_factory()
    manifest = json.loads((root / "pet.json").read_text(encoding="utf-8"))
    manifest["spritesheetPath"] = "../outside.webp"
    (root / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pet_dir(root)
    assert not report.ok
    assert "manifest.sprite_path" in finding_codes(report)


def test_missing_and_invalid_manifest_fail(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()
    assert "manifest.missing" in finding_codes(validate_pet_dir(missing))
    (missing / "pet.json").write_text("{", encoding="utf-8")
    assert "manifest.invalid_json" in finding_codes(validate_pet_dir(missing))


def test_manifest_schema_failures_are_actionable(
    pet_factory: Callable[..., Path],
) -> None:
    root = pet_factory()
    manifest_path = root / "pet.json"
    manifest_path.write_text("[]", encoding="utf-8")
    assert "manifest.not_object" in finding_codes(validate_pet_dir(root))

    manifest_path.write_text(
        json.dumps(
            {
                "id": "Bad--Id",
                "displayName": "",
                "description": 1,
                "spriteVersionNumber": 1,
                "spritesheetPath": "missing.webp",
            }
        ),
        encoding="utf-8",
    )
    codes = finding_codes(validate_pet_dir(root))
    assert {"manifest.field", "manifest.version", "manifest.id", "atlas.missing"} <= codes


def test_unreadable_and_wrong_format_atlas_fail(
    pet_factory: Callable[..., Path],
) -> None:
    unreadable = pet_factory(name="unreadable")
    (unreadable / "spritesheet.webp").write_bytes(b"not an image")
    assert "atlas.unreadable" in finding_codes(validate_pet_dir(unreadable))

    wrong_format = pet_factory(name="wrong-format")
    with Image.open(wrong_format / "spritesheet.webp") as source:
        source.convert("RGB").save(wrong_format / "spritesheet.webp", "BMP")
    assert "atlas.format" in finding_codes(validate_pet_dir(wrong_format, strict=True))


def test_cell_density_edges_chroma_and_motion_failures(
    pet_factory: Callable[..., Path],
) -> None:
    root = pet_factory()
    atlas_path = root / "spritesheet.webp"
    with Image.open(atlas_path) as source:
        atlas = source.convert("RGBA")
    draw = ImageDraw.Draw(atlas)

    draw.rectangle((0, 0, CELL_WIDTH - 1, CELL_HEIGHT - 1), fill=(120, 80, 80, 255))
    left = CELL_WIDTH
    draw.rectangle(
        (left, 0, left + CELL_WIDTH - 1, CELL_HEIGHT - 1),
        fill=(0, 0, 0, 0),
    )
    draw.rectangle((left + 80, 80, left + 84, 84), fill=(100, 100, 100, 255))
    draw.rectangle((2 * CELL_WIDTH + 70, 70, 2 * CELL_WIDTH + 90, 90), fill=(0, 255, 0, 255))

    wave_top = 3 * CELL_HEIGHT
    first_wave = atlas.crop((0, wave_top, CELL_WIDTH, wave_top + CELL_HEIGHT))
    for column in range(1, 4):
        atlas.paste(first_wave, (column * CELL_WIDTH, wave_top))
    first_direction = atlas.crop(
        (0, 9 * CELL_HEIGHT, CELL_WIDTH, 10 * CELL_HEIGHT)
    )
    for column in range(1, 8):
        atlas.paste(first_direction, (column * CELL_WIDTH, 9 * CELL_HEIGHT))
    atlas.save(atlas_path, "WEBP", lossless=True, method=6)

    codes = finding_codes(validate_pet_dir(root, strict=True))
    assert {
        "cell.too_dense",
        "cell.too_sparse",
        "cell.edge",
        "cell.chroma",
        "row.inert",
        "direction.repeated",
        "atlas.duplicate_cells",
    } <= codes


def test_private_motion_helpers_handle_blank_cells() -> None:
    blank = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    assert not _touches_edge(blank)
    assert _frame_change_ratio(blank, blank) == 0


def test_chroma_alpha_threshold_matches_authoritative_validator() -> None:
    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    cell.putpixel((10, 10), (0, 255, 0, 16))
    assert _near_key_pixels(cell) == 0
    cell.putpixel((10, 10), (0, 255, 0, 17))
    assert _near_key_pixels(cell) == 1
