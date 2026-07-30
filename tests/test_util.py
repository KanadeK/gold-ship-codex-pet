from __future__ import annotations

from pathlib import Path

import pytest

from golshi_pet.reporting import AuditReport
from golshi_pet.util import (
    canonical_json,
    is_relative_safe,
    resolve_within,
    sha256_bytes,
    sha256_file,
    write_json,
)


def test_deterministic_helpers(tmp_path: Path) -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert sha256_bytes(b"x") == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
    assert resolve_within(tmp_path, "pet/file") == (tmp_path / "pet" / "file").resolve()
    with pytest.raises(ValueError, match="unsafe|escapes"):
        resolve_within(tmp_path, "../escape")
    assert not is_relative_safe("")
    assert not is_relative_safe("/absolute")
    assert not is_relative_safe("bad\x00path")

    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"abc")
    assert sha256_file(artifact) == sha256_bytes(b"abc")
    output = tmp_path / "nested" / "report.json"
    write_json(output, {"value": 1})
    assert output.read_text(encoding="utf-8") == '{\n  "value": 1\n}\n'


def test_audit_report_counts_and_extend() -> None:
    first = AuditReport("one")
    first.add("one.warning", "warning", "warning")
    second = AuditReport("two")
    second.add("two.error", "error", "error", item=2)
    second.metrics["x"] = 1
    first.extend(second)
    value = first.to_dict()
    assert not value["ok"]
    assert value["counts"] == {"error": 1, "warning": 1, "info": 0}
    assert value["metrics"]["x"] == 1
