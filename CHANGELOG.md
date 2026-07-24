# Changelog

All notable changes to the ISO-build pipeline are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers are the internal build tags used in commit/testing notes
(`1`–`11`), not semantic-versioned releases.

## [Unreleased]

### Added

- `LICENSE` — MIT, covering this project's own tooling.
- `config.py` — central ISO filenames (`US_ISO`, `EU_ISO`, `OUT_ISO`), consumed by `p13` and `build.sh`.

### Changed

- README and `CLAUDE.md` updated for public release.

## [11] - 2026-07-20

### Fixed

- Keep US-empty string slots empty; gap-fill was planting German text in them, leaking into typed town/player names.

## [10] - 2026-07-20

### Added

- `build.sh` — runs the full pipeline and prints the output ISO's sha1.

### Fixed

- Preserve cutscene-driver codes (`SetDemoOrder`, `MsgTimeEnd`) lost in conversion; their loss soft-locked the intro.

## [9] - 2026-07-19

### Fixed

- Convert PAL's stateful highlight-color tags to the US count-based color code, so tinting no longer bleeds past the highlighted word.

## [8] - 2026-07-19

### Fixed

- Make tag conversion payload-aware (color/scale/BGM params), instead of replaying one frozen parameter per tag.

## [7] - 2026-07-19

### Fixed

- Strip the 3-byte German grammar prefix from US-format string banks, where it rendered as junk glyphs in name fields.

## [6] - 2026-07-19

### Fixed

- Complete the PAL-to-US date/time insert-code table (single-witness tags were dropped, garbling date confirmations).
- Extend "stub rescue" (relocated PAL entries) to the ten secondary banks.

## [5] - 2026-07-19

### Fixed

- Transplant flow-critical codes (choice menus, branch links, select strings) verbatim from the US original, restoring Yes/No options and branch targets.

## [4] - 2026-07-19

### Fixed

- **Critical boot bug**: repack archives compactly instead of appending German data; the old dead-byte padding overflowed the port's ARAM pool and crashed at boot.

### Verified

- First build booting into German dialog on real Anbernic hardware.

## [1]-[3] - pre-session

Initial extraction/conversion pipeline (archive/message parsing, entry mapping,
main dialog bank, ten secondary banks, NPC names). Superseded scripts and data
removed after the v4 rebuild; see `CLAUDE.md` for historical detail, including
an earlier archive-parsing bug (wrong data-area base offset).
