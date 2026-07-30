"""Deterministic multi-background silhouette legibility audit."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

from .atlas import crop_cell, validate_pet_dir
from .constants import CELL_HEIGHT, CELL_WIDTH, STATE_SPECS
from .reporting import AuditReport
from .util import write_json

DEFAULT_POLICY: dict[str, Any] = {
    "scales": [1.0, 0.5],
    "min_edge_contrast_p10": 1.08,
    "max_low_contrast_fraction": 0.58,
    "low_contrast_ratio": 1.18,
    "alpha_threshold": 32,
}


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} cannot be read: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _parse_color(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"background color must be #RRGGBB, got {value!r}")
    try:
        parsed = tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
        return parsed  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"background color must be #RRGGBB, got {value!r}") from exc


def load_backgrounds(path: Path) -> list[dict[str, Any]]:
    value = _load_object(path, "background palette").get("backgrounds")
    if not isinstance(value, list) or not value:
        raise ValueError("backgrounds must be a non-empty array")
    backgrounds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each background must be an object")
        identifier = item.get("id")
        name = item.get("name")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("background ids must be non-empty and unique")
        if not isinstance(name, str) or not name:
            raise ValueError(f"background {identifier!r} needs a name")
        color = _parse_color(item.get("color"))
        seen.add(identifier)
        backgrounds.append(
            {"id": identifier, "name": name, "color": color, "hex": item["color"].upper()}
        )
    return backgrounds


def load_policy(path: Path) -> dict[str, Any]:
    supplied = _load_object(path, "backdrop policy")
    unknown = sorted(set(supplied) - set(DEFAULT_POLICY))
    if unknown:
        raise ValueError(f"unknown backdrop policy fields: {', '.join(unknown)}")
    policy = {**DEFAULT_POLICY, **supplied}
    scales = policy["scales"]
    if (
        not isinstance(scales, list)
        or not scales
        or any(not isinstance(scale, int | float) or not 0.1 <= scale <= 1.0 for scale in scales)
    ):
        raise ValueError("scales must contain numbers from 0.1 through 1.0")
    for key in ("min_edge_contrast_p10", "low_contrast_ratio"):
        if not isinstance(policy[key], int | float) or policy[key] < 1:
            raise ValueError(f"{key} must be at least 1")
    fraction = policy["max_low_contrast_fraction"]
    if not isinstance(fraction, int | float) or not 0 <= fraction <= 1:
        raise ValueError("max_low_contrast_fraction must be from 0 through 1")
    threshold = policy["alpha_threshold"]
    if not isinstance(threshold, int) or not 1 <= threshold <= 255:
        raise ValueError("alpha_threshold must be an integer from 1 through 255")
    policy["scales"] = sorted({float(item) for item in scales}, reverse=True)
    return policy


def _channel(value: int) -> float:
    normalized = value / 255
    return normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4


def _luminance(color: tuple[int, int, int]) -> float:
    red, green, blue = (_channel(value) for value in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    bright, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def _edge_indices(alpha: bytes, width: int, height: int, threshold: int) -> list[int]:
    result: list[int] = []
    for y_coord in range(height):
        row = y_coord * width
        for x_coord in range(width):
            index = row + x_coord
            if alpha[index] < threshold:
                continue
            if (
                x_coord == 0
                or y_coord == 0
                or x_coord == width - 1
                or y_coord == height - 1
                or alpha[index - 1] < threshold
                or alpha[index + 1] < threshold
                or alpha[index - width] < threshold
                or alpha[index + width] < threshold
            ):
                result.append(index)
    return result


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[math.floor((len(ordered) - 1) * fraction)]


def _measure(
    frame: Image.Image,
    background: tuple[int, int, int],
    *,
    alpha_threshold: int,
    low_ratio: float,
) -> dict[str, Any]:
    rgba = frame.convert("RGBA")
    width, height = rgba.size
    raw = rgba.tobytes()
    alpha = raw[3::4]
    ratios: list[float] = []
    for index in _edge_indices(alpha, width, height, alpha_threshold):
        offset = index * 4
        opacity = raw[offset + 3] / 255
        foreground = raw[offset], raw[offset + 1], raw[offset + 2]
        composite = tuple(
            round(foreground[channel] * opacity + background[channel] * (1 - opacity))
            for channel in range(3)
        )
        ratios.append(_contrast(composite, background))  # type: ignore[arg-type]
    low_count = sum(ratio < low_ratio for ratio in ratios)
    return {
        "edge_pixels": len(ratios),
        "edge_contrast_p10": round(_percentile(ratios, 0.10), 6),
        "edge_contrast_median": round(_percentile(ratios, 0.50), 6),
        "low_contrast_fraction": round(low_count / len(ratios), 6) if ratios else 1.0,
    }


def _write_overview(
    atlas: Image.Image,
    backgrounds: list[dict[str, Any]],
    output: Path,
) -> None:
    tile_width, tile_height = 384, 572
    columns = 4
    rows = math.ceil(len(backgrounds) / columns)
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), (18, 20, 24))
    for index, background in enumerate(backgrounds):
        composite = Image.new("RGBA", atlas.size, (*background["color"], 255))
        composite.alpha_composite(atlas)
        thumbnail = composite.convert("RGB").resize(
            (tile_width, tile_height),
            Image.Resampling.LANCZOS,
        )
        sheet.paste(
            thumbnail,
            ((index % columns) * tile_width, (index // columns) * tile_height),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "PNG", optimize=False, compress_level=9)


def _write_html(report: dict[str, Any], output: Path) -> None:
    rows = []
    for item in report["metrics"]["background_summary"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td><code>{html.escape(item['hex'])}</code></td>"
            f"<td>{item['worst_edge_contrast_p10']:.3f}</td>"
            f"<td>{item['worst_low_contrast_fraction']:.1%}</td>"
            "</tr>"
        )
    status = "PASS" if report["ok"] else "FAIL"
    document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Backdrop Gauntlet report</title>
<style>
body{{font:16px/1.5 system-ui;margin:0;background:#0b0f14;color:#e8edf2}}
main{{max-width:1040px;margin:auto;padding:40px 24px}} h1{{font-size:clamp(2rem,5vw,4rem)}}
.status{{display:inline-block;padding:.35rem .7rem;border:1px solid #8e7dff;border-radius:999px}}
img{{width:100%;height:auto;border:1px solid #3a414a}} table{{width:100%;border-collapse:collapse}}
th,td{{padding:.7rem;text-align:left;border-bottom:1px solid #343b44}} code{{color:#ffd166}}
</style><main><p class="status">{status}</p><h1>Backdrop Gauntlet</h1>
<p>Every required Codex v2 cell was measured at every configured scale and background.
These are artwork legibility heuristics, not WCAG conformance claims.</p>
<img src="overview.png" alt="The complete atlas composited over every audit background">
<h2>Worst result per background</h2><table><thead><tr><th>Background</th><th>Color</th>
<th>Edge p10</th><th>Low-contrast edge</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</main></html>
"""
    output.write_text(document, encoding="utf-8", newline="\n")


