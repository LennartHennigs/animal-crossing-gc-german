# Animal Crossing GameCube — German localization of the US ISO

Goal: make [OpenCrossing-Anbernic](https://github.com/GabeConway/OpenCrossing-Anbernic)
show German text. The port is compiled from the USA `GAFE01` decompilation and only
accepts a USA ISO, which it uses purely as an asset source. Per the maintainer
(issue #3): keep the USA ISO, apply a translation mod to it.

## Source material

| File | What it is |
|---|---|
| `Animal Crossing (USA).iso` | GAFE01 rev0, asset source for the port |
| `Animal Crossing (Europe) … .nkit.iso` | GAFP01. Contains **five self-contained game images** (`tgc/forest_<lang>_Final_PAL50.tgc`), one per language |

NKit stripping does not break the filesystem: the FST and the German/English TGC
regions parse fine with `gc_fst.py`.

## Where the text lives

**US (GAFE01):** `forest_2nd.arc` → `data/message_data.bin` (2.7 MB stream) +
`data/message_data_table.bin` (17,500 u32 slots, 16,744 used). Table semantics per
`mMsg_Get_BodyParam` (ac-decomp `src/game/m_msg_main.c_inc`):
`entry[i] = data[table[i-1] : table[i]]`, `entry[0] = data[0 : table[0]]` —
i.e. **table stores end offsets**. Smaller banks (mail, item strings, select menus…)
are `*_data.bin` / `*_data_table.bin` pairs in `forest_1st.arc`.

**German PAL:** inside `forest_Gmn_Final_PAL50.tgc` → `forest_msg.arc` →
`data/msg.bin`: a small `ROOT`/`DATA` wrapper, then at 0x100 a standard **BMG**
(`MESGbmg1`) with INF1 (16,273 messages, 4-byte entries) + DAT1 (3.4 MB pool).
The English TGC has the same structure with identical message ids — DE and EN
BMGs are index-aligned translations of each other.

## Message model (the key insight)

- A PAL BMG message = **one whole dialog**.
- A US table entry = **one page/window chunk**. Dialogs span several consecutive
  entries chained by `7F 01` (CONTINUE) codes; text streams across entry
  boundaries, so entries legitimately begin mid-word. Dialog ends at `7F 00`
  (LAST), select-window, or msg-time-end codes.
- Validated concretely: PAL message 4520 (EN "Are you ready for the best festival
  of the whole summer?…" / DE "Bist du bereit für das beste Fest des ganzen
  Sommers?…") appears verbatim as the US stream spanning entries ~5000–5001.

## Encoding

- Character encoding is **identical** between US and PAL: one byte per char,
  custom table (see `Animal_Crossing_Character_Map` in Cuyler36's
  Animal-Crossing-Text-Editor). Umlauts/ß already exist in the US charset:
  `0x02 Ä, 0x17 Ö, 0x1C Ü, 0x1D ß, 0x5D ä, 0x8C ö, 0x92 ü`, newline `0xCD`.
  → No font hacking needed.
- **Control codes differ**:
  - US: `7F <id> <params>` — sizes per id from `ControlCodeSizeTable`
    (GCNParser.cs / ac-decomp `m_font.h` enum `mFont_CONT_CODE_*`).
  - PAL: `80 <size> <group> <idx16> <data…>` — self-sized tags.
  These need a semantic mapping (derivable statistically from aligned
  EN-PAL ↔ US pairs, since EN text largely matches US text).

## Alignment measurements

- Message counts: US main bank 16,744 entries ≈ 12,600+ dialogs; PAL BMG 16,273
  messages (likely includes the smaller banks' content too).
- Exact text equality US↔EN-PAL is only ~17% (PAL English was re-edited), but
  order is preserved: unique-string anchors are 55/55 monotonic with index delta
  drifting ≈ −480…−497. Banded 4-gram fuzzy matching maps ~10,400 entries with
  ≥0.5 similarity; dialog-level matching should do much better.

## Constraints / open items

- Hardcoded strings compiled into the port's binary stay English (would need
  patches in the OpenCrossing source, not the ISO).
- Textures containing text (signs etc.) are out of scope.
- Per-entry text buffer limit `mMsg_MSG_BUF_MAX` must be respected when
  re-paginating German (longer than English) into US entry chains.
- The port validates GAFE01 — the modified ISO keeps its header, so it loads.

## Correction (v2): the extraction bug that explained everything

`rarc.py` originally used the wrong data-area base (`header[0x08]+0x20` instead
of `header[0x0C]+0x20`), shifting every extracted file (−0x760 in
forest_2nd.arc, −0x100 in forest_msg.arc). The "US entries start mid-word /
pagination chains" model was an artifact of that shift. With correct
extraction:

- **US entries and PAL BMG messages correspond ~1:1 at the same index**:
  13,162 of 16,273 are byte-identical after code-stripping; difflib matching
  blocks + gap fill map 16,263 of 16,744 US entries (all but the US-only
  extras).
- The BMG "ROOT wrapper" was actually the RARC's own node table; msg.bin
  starts directly with `MESGbmg1`.
- Tag→code table from 11,108 identical-text pairs: 199 mappings, 98.2%+
  instance coverage on the German corpus.
- PAL group-19 tags are grammatical gender-variant selectors
  (`Er\xFESie\xFEEs`) with no US equivalent → first variant inlined.

## Result

`Animal Crossing (USA) [German].iso` — GAFE01 with 16,263 of 16,744 main-bank
entries in German. Verified: round-trip extraction bit-exact, all other archive
files untouched, max entry 1508 ≤ 1536 buffer limit.

Known gaps (v1): smaller banks (mail, item names, select menus in
forest_1st.arc) still English; ~600 gender-selector tag instances dropped
(minor grammar artifacts); strings compiled into the port stay English.

## v3: secondary banks (menus, mail, item names, villager names)

- PAL keeps the German text for the small banks as per-bank BMGs in
  `forest_1st_script.arc` (`mail/maila/mailb/mailc/ps/psz/select/string/
  super/superz.bin`); US equivalents are the `*_data(_table).bin` pairs in
  `forest_1st.arc` with the same end-offset semantics.
- Entry counts match the US banks almost exactly → near-identity mapping.
  Replaced: mail 975/982, maila-c 383/384 each, ps 981/982, psz 383/384,
  select 606/607, string 2035/2047, super 902/982, superz 383/384.
- `string.bin` quirk: its INF1 size field is file-absolute, not
  section-relative (handled in `msglib.load_bmg`). String entries carry
  3-byte grammar-metadata prefixes — copied verbatim.
- `npc_name_str_table.bin` (8-byte records): swapped wholesale for the German
  table (official German villager names: Jens, Bianca, Miezi, Tanja, …).
- Final ISO (34 MB) verified round-trip bit-exact for all replaced banks;
  untouched files identical; dialog bank from v2 intact.
