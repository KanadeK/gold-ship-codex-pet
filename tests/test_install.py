from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from golshi_pet.archive import create_bundle
from golshi_pet.install import (
    InstallLock,
    default_codex_home,
    doctor_pet,
    install_bundle,
    install_pet,
    rollback_pet,
    uninstall_pet,
)


def test_install_doctor_replace_and_uninstall(
    pet_factory: Callable[..., Path], tmp_path: Path
) -> None:
    source = pet_factory()
    codex_home = tmp_path / "codex-home"
    dry = install_pet(source, codex_home=codex_home, dry_run=True)
    assert dry["ok"] and dry["dry_run"]
    assert not Path(dry["target"]).exists()

    installed = install_pet(source, codex_home=codex_home)
    target = Path(installed["target"])
    assert target.is_dir()
    diagnosis = doctor_pet(source, codex_home=codex_home)
    assert diagnosis["ok"], diagnosis

    replacement = install_pet(source, codex_home=codex_home)
    assert replacement["backup"]
    assert Path(replacement["backup"]).is_dir()
    prior = rollback_pet("gold-ship", codex_home=codex_home)
    assert prior["preserved_current"]
    assert Path(prior["preserved_current"]).is_dir()

    removed = uninstall_pet("gold-ship", codex_home=codex_home)
    assert removed["changed"]
    assert Path(removed["backup"]).is_dir()
    assert not target.exists()
    restored = rollback_pet("gold-ship", codex_home=codex_home)
    assert restored["ok"]
    assert target.is_dir()
    rollback_preview = rollback_pet("gold-ship", codex_home=codex_home, dry_run=True)
    assert rollback_preview["dry_run"]


def test_install_verified_bundle(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "gold-ship.codex-pet"
    created = create_bundle(pet_factory(), bundle)
    result = install_bundle(bundle, codex_home=tmp_path / "codex-home")
    assert result["bundle_sha256"] == created["sha256"]
    assert Path(result["target"]).is_dir()


def test_rollback_requires_backup(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no backup"):
        rollback_pet("gold-ship", codex_home=tmp_path / "codex-home")


def test_rollback_rejects_invalid_newest_backup(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    invalid = codex_home / "pet-backups" / "gold-ship" / "newest"
    invalid.mkdir(parents=True)
    with pytest.raises(ValueError, match="newest backup is invalid"):
        rollback_pet("gold-ship", codex_home=codex_home)


def test_uninstall_previews_and_handles_missing(
    pet_factory: Callable[..., Path],
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex-home"
    missing = uninstall_pet("gold-ship", codex_home=codex_home)
    assert not missing["changed"]
    install_pet(pet_factory(), codex_home=codex_home)
    preview = uninstall_pet("gold-ship", codex_home=codex_home, dry_run=True)
    assert preview["changed"]
    assert (codex_home / "pets" / "gold-ship").is_dir()


def test_default_home_and_inert_lock_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "configured"
    monkeypatch.setenv("CODEX_HOME", str(configured))
    assert default_codex_home() == configured
    monkeypatch.delenv("CODEX_HOME")
    assert default_codex_home().name == ".codex"
    lock = InstallLock(tmp_path)
    lock.__exit__()


def test_lock_conflict_is_explicit(
    pet_factory: Callable[..., Path], tmp_path: Path
) -> None:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / ".gold-ship-codex-pet.lock").write_text("busy", encoding="utf-8")
    with pytest.raises(RuntimeError, match="another pet operation"):
        install_pet(pet_factory(), codex_home=codex_home)


def test_invalid_pet_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="kebab"):
        uninstall_pet("../escape", codex_home=tmp_path)
