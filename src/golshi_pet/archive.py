"""Deterministic Codex pet bundle creation and hostile-archive checks."""

from __future__ import annotations

import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .atlas import validate_pet_dir
from .util import sha256_bytes, sha256_file

BUNDLE_FILES = ("pet.json", "spritesheet.webp")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_MEMBER_SIZE = 30 * 1024 * 1024
MAX_TOTAL_SIZE = 45 * 1024 * 1024


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = (
        zipfile.ZIP_DEFLATED if name.endswith((".json", ".txt")) else zipfile.ZIP_STORED
    )
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    return info


def create_bundle(pet_dir: Path, output: Path) -> dict[str, Any]:
    pet_dir = pet_dir.resolve()
    report = validate_pet_dir(pet_dir, strict=True)
    if not report.ok:
        raise ValueError(f"pet failed strict validation: {report.to_dict()}")
    hashes = {name: sha256_file(pet_dir / name) for name in BUNDLE_FILES}
    checksums = "".join(f"{hashes[name]}  {name}\n" for name in BUNDLE_FILES).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", allowZip64=False) as bundle:
        for name in BUNDLE_FILES:
            bundle.writestr(_zip_info(name), (pet_dir / name).read_bytes())
        bundle.writestr(_zip_info("SHA256SUMS"), checksums)
    return {
        "ok": True,
        "output": str(output.resolve()),
        "sha256": sha256_file(output),
        "members": [*BUNDLE_FILES, "SHA256SUMS"],
        "member_hashes": hashes,
    }


def _validate_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe archive member: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ValueError(f"archive member is a symbolic link: {name}")
    if info.file_size > MAX_MEMBER_SIZE:
        raise ValueError(f"archive member is too large: {name}")


def verify_bundle(bundle_path: Path) -> dict[str, Any]:
    bundle_path = bundle_path.resolve()
    with zipfile.ZipFile(bundle_path) as bundle:
        infos = bundle.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate member names")
        expected = {*BUNDLE_FILES, "SHA256SUMS"}
        if set(names) != expected:
            raise ValueError(f"archive members must be exactly {sorted(expected)}")
        total = 0
        for info in infos:
            _validate_member(info)
            total += info.file_size
        if total > MAX_TOTAL_SIZE:
            raise ValueError("archive expands beyond the total size limit")
        raw_checksums = bundle.read("SHA256SUMS").decode("utf-8")
        expected_hashes: dict[str, str] = {}
        for line in raw_checksums.splitlines():
            pieces = line.split("  ", 1)
            if len(pieces) != 2 or pieces[1] not in BUNDLE_FILES:
                raise ValueError("SHA256SUMS has an invalid line")
            expected_hashes[pieces[1]] = pieces[0]
        if set(expected_hashes) != set(BUNDLE_FILES):
            raise ValueError("SHA256SUMS does not cover every package file")
        actual_hashes = {name: sha256_bytes(bundle.read(name)) for name in BUNDLE_FILES}
        if actual_hashes != expected_hashes:
            raise ValueError("bundle member checksum mismatch")
        with tempfile.TemporaryDirectory(prefix="golshi-bundle-") as temp:
            root = Path(temp)
            for name in BUNDLE_FILES:
                (root / name).write_bytes(bundle.read(name))
            validation = validate_pet_dir(root, strict=True)
            if not validation.ok:
                raise ValueError(f"bundled pet failed strict validation: {validation.to_dict()}")
    return {
        "ok": True,
        "bundle": str(bundle_path),
        "sha256": sha256_file(bundle_path),
        "members": names,
        "member_hashes": actual_hashes,
    }
