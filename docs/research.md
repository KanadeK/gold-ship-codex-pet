# Character selection research

Research date: 2026-07-30

## Decision

The selected character is **Gold Ship** from *Umamusume: Pretty Derby*.

The decision combined four constraints:

1. The character must already exist and be recognizable. No invented mascot.
2. Popularity must be substantial enough to support discovery.
3. The rights holder must publish a usable fan-work boundary.
4. No matching Codex pet could be found in the checked public catalogs or local
   project history.

## Candidate screen

| Candidate | Popularity signal | Collision result | Rights or continuity concern | Decision |
| --- | --- | --- | --- | --- |
| Gold Ship | Official character portal, official media host role, globally released game | No matching Codex pet found | Must stay within Cygames fan-work guidelines | Selected |
| Zundamon | Strong Japanese creator ecosystem | Existing Codex pet and Codex voice integrations found | Would repeat existing work | Rejected |
| Gawr Gura | Multi-million subscriber history | No direct pet match found | Graduation on 2025-05-01 weakens current continuity | Rejected |

## Primary sources

- [Official Gold Ship character page](https://umamusume.jp/character/goldship)
- [Cygames derivative work guidelines](https://umamusume.jp/derivativework_guidelines/)
- [Umamusume on Steam](https://store.steampowered.com/app/3224770/Umamusume_Pretty_Derby/)
- [SteamDB charts](https://steamdb.info/app/3224770/charts/)

The guidelines are the controlling source for fan-work behavior. They can
change. Contributors and redistributors must review the current page rather
than treating this 2026 snapshot as permanent legal advice.

## Collision search

The following exact and normalized terms were checked:

- `"Gold Ship" "Codex Pet"`
- `"Gold Ship Codex pet"`
- `"ゴールドシップ" Codex pet`
- `golshi codex pet`
- `gorushi codex pet`
- `gold-ship-codex-pet`
- `spritesheet.webp "gold ship"`
- `"spriteVersionNumber" "Gold Ship"`

Search surfaces:

- GitHub repository and code search
- [awesome-codex-pet](https://github.com/legeling/awesome-codex-pet)
- [codex-anime-pets](https://github.com/chenxin-dlut/codex-anime-pets)
- [Petdex](https://github.com/crafter-station/petdex)
- codex-pet.org
- petscodex and codexpets.directory
- local repositories and prior project notes

No matching result was found on the research date. This is evidence of a public
gap, not an absolute claim that no private, deleted, renamed, or unindexed
implementation exists.

## Product gap

Existing pet projects commonly provide a validator, installer, doctor,
rollback, trace replay, or image diff. The chosen project adds two different
reusable contracts:

- seeded transition coverage and continuity testing across state families and
  all look directions
- palette-driven, multi-scale foreground-edge measurement over every active
  cell, with deterministic evidence

Neither tool claims to prove artistic quality or WCAG conformance for artwork.
They catch specific mechanical regressions and preserve evidence for review.

## Popularity caveat

Popularity metrics change continuously. Steam activity, social following, and
video views were used as selection signals, not promises of GitHub stars. Star
potential also depends on documentation, release reliability, community
distribution, and whether the reusable Action solves a real maintainer problem.
