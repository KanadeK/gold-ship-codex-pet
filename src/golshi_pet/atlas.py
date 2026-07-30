"""Strict, evidence-producing Codex v2 atlas validation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from .constants import (
    ACTIVE_CELL_COUNT,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    NEUTRAL_LOOK_FRAME,
    SPECIAL_CELL_COUNT,
    STATE_SPECS,
    UNUSED_CELL_COUNT,
)
from .manifest import load_manifest
from .reporting import AuditReport
from .util import sha256_file


def crop_cell(atlas: Image.Image, row: int, column: int) -> Image.Image:
    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    return atlas.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))


def alpha_coverage(cell: Image.Image) -> float:
    alpha = cell.getchannel("A")
    histogram = alpha.histogram()
    opaque_or_partial = sum(histogram[1:])
    return opaque_or_partial / (CELL_WIDTH * CELL_HEIGHT)


def _touches_edge(cell: Image.Image, margin: int = 2) -> bool:
    alpha = cell.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return False
    left, top, right, bottom = bbox
    return (
        left < margin
        or top < margin
        or right > CELL_WIDTH - margin
        or bottom > CELL_HEIGHT - margin
    )


def _near_key_pixels(cell: Image.Image, key: tuple[int, int, int] = (0, 255, 0)) -> int:
    count = 0
    raw = cell.convert("RGBA").tobytes()
    for offset in range(0, len(raw), 4):
        red, green, blue, alpha = raw[offset : offset + 4]
        if alpha > 16 and abs(red - key[0]) <= 8 and abs(green - key[1]) <= 8 and abs(
            blue - key[2]
        ) <= 8:
            count += 1
    return count


def _frame_change_ratio(first: Image.Image, second: Image.Image) -> float:
    difference = ImageChops.difference(first, second)
    bbox = difference.getbbox()
    if bbox is None:
        return 0.0
    raw = difference.convert("RGBA").tobytes()
    changed = sum(any(raw[offset : offset + 4]) for offset in range(0, len(raw), 4))
    return changed / (CELL_WIDTH * CELL_HEIGHT)


def validate_pet_dir(pet_dir: Path, *, strict: bool = False) -> AuditReport:
    """Validate package metadata, atlas geometry, cell usage, and basic motion."""

    pet_dir = pet_dir.resolve()
    report = AuditReport(str(pet_dir))
    manifest, spritesheet_path = load_manifest(pet_dir, report)
    report.metrics["strict"] = strict
    report.metrics["expected_active_cells"] = ACTIVE_CELL_COUNT
    report.metrics["expected_neutral_cells"] = SPECIAL_CELL_COUNT
    report.metrics["expected_unused_cells"] = UNUSED_CELL_COUNT
    if spritesheet_path is None or not spritesheet_path.is_file():
        return report

    try:
        with Image.open(spritesheet_path) as source:
            source.load()
            source_format = source.format
            atlas = source.convert("RGBA")
    except (OSError, ValueError) as exc:
        report.add("atlas.unreadable", "error", f"spritesheet cannot be decoded: {exc}")
        return report

    report.metrics.update(
        {
            "atlas_path": str(spritesheet_path),
            "atlas_sha256": sha256_file(spritesheet_path),
            "atlas_format": source_format,
            "atlas_size": list(atlas.size),
        }
    )
    if atlas.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        report.add(
            "atlas.dimensions",
            "error",
            f"atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}",
            actual=list(atlas.size),
        )
        return report
    if source_format not in {"WEBP", "PNG"}:
        report.add(
            "atlas.format",
            "error" if strict else "warning",
            "atlas should be PNG or WebP",
            actual=source_format,
        )

    active_cells = 0
    neutral_cells = 0
    unused_cells = 0
    row_motion: dict[str, dict[str, Any]] = {}
    frame_hashes: Counter[bytes] = Counter()
    near_key_total = 0
    for state in STATE_SPECS:
        frames: list[Image.Image] = []
        coverages: list[float] = []
        for column in range(8):
            cell = crop_cell(atlas, state.row, column)
            bbox = cell.getchannel("A").getbbox()
            is_active = column < state.frames
            is_neutral = (state.row, column) == NEUTRAL_LOOK_FRAME
            if is_active or is_neutral:
                cell_state = "neutral-look-frame" if is_neutral else state.name
                if is_neutral:
                    neutral_cells += 1
                else:
                    active_cells += 1
                if bbox is None:
                    report.add(
                        "cell.empty",
                        "error",
                        "required cell is transparent",
                        state=cell_state,
                        row=state.row,
                        column=column,
                    )
                    continue
                coverage = alpha_coverage(cell)
                if is_active:
                    coverages.append(round(coverage, 6))
                    frames.append(cell)
                    frame_hashes[cell.tobytes()] += 1
                if coverage < 0.015:
                    report.add(
                        "cell.too_sparse",
                        "error",
                        "required cell has implausibly little visible content",
                        state=cell_state,
                        column=column,
                        coverage=coverage,
                    )
                elif coverage > 0.82:
                    report.add(
                        "cell.too_dense",
                        "error" if strict else "warning",
                        "required cell fills an implausibly large part of its slot",
                        state=cell_state,
                        column=column,
                        coverage=coverage,
                    )
                if _touches_edge(cell):
                    report.add(
                        "cell.edge",
                        "error" if strict else "warning",
                        "visible pixels touch the cell safety margin",
                        state=cell_state,
                        column=column,
                    )
                near_key = _near_key_pixels(cell)
                near_key_total += near_key
                if near_key:
                    report.add(
                        "cell.chroma",
                        "error",
                        "opaque or translucent chroma-key pixels remain",
                        state=cell_state,
                        column=column,
                        pixels=near_key,
                    )
            else:
                unused_cells += 1
                if bbox is not None:
                    report.add(
                        "cell.unused_nonempty",
                        "error",
                        "unused cell must be fully transparent",
                        state=state.name,
                        row=state.row,
                        column=column,
                    )
        changes = [
            round(_frame_change_ratio(frames[index], frames[(index + 1) % len(frames)]), 6)
            for index in range(len(frames))
        ] if len(frames) > 1 else []
        row_motion[state.name] = {
            "frames": len(frames),
            "coverage": coverages,
            "adjacent_change_ratio": changes,
        }
        if len(frames) > 1 and max(changes, default=0.0) < 0.001:
            report.add(
                "row.inert",
                "error",
                "animation row is effectively static",
                state=state.name,
                max_change=max(changes, default=0.0),
            )
        if state.directions and len({frame.tobytes() for frame in frames}) < 6:
            report.add(
                "direction.repeated",
                "error",
                "look row contains too many identical direction cells",
                state=state.name,
            )

    repeated = sum(count - 1 for count in frame_hashes.values() if count > 1)
    if repeated:
        report.add(
            "atlas.duplicate_cells",
            "warning",
            "some active cells are byte-identical; inspect animation intent",
            repeated_cells=repeated,
        )
    report.metrics.update(
        {
            "manifest": manifest,
            "active_cells_seen": active_cells,
            "neutral_cells_seen": neutral_cells,
            "unused_cells_seen": unused_cells,
            "near_chroma_pixels": near_key_total,
            "row_motion": row_motion,
        }
    )
    return report
