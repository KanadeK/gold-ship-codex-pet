"""Build and verify deterministic release artifacts."""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from golshi_pet.archive import create_bundle, verify_bundle
from golshi_pet.util import sha256_file

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATE_EPOCH = 1_785_369_600


def _run(command: list[str]) -> None:
    environment = {**os.environ, "SOURCE_DATE_EPOCH": str(SOURCE_DATE_EPOCH)}
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")


def _python_artifacts(output: Path) -> dict[str, Path]:
    return {
        path.name: path
        for path in output.iterdir()
        if path.is_file() and path.suffix in {".gz", ".whl"}
    }


def _normalize_sdist(path: Path) -> None:
    """Rewrite a locally built sdist with stable ordering and metadata."""
    with tarfile.open(path, "r:gz") as source:
        members = sorted(source.getmembers(), key=lambda member: member.name)
        payloads: dict[str, bytes] = {}
        for member in members:
            if member.isfile():
                extracted = source.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"cannot read sdist member: {member.name}")
                payloads[member.name] = extracted.read()

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as target:
        for original in members:
            member = copy.copy(original)
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.mtime = SOURCE_DATE_EPOCH
            member.pax_headers = {}
            if member.isdir():
                member.mode = 0o755
            elif member.isfile():
                member.mode = 0o644
            payload = io.BytesIO(payloads[member.name]) if member.isfile() else None
            target.addfile(member, payload)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=temporary,
                compresslevel=9,
                mtime=SOURCE_DATE_EPOCH,
            ) as compressed:
                compressed.write(tar_buffer.getvalue())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _normalize_python_artifacts(artifacts: dict[str, Path]) -> None:
    for path in artifacts.values():
        if path.name.endswith(".tar.gz"):
            _normalize_sdist(path)


def _verify_python_metadata(artifacts: dict[str, Path]) -> None:
    expected_zip = datetime.fromtimestamp(SOURCE_DATE_EPOCH, timezone.utc).timetuple()[:6]
    for path in artifacts.values():
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as wheel:
                if any(member.date_time != expected_zip for member in wheel.infolist()):
                    raise RuntimeError(f"wheel contains a non-reproducible timestamp: {path}")
        elif path.name.endswith(".tar.gz"):
            gzip_header = path.read_bytes()[:10]
            header_mtime = (
                struct.unpack("<I", gzip_header[4:8])[0] if len(gzip_header) == 10 else -1
            )
            if header_mtime != SOURCE_DATE_EPOCH:
                raise RuntimeError(f"sdist contains a non-reproducible gzip header: {path}")
            with tarfile.open(path, "r:gz") as source:
                if any(member.mtime != SOURCE_DATE_EPOCH for member in source.getmembers()):
                    raise RuntimeError(f"sdist contains a non-reproducible timestamp: {path}")


def build_release(output: Path) -> list[Path]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(output),
        ]
    )
    first_python = _python_artifacts(output)
    if len(first_python) != 2:
        raise RuntimeError(f"expected wheel and sdist, found {sorted(first_python)}")
    _normalize_python_artifacts(first_python)
    _verify_python_metadata(first_python)
    time.sleep(1.1)
    with tempfile.TemporaryDirectory(prefix="golshi-python-release-") as temporary:
        second_output = Path(temporary)
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(second_output),
            ]
        )
        second_python = _python_artifacts(second_output)
        if set(first_python) != set(second_python):
            raise RuntimeError("repeated Python builds produced different filenames")
        _normalize_python_artifacts(second_python)
        _verify_python_metadata(second_python)
        for name, first in first_python.items():
            if first.read_bytes() != second_python[name].read_bytes():
                raise RuntimeError(f"determinism check failed: repeated {name} differs")
    bundle = output / "gold-ship.codex-pet"
    create_bundle(ROOT / "pet", bundle)
    verify_bundle(bundle)
    with tempfile.TemporaryDirectory(prefix="golshi-release-") as temporary:
        second = Path(temporary) / "gold-ship.codex-pet"
        create_bundle(ROOT / "pet", second)
        if bundle.read_bytes() != second.read_bytes():
            raise RuntimeError("determinism check failed: repeated pet bundles differ")
    artifacts = sorted(
        (
            path
            for path in output.iterdir()
            if path.is_file() and path.name != "SHA256SUMS"
        ),
        key=lambda path: path.name,
    )
    checksums = "".join(f"{sha256_file(path)}  {path.name}\n" for path in artifacts)
    (output / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
    return [*artifacts, output / "SHA256SUMS"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        artifacts = build_release(args.output)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    for artifact in artifacts:
        print(f"{sha256_file(artifact)}  {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
