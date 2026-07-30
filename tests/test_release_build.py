from __future__ import annotations

import io
import tarfile
from pathlib import Path

from scripts.build_release import (
    SOURCE_DATE_EPOCH,
    _normalize_sdist,
    _verify_python_metadata,
)


def _write_sdist(
    path: Path,
    entries: list[tuple[str, bytes]],
    *,
    mtime: int,
    uid: int,
) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in entries:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            member.mtime = mtime
            member.uid = uid
            member.gid = uid
            member.uname = f"user-{uid}"
            member.gname = f"group-{uid}"
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(payload))


def test_sdist_normalization_is_byte_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    entries = [
        ("package-0.1.0/pyproject.toml", b"[build-system]\n"),
        ("package-0.1.0/src/package.py", b"VALUE = 1\n"),
    ]
    _write_sdist(first, entries, mtime=111, uid=1001)
    _write_sdist(second, list(reversed(entries)), mtime=999, uid=2002)

    _normalize_sdist(first)
    _normalize_sdist(second)

    assert first.read_bytes() == second.read_bytes()
    _verify_python_metadata({first.name: first})
    with tarfile.open(first, "r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == sorted(member.name for member in members)
        assert all(member.mtime == SOURCE_DATE_EPOCH for member in members)
        assert all(member.uid == 0 and member.gid == 0 for member in members)
        assert all(member.mode == 0o644 for member in members)
