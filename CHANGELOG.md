# Changelog

All notable changes to the ISO-build pipeline. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions here are the
internal build tags used in commit/testing notes (`v1`…`v11`), not releases.

## v11 — 2026-07-20

### Fixed
- String-bank slots left empty in the US original were being filled with
  German text by the difflib gap-fill. The engine treats an empty slot as
  "clear to spaces," and the player-name entry screen prefills from one of
  these slots — a filled slot leaked leftover text into typed town/player
  names (`"bonn"` became `"bonnSchmetterling"`).

## v10 — 2026-07-20

### Fixed
- Cutscene-driver control codes (`SetDemoOrder`, `MsgTimeEnd`) were
  sometimes dropped during PAL→US tag conversion, soft-locking the intro
  after the player-select name question. Codes present in the US original
  but lost in conversion are now appended before the message terminator.

### Added
- `build.sh` — runs the full pipeline and prints the output ISO's sha1.

## v9 — 2026-07-19

### Fixed
- PAL's stateful highlight-color tags (color-on/color-off pair) were
  converted to a single frozen color-on code with no matching reset,
  painting entire dialogs grey/tinted past the intended highlighted word.
  Now converted to the US engine's count-based color code, with the count
  measured on the converted German text span.

## v8 — 2026-07-19

### Fixed
- PAL presentation tags (text color, character/line scale, background
  music ID) carry a parameter in trailing payload bytes; the tag→code
  table was ignoring the payload and replaying one frozen parameter for
  every occurrence of a tag (e.g. one scale value for all `SetCharScale`
  uses, causing tiny/oversized first letters). Conversion is now
  payload-aware: exact `(tag, payload)` lookup, then payload pass-through
  where PAL and US params are identical, then nearest-payload matching for
  scale tags, then the old generic template as last resort.

## v7 — 2026-07-19

### Fixed
- PAL string-bank entries (used for on-screen names/items typed by the
  player) carry a 3-byte grammar prefix for German article agreement that
  the US engine has no concept of; it was being copied straight into
  fixed-size name fields as junk glyphs and ate into the field's padding.
  Prefixes are now stripped for the US-format banks (kept when reading
  PAL data, since real umlaut glyphs use overlapping byte values).

## v6 — 2026-07-19

### Fixed
- The PAL→US date/time insert-code table (year, month, weekday, day,
  hour, minute, second) was incomplete — codes with only a single training
  example fell below the vote threshold and were silently dropped,
  producing garbled date confirmations (e.g. a missing weekday name).
  Completed the table from EU disc alignment and allowed unambiguous
  single-witness tags into the map.
- Extended the "stub rescue" (recovering PAL entries relocated to a
  different index) from the main dialog bank to the ten secondary banks.

## v5 — 2026-07-19

### Fixed
- Flow-critical control codes — choice-menu triggers, next-message
  branch links, select-string references — were being dropped for
  messages where PAL restructured the dialog (e.g. into short stub
  entries), leaving choice dialogs with no visible Yes/No options and
  branch targets pointing at the wrong text. These codes are now
  transplanted verbatim from the US original after conversion, since the
  US and German select/main banks are index-aligned.

## v4 — 2026-07-19

### Fixed
- **Critical boot bug**: the port loads `forest_1st.arc`/`forest_2nd.arc`
  into a fixed-size ARAM pool at startup. The previous packing strategy
  (`p9`/`p12`, append-in-place) left the original English data as dead
  bytes and appended the German data after it, growing the archives past
  the pool's budget and segfaulting the port immediately after video init.
  Replaced with `p13_compact_pack.py`, which rebuilds each archive's data
  area compactly (German data replaces English in place, no dead bytes).
- First build verified booting into German dialog on real Anbernic
  hardware.

## v1–v3 — pre-session

Initial extraction/conversion pipeline (RARC/BMG parsing, entry mapping,
main dialog bank + ten secondary banks + NPC names). Superseded scripts
and intermediate JSON from this phase were removed after the v4 rebuild;
see `CLAUDE.md` and `FINDINGS.md` for the historical detail, including an
earlier RARC-parsing bug (wrong data-area base offset) that invalidated a
whole prior modeling attempt before it was found and fixed.