def audit_backdrops(
    pet_dir: Path,
    *,
    backgrounds_path: Path,
    policy_path: Path,
    output_dir: Path,
) -> AuditReport:
    """Measure all active cells and persist reproducible JSON, PNG, and HTML evidence."""

    backgrounds = load_backgrounds(backgrounds_path)
    policy = load_policy(policy_path)
    validation = validate_pet_dir(pet_dir)
    report = AuditReport(f"backdrop:{pet_dir.resolve()}")
    report.findings.extend(validation.findings)
    if not validation.ok:
        report.metrics["validation"] = validation.to_dict()
        return report
    manifest = validation.metrics["manifest"]
    atlas_path = pet_dir.resolve() / str(manifest["spritesheetPath"])
    with Image.open(atlas_path) as source:
        atlas = source.convert("RGBA")

    measurements: list[dict[str, Any]] = []
    for state in STATE_SPECS:
        for column in range(state.frames):
            original = crop_cell(atlas, state.row, column)
            for scale in policy["scales"]:
                size = (
                    max(1, round(CELL_WIDTH * scale)),
                    max(1, round(CELL_HEIGHT * scale)),
                )
                frame = (
                    original
                    if scale == 1
                    else original.resize(size, Image.Resampling.LANCZOS)
                )
                for background in backgrounds:
                    metric = _measure(
                        frame,
                        background["color"],
                        alpha_threshold=policy["alpha_threshold"],
                        low_ratio=policy["low_contrast_ratio"],
                    )
                    item = {
                        "state": state.name,
                        "row": state.row,
                        "column": column,
                        "scale": scale,
                        "background": background["id"],
                        **metric,
                    }
                    measurements.append(item)
                    weak_tail = (
                        metric["edge_contrast_p10"] < policy["min_edge_contrast_p10"]
                    )
                    weak_bulk = (
                        metric["low_contrast_fraction"]
                        > policy["max_low_contrast_fraction"]
                    )
                    if weak_tail and weak_bulk:
                        report.add(
                            "backdrop.weak_edge",
                            "error",
                            "cell edge has both a weak lower tail and an excessive "
                            "low-contrast fraction",
                            **item,
                        )

    summary = []
    for background in backgrounds:
        group = [item for item in measurements if item["background"] == background["id"]]
        summary.append(
            {
                "id": background["id"],
                "name": background["name"],
                "hex": background["hex"],
                "worst_edge_contrast_p10": min(
                    item["edge_contrast_p10"] for item in group
                ),
                "worst_low_contrast_fraction": max(
                    item["low_contrast_fraction"] for item in group
                ),
            }
        )
    report.metrics.update(
        {
            "policy": policy,
            "background_summary": summary,
            "measurements": measurements,
            "cells_measured": sum(state.frames for state in STATE_SPECS),
            "measurement_count": len(measurements),
            "validation": validation.to_dict(),
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_overview(atlas, backgrounds, output_dir / "overview.png")
    value = report.to_dict()
    write_json(output_dir / "report.json", value)
    _write_html(value, output_dir / "report.html")
    return report
