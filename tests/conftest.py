from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from golshi_pet.constants import (
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    NEUTRAL_LOOK_FRAME,
    STATE_SPECS,
)


@pytest.fixture
def pet_factory(tmp_path: Path) -> Callable[..., Path]:
    counter = 0

    def make_pet(
        *,
        name: str | None = None,
        size: tuple[int, int] = (ATLAS_WIDTH, ATLAS_HEIGHT),
        empty_cell: tuple[int, int] | None = None,
        dirty_unused: tuple[int, int] | None = None,
        sprite_path: str = "spritesheet.webp",
    ) -> Path:
        nonlocal counter
        counter += 1
        root = tmp_path / (name or f"pet-{counter}")
        root.mkdir()
        atlas = Image.new("RGBA", size, (0, 0, 0, 0))
        if size == (ATLAS_WIDTH, ATLAS_HEIGHT):
            draw = ImageDraw.Draw(atlas)
            for state in STATE_SPECS:
                for column in range(state.frames):
                    if empty_cell == (state.row, column):
                        continue
                    left = column * CELL_WIDTH
                    top = state.row * CELL_HEIGHT
                    shift_x = (column % 3) - 1
                    shift_y = (column % 2)
                    color = (
                        90 + (state.row * 13) % 130,
                        30 + (column * 17) % 140,
                        80 + (state.row * 9 + column * 7) % 150,
                        255,
                    )
                    draw.rounded_rectangle(
                        (
                            left + 52 + shift_x,
                            top + 32 + shift_y,
                            left + 140 + shift_x,
                            top + 190 + shift_y,
                        ),
                        radius=14,
                        fill=color,
                        outline=(34, 24, 44, 255),
                        width=3,
                    )
                    draw.rectangle(
                        (
                            left + 74 + column,
                            top + 54,
                            left + 76 + column,
                            top + 56,
                        ),
                        fill=(245, 214, 92, 255),
                    )
            if empty_cell != NEUTRAL_LOOK_FRAME:
                neutral_row, neutral_column = NEUTRAL_LOOK_FRAME
                left = neutral_column * CELL_WIDTH
                top = neutral_row * CELL_HEIGHT
                draw.rounded_rectangle(
                    (left + 52, top + 32, left + 140, top + 190),
                    radius=14,
                    fill=(165, 72, 118, 255),
                    outline=(34, 24, 44, 255),
                    width=3,
                )
            if dirty_unused is not None:
                row, column = dirty_unused
                draw.rectangle(
                    (
                        column * CELL_WIDTH + 80,
                        row * CELL_HEIGHT + 80,
                        column * CELL_WIDTH + 100,
                        row * CELL_HEIGHT + 100,
                    ),
                    fill=(255, 0, 0, 255),
                )
        atlas.save(root / "spritesheet.webp", "WEBP", lossless=True, method=6)
        manifest = {
            "id": "gold-ship",
            "displayName": "Gold Ship",
            "description": "Fixture pet.",
            "spriteVersionNumber": 2,
            "spritesheetPath": sprite_path,
        }
        (root / "pet.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return root

    return make_pet
