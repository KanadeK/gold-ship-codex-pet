"""Small deterministic and path-safety helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_relative_safe(value: str) -> bool:
    candidate = Path(value)
    if candidate.is_absolute() or candidate.root or candidate.drive or not value or "\x00" in value:
        return False
    return all(part not in {"", ".", ".."} for part in candidate.parts)


def resolve_within(root: Path, relative: str) -> Path:
    if not is_relative_safe(relative):
        raise ValueError(f"unsafe relative path: {relative!r}")
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    if os.path.commonpath((str(root_resolved), str(target))) != str(root_resolved):
        raise ValueError(f"path escapes root: {relative!r}")
    return target


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
