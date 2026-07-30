# Contributing

Thank you for improving the pet or its reusable QA tools.

## Before opening a change

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python scripts/release_check.py
```

For a code-only change made before the final pet asset is available, use:

```bash
python -m ruff check src tests scripts
python -m mypy src/golshi_pet scripts
python -m pytest -q
python scripts/secret_scan.py
python scripts/check_web.py web
```

## Change rules

- Add or update tests for every behavior change.
- Keep machine-readable finding codes stable unless the change is explicitly
  breaking.
- Do not weaken an audit threshold to hide a failing frame. Submit the visual
  repair and before-and-after evidence.
- Do not commit official source art, credentials, personal data, generated
  caches, or local Codex home contents.
- Never add `Co-authored-by` trailers without the named person's informed
  consent.
- Keep the code license and fan-art rights notice separate.

## Asset changes

Every atlas change must include:

- a complete 1536 x 2288 format-v2 WebP
- the contact sheet and blind look-direction QA evidence
- strict validator, Pet Derby, and Backdrop Gauntlet reports
- updated `pet/provenance.json` hashes
- a short visual rationale

Do not reuse official screenshots or another artist's work as the released
sprite. References stay uncommitted.

## Pull request evidence

Include:

- operating system and Python version
- exact acceptance commands
- test count and coverage
- relevant JSON finding codes
- screenshots for visual or Pages changes
- recovery impact for installer or archive changes

Small focused changes are easier to review than mixed code, art, and policy
changes.
