"""Shared Codex pet contract constants."""

from __future__ import annotations

from dataclasses import dataclass

VERSION = "0.1.0"
ATLAS_COLUMNS = 8
ATLAS_ROWS = 11
CELL_WIDTH = 192
CELL_HEIGHT = 208
ATLAS_WIDTH = ATLAS_COLUMNS * CELL_WIDTH
ATLAS_HEIGHT = ATLAS_ROWS * CELL_HEIGHT
NEUTRAL_LOOK_FRAME = (0, 6)


@dataclass(frozen=True, slots=True)
class StateSpec:
    """One row in the Codex v2 pet atlas."""

    name: str
    row: int
    frames: int
    directions: tuple[str, ...] = ()


STATE_SPECS: tuple[StateSpec, ...] = (
    StateSpec("idle", 0, 6),
    StateSpec("running-right", 1, 8),
    StateSpec("running-left", 2, 8),
    StateSpec("waving", 3, 4),
    StateSpec("jumping", 4, 5),
    StateSpec("failed", 5, 8),
    StateSpec("waiting", 6, 6),
    StateSpec("running", 7, 6),
    StateSpec("review", 8, 6),
    StateSpec(
        "look-row-9",
        9,
        8,
        ("000", "022.5", "045", "067.5", "090", "112.5", "135", "157.5"),
    ),
    StateSpec(
        "look-row-10",
        10,
        8,
        ("180", "202.5", "225", "247.5", "270", "292.5", "315", "337.5"),
    ),
)

STATE_BY_NAME = {state.name: state for state in STATE_SPECS}
DIRECTION_TO_CELL = {
    direction: (state.row, column)
    for state in STATE_SPECS
    for column, direction in enumerate(state.directions)
}
ACTIVE_CELL_COUNT = sum(state.frames for state in STATE_SPECS)
SPECIAL_CELL_COUNT = 1
USED_CELL_COUNT = ACTIVE_CELL_COUNT + SPECIAL_CELL_COUNT
UNUSED_CELL_COUNT = ATLAS_COLUMNS * ATLAS_ROWS - USED_CELL_COUNT
