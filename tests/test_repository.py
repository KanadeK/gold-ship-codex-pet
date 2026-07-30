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
