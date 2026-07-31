# Changelog

All notable changes to the ISO-build pipeline are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers are the internal build tags used in commit/testing notes
(`1`–`11`), not semantic-versioned releases.

## [Unreleased]

### Added

- German **item names** (fruit, tools, clothing, furniture — 2271 across 18 tables), patched into `foresta.rel`. Like the menu labels, these are baked into the module (not the message banks), so the port showed English ("orange", "green shirt", "wave print"). The German bytes come from a *different* PAL overlay (`forestd.rel` in `german.tgc`), where the same 18 `itemName_*`/`ftrName*` tables have byte-identical sizes and slot order — so they copy verbatim slot-for-slot (charmap-correct). New: `make_rel_item_map.py` (reads both linker maps, calibrates by content anchor, builds `maps/rel_item_map.json`), `p15_patch_rel_items.py` (patches p14's output in place, asserting English per slot).
- **Suppressed item articles** (p15 also zeroes the `itemArt_*`/`ftrArt` tables). The string bank localizes a/an/the to ein/eine/der/die, but the article index is chosen by English a/an-by-vowel rules, so German gender came out wrong ("eine Apfel"); the US 4-slot article model can't express German gender/case. Zeroing the tables makes `mIN_get_item_article` return NONE, so items show as bare names.
- German **menu-command labels** (`Grab`→`Nehmen`, `Quit`→`Beenden`, `Give Away`→`Verschenken`, item sub-menus, `Yes/No`…), patched into the `foresta.rel` main module — these live outside the 11 message banks, so the prior pipeline left them English. New: `relpack.py` (Yaz0), `make_rel_label_map.py` (locates the label tables by content anchor and copies German bytes verbatim), `p14_patch_rel.py`, `maps/rel_label_map.json`.
- `LICENSE` — MIT, covering this project's own tooling.
- `config.py` — central ISO filenames (`US_ISO`, `EU_ISO`, `OUT_ISO`), consumed by `p13` and `build.sh`.

### Fixed

- Sector-pad the trimmed ISO tail; the newly-appended `foresta.rel.szs` (non-32-byte-aligned, last file) made the loader's tail read run past EOF → "disc could not be read" at boot.

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
