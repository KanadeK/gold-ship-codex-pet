from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from golshi_pet.archive import (
    MAX_MEMBER_SIZE,
    _validate_member,
    create_bundle,
    verify_bundle,
)
from golshi_pet.util import sha256_bytes


def test_bundle_is_deterministic_and_verifiable(
    pet_factory: Callable[..., Path], tmp_path: Path
) -> None:
    pet = pet_factory()
    first = tmp_path / "first.codex-pet"
    second = tmp_path / "second.codex-pet"
    first_result = create_bundle(pet, first)
    second_result = create_bundle(pet, second)
    assert first.read_bytes() == second.read_bytes()
    assert first_result["sha256"] == second_result["sha256"]
    assert verify_bundle(first)["ok"]
    with zipfile.ZipFile(first) as bundle:
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in bundle.infolist())


def test_bundle_rejects_traversal(tmp_path: Path) -> None:
    malicious = tmp_path / "malicious.codex-pet"
    with zipfile.ZipFile(malicious, "w") as bundle:
        bundle.writestr("../pet.json", "{}")
        bundle.writestr("pet.json", "{}")
        bundle.writestr("spritesheet.webp", b"x")
        bundle.writestr("SHA256SUMS", "")
    with pytest.raises(ValueError, match="members|unsafe"):
        verify_bundle(malicious)


def test_bundle_rejects_checksum_tamper(
    pet_factory: Callable[..., Path], tmp_path: Path
) -> None:
    valid = tmp_path / "valid.codex-pet"
    create_bundle(pet_factory(), valid)
    tampered = tmp_path / "tampered.codex-pet"
    with zipfile.ZipFile(valid) as source, zipfile.ZipFile(tampered, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "pet.json":
                data += b" "
            target.writestr(item, data)
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(tampered)


def test_create_bundle_rejects_invalid_pet(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="strict validation"):
        create_bundle(pet_factory(empty_cell=(0, 0)), tmp_path / "bad.codex-pet")


def test_archive_member_guard_rejects_symlink_and_size() -> None:
    symlink = zipfile.ZipInfo("pet.json")
    symlink.create_system = 3
    symlink.external_attr = 0o120777 << 16
    with pytest.raises(ValueError, match="symbolic"):
        _validate_member(symlink)

    huge = zipfile.ZipInfo("spritesheet.webp")
    huge.file_size = MAX_MEMBER_SIZE + 1
    with pytest.raises(ValueError, match="too large"):
        _validate_member(huge)


def test_bundle_rejects_duplicate_and_bad_checksum_lines(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.codex-pet"
    with (
        pytest.warns(UserWarning, match="Duplicate"),
        zipfile.ZipFile(duplicate, "w") as bundle,
    ):
        bundle.writestr("pet.json", "{}")
        bundle.writestr("pet.json", "{}")
        bundle.writestr("spritesheet.webp", b"x")
        bundle.writestr("SHA256SUMS", "")
    with pytest.raises(ValueError, match="duplicate"):
        verify_bundle(duplicate)

    bad_lines = tmp_path / "bad-lines.codex-pet"
    with zipfile.ZipFile(bad_lines, "w") as bundle:
        bundle.writestr("pet.json", "{}")
        bundle.writestr("spritesheet.webp", b"x")
        bundle.writestr("SHA256SUMS", "not a checksum")
    with pytest.raises(ValueError, match="invalid line"):
        verify_bundle(bad_lines)

    incomplete = tmp_path / "incomplete.codex-pet"
    with zipfile.ZipFile(incomplete, "w") as bundle:
        bundle.writestr("pet.json", "{}")
        bundle.writestr("spritesheet.webp", b"x")
        bundle.writestr("SHA256SUMS", f"{sha256_bytes(b'{}')}  pet.json\n")
    with pytest.raises(ValueError, match="does not cover"):
        verify_bundle(incomplete)


def test_bundle_rejects_valid_checksums_for_invalid_pet(tmp_path: Path) -> None:
    manifest = b'{"id":"gold-ship"}'
    atlas = b"not-an-image"
    checksums = (
        f"{sha256_bytes(manifest)}  pet.json\n"
        f"{sha256_bytes(atlas)}  spritesheet.webp\n"
    )
    bundle_path = tmp_path / "invalid-pet.codex-pet"
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("pet.json", manifest)
        bundle.writestr("spritesheet.webp", atlas)
        bundle.writestr("SHA256SUMS", checksums)
    with pytest.raises(ValueError, match="strict validation"):
        verify_bundle(bundle_path)
