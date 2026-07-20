# Changelog

All notable changes to the ISO-build pipeline are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers here are the internal build tags used in commit/testing
notes (`1`–`11`), not semantic-versioned releases.

## [Unreleased]

No unreleased changes.

## [11] - 2026-07-20

### Fixed

- String-bank slots left empty in the US original were being filled with
  German text by the gap-fill step (`difflib`-based alignment). The engine
  treats an empty slot as "clear to spaces," and the player-name entry
  screen prefills from one of these slots — a filled slot leaked leftover
  text into typed town/player names (`"bonn"` became `"bonnSchmetterling"`).

## [10] - 2026-07-20

### Added

- `build.sh` — runs the full pipeline and prints the output ISO's sha1.

### Fixed

- Cutscene-driver control codes (`SetDemoOrder`, `MsgTimeEnd`) were
  sometimes dropped during PAL-to-US tag conversion, soft-locking the intro
  after the player-select name question. Codes present in the US original
  but lost in conversion are now appended before the message terminator.

## [9] - 2026-07-19

### Fixed

- PAL's stateful highlight-color tags (color-on/color-off pair) were
  converted to a single frozen color-on code with no matching reset,
  painting entire dialogs grey/tinted past the intended highlighted word.
  Now converted to the US engine's count-based color code, with the count
  measured on the converted German text span.

## [8] - 2026-07-19

### Fixed

- PAL presentation tags (text color, character/line scale, background
  music ID) carry a parameter in trailing payload bytes; the tag-to-code
  table was ignoring the payload and replaying one frozen parameter for
  every occurrence of a tag (e.g. one scale value for all `SetCharScale`
  uses, causing tiny or oversized first letters). Conversion is now
  payload-aware: exact `(tag, payload)` lookup, then payload pass-through
  where PAL and US params are identical, then nearest-payload matching for
  scale tags, then the old generic template as a last resort.

## [7] - 2026-07-19

### Fixed

- PAL string-bank entries (used for on-screen names/items typed by the
  player) carry a 3-byte grammar prefix for German article agreement that
  the US engine has no concept of; it was being copied straight into
  fixed-size name fields as junk glyphs and ate into the field's padding.
  Prefixes are now stripped for the US-format banks (kept when reading
  PAL data, since real umlaut glyphs use overlapping byte values).

## [6] - 2026-07-19

### Fixed

- The PAL-to-US date/time insert-code table (year, month, weekday, day,
  hour, minute, second) was incomplete — codes with only a single training
  example fell below the vote threshold and were silently dropped,
  producing garbled date confirmations (e.g. a missing weekday name).
  Completed the table from EU disc alignment and allowed unambiguous
  single-witness tags into the map.
- Extended the "stub rescue" (recovering PAL entries relocated to a
  different index) from the main dialog bank to the ten secondary banks.

## [5] - 2026-07-19

### Fixed

- Flow-critical control codes — choice-menu triggers, next-message
  branch links, select-string references — were being dropped for
  messages where PAL restructured the dialog (e.g. into short stub
  entries), leaving choice dialogs with no visible Yes/No options and
  branch targets pointing at the wrong text. These codes are now
  transplanted verbatim from the US original after conversion, since the
  US and German select/main banks are index-aligned.

## [4] - 2026-07-19

### Fixed

- **Critical boot bug**: the port loads `forest_1st.arc`/`forest_2nd.arc`
  into a fixed-size ARAM pool at startup. The previous packing strategy
  (append-in-place) left the original English data as dead bytes and
  appended the German data after it, growing the archives past the pool's
  budget and crashing the port immediately after video init. Replaced
  with a compact repacker that rebuilds each archive's data area in
  place (German data replaces English, no dead bytes).

### Verified

- First build booting into German dialog on real Anbernic hardware.

## [1]-[3] - pre-session

Initial extraction/conversion pipeline (archive/message parsing, entry
mapping, main dialog bank, ten secondary banks, NPC names). Superseded
scripts and intermediate data from this phase were removed after the v4
rebuild; see `CLAUDE.md` for the historical detail,
including an earlier archive-parsing bug (wrong data-area base offset)
that invalidated a whole prior modeling attempt before it was found and
fixed.
