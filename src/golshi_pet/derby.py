"""Seeded state-transition stress tests for any Codex v2 pet."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .atlas import crop_cell, validate_pet_dir
from .constants import (
    CELL_HEIGHT,
    CELL_WIDTH,
    DIRECTION_TO_CELL,
    STATE_SPECS,
)
from .reporting import AuditReport
from .util import canonical_json, sha256_bytes

DEFAULT_STATE_WEIGHTS = {
    "idle": 12,
    "running-right": 5,
    "running-left": 5,
    "waving": 4,
    "jumping": 3,
    "failed": 2,
    "waiting": 7,
    "running": 14,
    "review": 8,
    "look": 10,
}


@dataclass(frozen=True, slots=True)
class FrameFeature:
    area: int
    centroid_x: float
    centroid_y: float
    bbox: tuple[int, int, int, int]


def _frame_feature(cell: Image.Image) -> FrameFeature:
    alpha = cell.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return FrameFeature(0, 0.0, 0.0, (0, 0, 0, 0))
    area = 0
    sum_x = 0
    sum_y = 0
    for index, opacity in enumerate(alpha.tobytes()):
        if opacity:
            y_coord, x_coord = divmod(index, CELL_WIDTH)
            area += 1
            sum_x += x_coord
            sum_y += y_coord
    return FrameFeature(area, sum_x / area, sum_y / area, bbox)


def _transition_metrics(first: FrameFeature, second: FrameFeature) -> dict[str, float]:
    if not first.area or not second.area:
        return {"centroid_jump": 1.0, "area_ratio": math.inf, "bbox_size_jump": 1.0}
    centroid_jump = math.hypot(
        (second.centroid_x - first.centroid_x) / CELL_WIDTH,
        (second.centroid_y - first.centroid_y) / CELL_HEIGHT,
    )
    area_ratio = max(first.area, second.area) / min(first.area, second.area)
    first_width = first.bbox[2] - first.bbox[0]
    first_height = first.bbox[3] - first.bbox[1]
    second_width = second.bbox[2] - second.bbox[0]
    second_height = second.bbox[3] - second.bbox[1]
    bbox_size_jump = max(
        abs(second_width - first_width) / CELL_WIDTH,
        abs(second_height - first_height) / CELL_HEIGHT,
    )
    return {
        "centroid_jump": round(centroid_jump, 6),
        "area_ratio": round(area_ratio, 6),
        "bbox_size_jump": round(bbox_size_jump, 6),
    }


def load_plan(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("race plan must contain a JSON object")
    allowed = {
        "schema_version",
        "seed",
        "steps",
        "state_weights",
        "max_centroid_jump",
        "max_area_ratio",
        "max_bbox_size_jump",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"unknown race-plan fields: {', '.join(unknown)}")
    return value


def run_derby(
    pet_dir: Path,
    *,
    plan_path: Path | None = None,
    seed_override: int | None = None,
    steps_override: int | None = None,
    strict: bool = False,
) -> AuditReport:
    """Run deterministic coverage and continuity checks over the real atlas."""

    plan = load_plan(plan_path)
    seed = int(seed_override if seed_override is not None else plan.get("seed", 564))
    steps = int(steps_override if steps_override is not None else plan.get("steps", 564))
    if steps < 32 or steps > 100_000:
        raise ValueError("steps must be between 32 and 100000")
    max_centroid_jump = float(plan.get("max_centroid_jump", 0.32))
    max_area_ratio = float(plan.get("max_area_ratio", 1.9))
    max_bbox_size_jump = float(plan.get("max_bbox_size_jump", 0.35))

    validation = validate_pet_dir(pet_dir, strict=strict)
    report = AuditReport(f"pet-derby:{pet_dir.resolve()}")
    report.findings.extend(validation.findings)
    if not validation.ok:
        report.metrics["validation"] = validation.to_dict()
        return report

    manifest = validation.metrics["manifest"]
    atlas_path = pet_dir.resolve() / str(manifest["spritesheetPath"])
    with Image.open(atlas_path) as source:
        atlas = source.convert("RGBA")

    features: dict[tuple[int, int], FrameFeature] = {}
    for state in STATE_SPECS:
        for column in range(state.frames):
            features[(state.row, column)] = _frame_feature(crop_cell(atlas, state.row, column))

    continuity: list[dict[str, Any]] = []
    for state in STATE_SPECS:
        for column in range(state.frames):
            following = (column + 1) % state.frames
            metrics = _transition_metrics(
                features[(state.row, column)],
                features[(state.row, following)],
            )
            transition = {
                "state": state.name,
                "from": column,
                "to": following,
                **metrics,
            }
            continuity.append(transition)
            if metrics["centroid_jump"] > max_centroid_jump:
                report.add(
                    "derby.centroid_jump",
                    "error" if strict else "warning",
                    "adjacent frames move too far for the configured race contract",
                    **transition,
                    threshold=max_centroid_jump,
                )
            if metrics["area_ratio"] > max_area_ratio:
                report.add(
                    "derby.area_pop",
                    "error" if strict else "warning",
                    "adjacent frames change visible area too sharply",
                    **transition,
                    threshold=max_area_ratio,
                )
            if metrics["bbox_size_jump"] > max_bbox_size_jump:
                report.add(
                    "derby.bbox_pop",
                    "error" if strict else "warning",
                    "adjacent frames change silhouette size too sharply",
                    **transition,
                    threshold=max_bbox_size_jump,
                )

    weights = dict(DEFAULT_STATE_WEIGHTS)
    supplied_weights = plan.get("state_weights", {})
    if not isinstance(supplied_weights, dict):
        raise ValueError("state_weights must be a JSON object")
    for name, value in supplied_weights.items():
        if name not in weights or not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid state weight: {name}={value!r}")
        weights[name] = value
    if not any(weights.values()):
        raise ValueError("at least one state weight must be positive")

    rng = random.Random(seed)
    choices = [name for name, weight in weights.items() if weight > 0]
    choice_weights = [weights[name] for name in choices]
    frame_counters = {state.name: 0 for state in STATE_SPECS}
    direction_index = rng.randrange(16)
    sequence: list[dict[str, Any]] = []
    visited_states: set[str] = set()
    visited_directions: set[str] = set()
    directions = list(DIRECTION_TO_CELL)
    warmup: list[tuple[str, str | None]] = [
        (name, None) for name in choices if name != "look"
    ]
    if "look" in choices:
        warmup.extend(("look", direction) for direction in directions)
    rng.shuffle(warmup)
    for tick in range(steps):
        if tick < len(warmup):
            selected, forced_direction = warmup[tick]
        else:
            selected = rng.choices(choices, weights=choice_weights, k=1)[0]
            forced_direction = None
        if selected == "look":
            if forced_direction is None:
                direction_index = (direction_index + rng.choice((-1, 1))) % 16
                direction = directions[direction_index]
            else:
                direction = forced_direction
                direction_index = directions.index(direction)
            row, column = DIRECTION_TO_CELL[direction]
            visited_states.add("look")
            visited_directions.add(direction)
            sequence.append(
                {
                    "tick": tick,
                    "state": "look",
                    "direction": direction,
                    "row": row,
                    "column": column,
                }
            )
            continue
        spec = next(state for state in STATE_SPECS if state.name == selected)
        column = frame_counters[selected] % spec.frames
        frame_counters[selected] += 1
        visited_states.add(selected)
        sequence.append(
            {
                "tick": tick,
                "state": selected,
                "row": spec.row,
                "column": column,
            }
        )

    expected_states = set(choices)
    missing_states = sorted(expected_states - visited_states)
    missing_directions = (
        sorted(set(directions) - visited_directions) if "look" in choices else []
    )
    if missing_states:
        report.add(
            "derby.state_coverage",
            "error" if strict else "warning",
            "seeded race did not visit every state family",
            missing=missing_states,
        )
    if missing_directions:
        report.add(
            "derby.direction_coverage",
            "error" if strict else "warning",
            "seeded race did not visit every look direction",
            missing=missing_directions,
        )

    continuity_sorted = sorted(
        continuity,
        key=lambda item: (
            item["centroid_jump"],
            item["area_ratio"],
            item["bbox_size_jump"],
        ),
        reverse=True,
    )
    report.metrics.update(
        {
            "schema_version": 1,
            "seed": seed,
            "steps": steps,
            "state_weights": weights,
            "thresholds": {
                "max_centroid_jump": max_centroid_jump,
                "max_area_ratio": max_area_ratio,
                "max_bbox_size_jump": max_bbox_size_jump,
            },
            "coverage": {
                "states": sorted(visited_states),
                "state_ratio": round(len(visited_states) / len(expected_states), 6),
                "directions": sorted(visited_directions),
                "direction_ratio": (
                    round(len(visited_directions) / 16, 6) if "look" in choices else 1.0
                ),
            },
            "sequence_sha256": sha256_bytes(canonical_json(sequence).encode("utf-8")),
            "sequence": sequence,
            "continuity": continuity,
            "worst_transitions": continuity_sorted[:12],
            "atlas_sha256": validation.metrics["atlas_sha256"],
        }
    )
    return report
