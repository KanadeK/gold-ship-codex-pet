# Security policy

## Supported version

The newest GitHub Release is supported. Older tags receive fixes only when the
same issue affects the newest release.

## Private reporting

Use
[GitHub private vulnerability reporting](https://github.com/KanadeK/gold-ship-codex-pet/security/advisories/new).
Do not open a public issue for:

- archive traversal, symlink, or extraction bypasses
- install path escape or backup loss
- release checksum or workflow compromise
- leaked credentials or personal data
- sensitive rights-holder requests

Include the exact version, operating system, command, exit code, and a minimal
reproduction that does not contain a real secret.

## Response

The maintainer will acknowledge a complete report when available, reproduce it
in an isolated directory, and coordinate a fix and disclosure. Do not test
against another person's Codex home or publish working exploitation details
before a fixed release exists.

## Scope note

The artwork QA heuristics do not make security claims. Character rights and
takedown requests are governed by [ASSET_LICENSE.md](ASSET_LICENSE.md), not the
MIT software warranty.
