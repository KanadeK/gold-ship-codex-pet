# Architecture

## Trust boundaries

### Read-only inspection

`manifest.py`, `atlas.py`, `derby.py`, and `backdrop.py` read the pet and emit
findings. They do not modify the pet package.

### Untrusted archives

`archive.py` accepts a `.codex-pet` file only when:

- member names are unique and exactly expected
- paths are relative and contain no traversal or backslashes
- members are not symbolic links
- member and total sizes stay below configured limits
- every payload member is covered by `SHA256SUMS`
- extracted content passes strict v2 validation

### Installation writes

`install.py` validates before write, obtains an exclusive lock, copies into a
staging directory, compares hashes, moves the previous install to a backup,
atomically swaps the stage, and validates again. Exceptions restore the prior
package when possible.

Rollback validates its chosen backup before moving anything. When a current
install exists, rollback preserves it as another backup.

## Modules

| Module | Responsibility |
| --- | --- |
| `manifest.py` | UTF-8 JSON schema, safe relative sprite path, pet id |
| `atlas.py` | format-v2 geometry, 73 animation cells, neutral slot, chroma, motion heuristics |
| `derby.py` | deterministic state sequence and continuity metrics |
| `backdrop.py` | multi-background edge contrast heuristic and evidence |
| `archive.py` | deterministic bundle, archive and checksum validation |
| `install.py` | staged install, doctor, uninstall, rollback |
| `html_report.py` | self-contained Derby evidence |
| `cli.py` | stable command and exit-code surface |

## Exit codes

- `0`: operation completed and the report contains no error findings
- `1`: a valid command produced a failing audit or install result
- `2`: command input, filesystem, archive, or policy parsing failed

All audit and operational commands support JSON output so CI and repair tooling
do not need to scrape human text.

## Determinism

- Derby uses an explicit seed and canonical JSON hashing.
- JSON evidence is key-sorted and newline-terminated.
- PNG evidence uses fixed dimensions and encoder options.
- Bundles use a 1980 ZIP timestamp, fixed Unix mode, fixed ordering, and fixed
  compression choices.
- Release building creates the pet bundle twice and compares raw bytes.
