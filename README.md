# Animal Crossing (GameCube) — German localization of the US (GAFE01) release

Rebuilds the USA `GAFE01` Animal Crossing ISO with German text extracted from
the EU (PAL) disc. The US disc's dialog engine is kept as-is (control codes,
choice menus, cutscene triggers); only the text and a handful of PAL-only
presentation tags (colors, scale) are translated across. The result is an
ordinary US ISO — usable on real hardware, in an emulator, or with the
[OpenCrossing-Anbernic](https://github.com/GabeConway/OpenCrossing-Anbernic)
native port.

Verified booting with German text on real Anbernic hardware (via the
OpenCrossing-Anbernic port).

**You need your own legally-owned copies** of the USA and EU (PAL) Animal
Crossing discs to use this — none are included or distributed here.

## Requirements

- Python 3, no third-party packages
- Your own ISOs:
  - `isos/Animal Crossing (USA).iso`
  - `isos/Animal Crossing (Europe) (En,Fr,De,Es,It).nkit.iso`

  If your filenames differ, edit them once in `config.py` (`US_ISO`, `EU_ISO`,
  `OUT_ISO`). An NKit `.nkit.iso` works; compressed `.nkit.gcz`/`.rvz` do not —
  convert those back to `.iso` first.

## Quick start

```bash
./build.sh
```

Extracts and converts the dialog/text banks, rebuilds the two archives that
hold them, and packs a new ISO at
`output/Animal Crossing (USA) [German].iso`. Takes under a minute; prints the
output ISO's sha1 when done. Re-extracting from the source ISOs (if
`extracted/` is missing) is documented in `CLAUDE.md`.

## How it works, briefly

1. Extract the German and English text banks from the EU disc (BMG format)
   and the English text banks from the US disc (a different string-table
   format), archive-by-archive.
2. Align US entries to PAL (German/English) entries by matching stripped text
   (index-aligned for the main dialog bank; `difflib` for the ten secondary
   banks), then learn a mapping from PAL's presentation tags to the US
   engine's control codes — including tag *parameters* (color, scale, music
   IDs), not just the tag types.
3. Convert each German PAL message into the US control-code dialect, transplant flow-critical
   codes (choice menus, cutscene triggers) verbatim from the US original so
   dialog branching and demo scripting stay intact, and fall back to English
   for anything that can't be converted safely.
4. Rebuild the two RARC archives that hold these banks compactly (matching
   the ARAM budget the port allocates for them) and patch the rebuilt
   archives into a copy of the US ISO.

Full technical detail — every gotcha, the exact control-code tables, and the
reasoning behind each fix — is in `CLAUDE.md`.

## Folder layout

| Folder | Contents | Tracked in git? |
|---|---|---|
| `isos/` | Your source ISOs (not included) | no |
| `extracted/` | Raw disc/archive extracts | no (regenerated) |
| `maps/` | Entry/tag mapping JSONs | **yes** — `entry_map_v2.json` isn't regenerable by the current scripts |
| `build/` | Rebuilt text banks | no (regenerated) |
| `output/` | Final arcs + ISO | no (regenerated) |

The control-code semantics, ARAM layout, and charmap/control-code tables this
project relies on are documented in the upstream reference projects linked
below — see [ACreTeam/ac-decomp](https://github.com/ACreTeam/ac-decomp) and
[Cuyler36/Animal-Crossing-Text-Editor](https://github.com/Cuyler36/Animal-Crossing-Text-Editor)
directly rather than a vendored copy here.

## Credits / references

- [ACreTeam/ac-decomp](https://github.com/ACreTeam/ac-decomp) — game engine
  source, used to identify control-code semantics and ARAM layout.
- [Cuyler36/Animal-Crossing-Text-Editor](https://github.com/Cuyler36/Animal-Crossing-Text-Editor) —
  charmap and control-code tables.
- [GabeConway/OpenCrossing-Anbernic](https://github.com/GabeConway/OpenCrossing-Anbernic) —
  the native port this ISO targets.

## License

The tooling in this repository is released under the [MIT License](LICENSE).

The license covers only this project's own code. It contains no game assets or
copyrighted disc data — only tooling to convert your own legally-owned discs.
Animal Crossing and its data are the property of Nintendo; the reference
projects credited above retain their respective licenses.
