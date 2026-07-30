# Repair playbook

## Preserve evidence first

Copy the failing command, exit code, JSON output, selected input files, and the
current `CODEX_HOME` path. Do not remove a lock, pet, or backup until you have
confirmed its role.

## Validation failure

```bash
golshi-pet validate pet --strict --json > validation.json
```

Use the stable finding code and its row or column context. Repair only the named
manifest field or cell. Rerun strict validation before any audit or install.

## Derby failure

```bash
golshi-pet derby pet \
  --plan examples/gold-ship-chaos-race.json \
  --strict \
  --json-out build/pet-derby/report.json \
  --html-out build/pet-derby/report.html
```

Keep the seed and thresholds unchanged while repairing. Inspect the named
adjacent frames. A changed seed hides the original reproduction.

## Backdrop failure

```bash
golshi-pet backdrop-audit pet \
  --backgrounds examples/backgrounds.json \
  --policy examples/backdrop-policy.json \
  --output-dir build/backdrop-audit \
  --json
```

Open `build/backdrop-audit/report.html`, find the row, column, scale, and
background in the JSON findings, then strengthen that edge without changing
the policy. If the policy itself is wrong, change it in a separate reviewed
commit with before-and-after evidence.

## Archive failure

```bash
golshi-pet verify-bundle gold-ship.codex-pet --json
```

Never bypass checksum or path validation. Download the Release asset again and
compare its SHA-256 with Release `SHA256SUMS`. If it still differs, report the
Release as compromised or incorrectly uploaded.

## Installer lock

The error prints the exact lock path. Confirm no `golshi-pet` process is still
running. Remove only that file, then run a dry-run install. Never remove the
whole Codex home or pets directory.

## Drift and rollback

```bash
golshi-pet doctor pet --json
golshi-pet rollback --pet-id gold-ship --dry-run --json
golshi-pet rollback --pet-id gold-ship --json
```

Doctor compares source and installed hashes. Rollback validates the newest
backup first and preserves the current install before restoring. If the newest
backup is invalid, the command stops without changing the active pet. Inspect
older backups manually and validate them before moving anything.

## CI failure

Record the Python, Ruff, MyPy, and pytest versions shown in the job. Reproduce
with the same Python and tool versions instead of assuming an older local
environment exercises every current rule:

```bash
python -m pip install -e ".[dev]"
python -m ruff --version
python scripts/release_check.py
```

If a `--no-isolation` build reports that `setuptools.build_meta` is
unavailable, install the checked-in `requirements-dev.txt` and verify that all
entries from `[build-system].requires` are also declared in the `dev` extra.
Do not remove `--no-isolation` merely to hide an undeclared build dependency.

Do not move a tag or replace a Release asset until the exact tagged commit
passes locally and in GitHub Actions.

## Pages `configure-pages` Not Found

A new repository can contain a correct Pages workflow while the Pages site
itself is still disabled. If `actions/configure-pages` reports `Get Pages site
failed` with `Not Found` after the site build passed:

1. Open **Settings → Pages** for the repository.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Rerun the failed Pages workflow and wait for both `build` and `deploy`.
4. Request the published HTTPS URL and confirm it serves the expected commit.

Do not add `enablement: true` with the default `GITHUB_TOKEN`: the
`configure-pages` action requires a separate token with administration and
Pages write permissions for automatic enablement. Keep that stronger token out
of an ordinary public workflow.
