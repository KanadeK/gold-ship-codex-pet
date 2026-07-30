"""Validate-before-write, recoverable Codex pet installation."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
import zipfile
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from .archive import BUNDLE_FILES, verify_bundle
from .atlas import validate_pet_dir
from .util import sha256_file


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _target_paths(codex_home: Path, pet_id: str) -> tuple[Path, Path]:
    home = codex_home.expanduser().resolve()
    if not pet_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in pet_id):
        raise ValueError("pet id must be a lowercase kebab-case slug")
    target = home / "pets" / pet_id
    backup_root = home / "pet-backups" / pet_id
    return target, backup_root


class InstallLock(AbstractContextManager["InstallLock"]):
    """Small cross-platform exclusive lock with clear failure behavior."""

    def __init__(self, codex_home: Path) -> None:
        self.path = codex_home.resolve() / ".gold-ship-codex-pet.lock"
        self.fd: int | None = None

    def __enter__(self) -> InstallLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError(
                f"another pet operation holds {self.path}; remove it only after "
                "confirming no operation runs"
            ) from exc
        os.write(self.fd, f"pid={os.getpid()}\n".encode())
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.path.unlink(missing_ok=True)


def _package_hashes(pet_dir: Path) -> dict[str, str]:
    return {
        name: sha256_file(pet_dir / name)
        for name in ("pet.json", "spritesheet.webp")
        if (pet_dir / name).is_file()
    }


def install_pet(
    source: Path,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    source = source.resolve()
    report = validate_pet_dir(source, strict=True)
    if not report.ok:
        raise ValueError(f"source pet failed validation: {report.to_dict()}")
    manifest = report.metrics["manifest"]
    pet_id = str(manifest["id"])
    home = (codex_home or default_codex_home()).expanduser().resolve()
    target, backup_root = _target_paths(home, pet_id)
    result: dict[str, Any] = {
        "ok": True,
        "action": "install",
        "dry_run": dry_run,
        "source": str(source),
        "target": str(target),
        "pet_id": pet_id,
        "source_hashes": _package_hashes(source),
        "backup": None,
    }
    if dry_run:
        result["would_replace"] = target.exists()
        return result

    pets_root = target.parent
    pets_root.mkdir(parents=True, exist_ok=True)
    staging = pets_root / f".{pet_id}.staging-{uuid.uuid4().hex}"
    backup: Path | None = None
    with InstallLock(home):
        try:
            shutil.copytree(source, staging)
            staged_report = validate_pet_dir(staging, strict=True)
            if not staged_report.ok:
                raise RuntimeError(f"staged pet failed validation: {staged_report.to_dict()}")
            if _package_hashes(staging) != result["source_hashes"]:
                raise RuntimeError("staged package hashes differ from the source")
            if target.exists():
                backup_root.mkdir(parents=True, exist_ok=True)
                stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                backup = backup_root / f"{stamp}-{uuid.uuid4().hex[:8]}"
                target.replace(backup)
                result["backup"] = str(backup)
            staging.replace(target)
            installed_report = validate_pet_dir(target, strict=True)
            if not installed_report.ok or _package_hashes(target) != result["source_hashes"]:
                raise RuntimeError("post-install validation or hash comparison failed")
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            if backup is not None and backup.exists() and not target.exists():
                backup.replace(target)
            raise
    result["installed_hashes"] = _package_hashes(target)
    return result


def install_bundle(
    bundle: Path,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Verify an untrusted release bundle before installing its exact contents."""

    bundle = bundle.resolve()
    verification = verify_bundle(bundle)
    with tempfile.TemporaryDirectory(prefix="golshi-install-") as temporary:
        source = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            for name in BUNDLE_FILES:
                (source / name).write_bytes(archive.read(name))
        result = install_pet(source, codex_home=codex_home, dry_run=dry_run)
    result["bundle"] = str(bundle)
    result["bundle_sha256"] = verification["sha256"]
    return result


def uninstall_pet(
    pet_id: str,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    home = (codex_home or default_codex_home()).expanduser().resolve()
    target, backup_root = _target_paths(home, pet_id)
    result: dict[str, Any] = {
        "ok": True,
        "action": "uninstall",
        "dry_run": dry_run,
        "target": str(target),
        "pet_id": pet_id,
        "backup": None,
    }
    if not target.exists():
        result["changed"] = False
        return result
    if dry_run:
        result["changed"] = True
        return result
    with InstallLock(home):
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        backup = backup_root / f"uninstalled-{stamp}-{uuid.uuid4().hex[:8]}"
        target.replace(backup)
        result["backup"] = str(backup)
        result["changed"] = True
    return result


def doctor_pet(
    source: Path,
    *,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    source = source.resolve()
    source_report = validate_pet_dir(source, strict=True)
    manifest = source_report.metrics.get("manifest", {})
    pet_id = str(manifest.get("id", "gold-ship"))
    home = (codex_home or default_codex_home()).expanduser().resolve()
    target, _ = _target_paths(home, pet_id)
    installed_report = validate_pet_dir(target, strict=True)
    source_hashes = _package_hashes(source)
    installed_hashes = _package_hashes(target)
    hashes_match = source_hashes == installed_hashes and bool(source_hashes)
    return {
        "ok": source_report.ok and installed_report.ok and hashes_match,
        "action": "doctor",
        "pet_id": pet_id,
        "source": source_report.to_dict(),
        "installed": installed_report.to_dict(),
        "source_hashes": source_hashes,
        "installed_hashes": installed_hashes,
        "hashes_match": hashes_match,
        "repair_command": f"golshi-pet install {source}",
    }


def rollback_pet(
    pet_id: str,
    *,
    codex_home: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore the newest valid backup while preserving the current install."""

    home = (codex_home or default_codex_home()).expanduser().resolve()
    target, backup_root = _target_paths(home, pet_id)
    candidates = sorted(
        (path for path in backup_root.glob("*") if path.is_dir()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    if not candidates:
        raise ValueError(f"no backup exists for {pet_id}")
    selected = candidates[0]
    validation = validate_pet_dir(selected, strict=True)
    if not validation.ok:
        raise ValueError(
            f"newest backup is invalid: {selected}; inspect older backups without overwriting"
        )
    result: dict[str, Any] = {
        "ok": True,
        "action": "rollback",
        "dry_run": dry_run,
        "pet_id": pet_id,
        "backup": str(selected),
        "target": str(target),
        "preserved_current": None,
    }
    if dry_run:
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    with InstallLock(home):
        if target.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            preserved = backup_root / f"before-rollback-{stamp}-{uuid.uuid4().hex[:8]}"
            target.replace(preserved)
            result["preserved_current"] = str(preserved)
        selected.replace(target)
    result["installed_hashes"] = _package_hashes(target)
    return result
