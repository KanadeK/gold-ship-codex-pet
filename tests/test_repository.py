from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_github_yaml_is_parseable() -> None:
    files = [
        ROOT / "action.yml",
        ROOT / ".github" / "dependabot.yml",
        *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
        *sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml")),
    ]
    assert files
    for path in files:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(value, dict), path


def test_public_document_links_exist() -> None:
    for name in (
        "ASSET_LICENSE.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "NOTICE.md",
        "README.md",
        "SECURITY.md",
        "docs/architecture.md",
        "docs/qa-contract.md",
        "docs/repair.md",
        "docs/research.md",
    ):
        path = ROOT / name
        assert path.is_file(), name
        assert path.stat().st_size > 20, name


def test_no_official_reference_is_publicly_tracked() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "artwork/source-reference/" in ignore
    assert "artwork/hatch-run/" in ignore


def test_site_builder_uses_published_contact_sheet() -> None:
    builder = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    assert "final-contact-sheet.png" not in builder
    assert (ROOT / "artwork" / "qa" / "contact-sheet.png").is_file()


def test_curated_qa_reports_are_portable() -> None:
    reports = sorted((ROOT / "artwork" / "qa").glob("*.json"))
    assert reports
    for path in reports:
        text = path.read_text(encoding="utf-8")
        assert "C:\\\\" not in text, path
        assert "D:\\\\" not in text, path
        assert "hatch-run" not in text, path


def test_no_isolation_build_declares_backend_dependencies() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    release_builder = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")

    assert '"--no-isolation"' in release_builder
    assert '"setuptools>=75,<90"' in pyproject
    assert '"wheel>=0.45,<1"' in pyproject
    assert "setuptools==" in requirements
    assert "wheel==" in requirements


def test_release_workflows_use_pinned_development_environment() -> None:
    for name in ("ci.yml", "pages.yml", "release.yml"):
        workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "python -m pip install -r requirements-dev.txt" in workflow
        assert 'python -m pip install -e ".[dev]"' not in workflow
