from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from golshi_pet.constants import CELL_HEIGHT, CELL_WIDTH
from golshi_pet.derby import _frame_feature, _transition_metrics, load_plan, run_derby


def test_derby_is_seeded_and_covers_contract(pet_factory: Callable[..., Path]) -> None:
    pet = pet_factory()
    first = run_derby(pet, seed_override=564, steps_override=128, strict=True)
    second = run_derby(pet, seed_override=564, steps_override=128, strict=True)
    assert first.ok, first.to_dict()
    assert second.ok
    assert first.metrics["sequence_sha256"] == second.metrics["sequence_sha256"]
    assert first.metrics["coverage"]["state_ratio"] == 1.0
    assert first.metrics["coverage"]["direction_ratio"] == 1.0


def test_derby_changes_with_seed(pet_factory: Callable[..., Path]) -> None:
    pet = pet_factory()
    first = run_derby(pet, seed_override=1, steps_override=64)
    second = run_derby(pet, seed_override=2, steps_override=64)
    assert first.metrics["sequence_sha256"] != second.metrics["sequence_sha256"]


def test_plan_rejects_unknown_and_invalid_values(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text('{"unknown": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        load_plan(plan)
    plan.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        load_plan(plan)


def test_derby_rejects_step_abuse(pet_factory: Callable[..., Path]) -> None:
    with pytest.raises(ValueError, match="steps"):
        run_derby(pet_factory(), steps_override=10)


def test_derby_rejects_invalid_weights(
    pet_factory: Callable[..., Path], tmp_path: Path
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"state_weights": {"unknown": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="weight"):
        run_derby(pet_factory(), plan_path=plan)


def test_derby_returns_validation_report_for_bad_pet(tmp_path: Path) -> None:
    report = run_derby(tmp_path / "missing", steps_override=32)
    assert not report.ok
    assert "validation" in report.metrics


def test_derby_enforces_continuity_contract(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    plan = tmp_path / "strict-plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": 32,
                "max_centroid_jump": 0,
                "max_area_ratio": 1,
                "max_bbox_size_jump": 0,
            }
        ),
        encoding="utf-8",
    )
    report = run_derby(pet_factory(), plan_path=plan, strict=True)
    codes = {item.code for item in report.findings}
    assert {"derby.centroid_jump", "derby.area_pop", "derby.bbox_pop"} & codes


def test_derby_weight_schema_and_without_look(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"state_weights": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        run_derby(pet_factory(), plan_path=plan)

    all_zero = {name: 0 for name in (
        "idle",
        "running-right",
        "running-left",
        "waving",
        "jumping",
        "failed",
        "waiting",
        "running",
        "review",
        "look",
    )}
    plan.write_text(json.dumps({"state_weights": all_zero}), encoding="utf-8")
    with pytest.raises(ValueError, match="positive"):
        run_derby(pet_factory(), plan_path=plan)

    all_zero["idle"] = 1
    plan.write_text(
        json.dumps({"steps": 32, "state_weights": all_zero}),
        encoding="utf-8",
    )
    report = run_derby(pet_factory(), plan_path=plan)
    assert report.ok
    assert report.metrics["coverage"]["direction_ratio"] == 1.0
    assert report.metrics["coverage"]["directions"] == []


def test_blank_frame_metrics_are_explicit() -> None:
    blank = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    feature = _frame_feature(blank)
    metrics = _transition_metrics(feature, feature)
    assert feature.area == 0
    assert metrics["area_ratio"] == float("inf")
