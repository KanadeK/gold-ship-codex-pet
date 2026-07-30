from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from golshi_pet.backdrop import _percentile, audit_backdrops, load_backgrounds, load_policy
from golshi_pet.constants import ACTIVE_CELL_COUNT


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_backdrop_audit_is_deterministic_and_writes_evidence(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pet = pet_factory()
    backgrounds = _write_json(
        tmp_path / "backgrounds.json",
        {"backgrounds": [{"id": "ink", "name": "Ink", "color": "#000000"}]},
    )
    policy = _write_json(
        tmp_path / "policy.json",
        {
            "scales": [1.0, 0.5],
            "min_edge_contrast_p10": 1.0,
            "max_low_contrast_fraction": 1.0,
            "low_contrast_ratio": 1.0,
            "alpha_threshold": 32,
        },
    )
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = audit_backdrops(
        pet,
        backgrounds_path=backgrounds,
        policy_path=policy,
        output_dir=first_dir,
    )
    audit_backdrops(
        pet,
        backgrounds_path=backgrounds,
        policy_path=policy,
        output_dir=second_dir,
    )
    assert first.ok
    assert first.metrics["cells_measured"] == ACTIVE_CELL_COUNT
    assert first.metrics["measurement_count"] == ACTIVE_CELL_COUNT * 2
    assert (first_dir / "report.json").read_bytes() == (second_dir / "report.json").read_bytes()
    assert (first_dir / "overview.png").read_bytes() == (
        second_dir / "overview.png"
    ).read_bytes()
    assert "not WCAG" in (first_dir / "report.html").read_text(encoding="utf-8")


def test_backdrop_audit_enforces_policy(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    backgrounds = _write_json(
        tmp_path / "backgrounds.json",
        {"backgrounds": [{"id": "white", "name": "White", "color": "#FFFFFF"}]},
    )
    policy = _write_json(
        tmp_path / "policy.json",
        {
            "scales": [1.0],
            "min_edge_contrast_p10": 21.0,
            "max_low_contrast_fraction": 0.0,
            "low_contrast_ratio": 21.0,
            "alpha_threshold": 255,
        },
    )
    report = audit_backdrops(
        pet_factory(),
        backgrounds_path=backgrounds,
        policy_path=policy,
        output_dir=tmp_path / "out",
    )
    assert not report.ok
    assert any(item.code == "backdrop.weak_edge" for item in report.findings)


def test_backdrop_weak_tail_alone_does_not_reject_cell(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    backgrounds = _write_json(
        tmp_path / "backgrounds.json",
        {"backgrounds": [{"id": "white", "name": "White", "color": "#FFFFFF"}]},
    )
    policy = _write_json(
        tmp_path / "policy.json",
        {
            "scales": [1.0],
            "min_edge_contrast_p10": 21.0,
            "max_low_contrast_fraction": 1.0,
            "low_contrast_ratio": 21.0,
            "alpha_threshold": 32,
        },
    )
    report = audit_backdrops(
        pet_factory(),
        backgrounds_path=backgrounds,
        policy_path=policy,
        output_dir=tmp_path / "out",
    )
    assert report.ok
    assert not report.findings
    assert all(
        measurement["edge_contrast_p10"] < 21.0
        for measurement in report.metrics["measurements"]
    )


@pytest.mark.parametrize(
    "value, message",
    [
        ({}, "non-empty"),
        (
            {
                "backgrounds": [
                    {"id": "same", "name": "One", "color": "#000000"},
                    {"id": "same", "name": "Two", "color": "#FFFFFF"},
                ]
            },
            "unique",
        ),
        (
            {"backgrounds": [{"id": "bad", "name": "Bad", "color": "black"}]},
            "#RRGGBB",
        ),
        ({"backgrounds": [1]}, "object"),
        (
            {"backgrounds": [{"id": "bad", "name": "", "color": "#000000"}]},
            "needs a name",
        ),
        (
            {"backgrounds": [{"id": "bad", "name": "Bad", "color": "#GGGGGG"}]},
            "#RRGGBB",
        ),
    ],
)
def test_background_schema_rejects_bad_values(
    tmp_path: Path,
    value: object,
    message: str,
) -> None:
    path = _write_json(tmp_path / "backgrounds.json", value)
    with pytest.raises(ValueError, match=message):
        load_backgrounds(path)


@pytest.mark.parametrize(
    "value, message",
    [
        ({"unknown": 1}, "unknown"),
        ({"scales": []}, "scales"),
        ({"min_edge_contrast_p10": 0.5}, "at least"),
        ({"max_low_contrast_fraction": 2}, "0 through 1"),
        ({"alpha_threshold": 0}, "1 through 255"),
    ],
)
def test_policy_rejects_bad_values(
    tmp_path: Path,
    value: object,
    message: str,
) -> None:
    path = _write_json(tmp_path / "policy.json", value)
    with pytest.raises(ValueError, match=message):
        load_policy(path)


def test_backdrop_returns_validation_evidence_for_bad_pet(tmp_path: Path) -> None:
    backgrounds = _write_json(
        tmp_path / "backgrounds.json",
        {"backgrounds": [{"id": "ink", "name": "Ink", "color": "#000000"}]},
    )
    policy = _write_json(tmp_path / "policy.json", {})
    report = audit_backdrops(
        tmp_path / "missing",
        backgrounds_path=backgrounds,
        policy_path=policy,
        output_dir=tmp_path / "out",
    )
    assert not report.ok
    assert "validation" in report.metrics
    assert not (tmp_path / "out").exists()


def test_json_loader_and_empty_percentile_errors(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be read"):
        load_backgrounds(malformed)
    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_policy(not_object)
    assert _percentile([], 0.5) == 0.0
