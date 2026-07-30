"""Dependency-free structural checks for the static project page."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

BANNED_TEXT = (
    "\u2013",
    "\u2014",
    "quietly in use at",
    "scroll to explore",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.images: list[tuple[str, str | None, str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag in {"a", "link", "script"}:
            target = values.get("href") or values.get("src")
            if target:
                self.links.append(target)
        if tag == "img" and values.get("src"):
            self.images.append(
                (
                    str(values["src"]),
                    values.get("alt"),
                    values.get("width"),
                    values.get("height"),
                )
            )


def check_web(root: Path, *, require_assets: bool = False) -> list[str]:
    html_path = root / "index.html"
    text = html_path.read_text(encoding="utf-8")
    issues = [
        f"banned visible pattern found: {pattern!r}"
        for pattern in BANNED_TEXT
        if pattern.lower() in text.lower()
    ]
    parser = PageParser()
    parser.feed(text)
    for required in ("main", "atlas", "qa", "install"):
        if required not in parser.ids:
            issues.append(f"missing required section id: {required}")
    if len(parser.images) < 3:
        issues.append("page must use at least three real project images")
    for source, alt, width, height in parser.images:
        if not alt:
            issues.append(f"image lacks alt text: {source}")
        if not width or not height:
            issues.append(f"image lacks intrinsic dimensions: {source}")
        if require_assets and not (root / source).is_file():
            issues.append(f"local image is missing: {source}")
    for target in parser.links:
        parsed = urlparse(target)
        if parsed.scheme or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if path and not (root / path).is_file():
            issues.append(f"local linked asset is missing: {target}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("web"))
    parser.add_argument("--require-assets", action="store_true")
    args = parser.parse_args()
    try:
        issues = check_web(args.root, require_assets=args.require_assets)
    except OSError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}", file=sys.stderr)
        return 1
    print(f"PASS: web structure is complete at {args.root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
