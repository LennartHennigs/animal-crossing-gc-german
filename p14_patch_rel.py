#!/usr/bin/env python3
"""Patch German menu-command labels into foresta.rel (Group A).

The action/selection menu labels are fixed 20-byte records (16-byte space-padded
text + 4 NUL) baked into the main module foresta.rel, so the p8..p13 message-bank
pipeline never localized them. This step:

  1. pulls foresta.rel.szs from the US ISO (by FST name — no hardcoded offsets),
  2. decompresses it (relpack / Yaz0),
  3. locates the label-record run *by content anchor* ("Write Letter"),
  4. overwrites each record's 16-byte field in place with the German bytes from
     maps/rel_label_map.json (built by make_rel_label_map.py from the German
     module, so the game-font charmap encoding is already correct),
  5. recompresses to output/foresta_de.rel.szs for p13.build_iso to inject.

Every write is in-place and same-length (field stays 16 bytes, terminator stays
4 NUL) so no pointers/relocations shift. Each slot is content-checked against the
expected English text before writing; a mismatch (e.g. a different ROM revision
that reordered the table) aborts rather than corrupting the module.
"""
import json, os
import relpack
from make_rel_label_map import load_us_rel, table
from config import US_ISO

OUT = "output/foresta_de.rel.szs"
MAP = "maps/rel_label_map.json"


def patch(rel, entries):
    recs = table(rel, "Write Letter")
    if len(recs) != len(entries):
        raise SystemExit(f"table has {len(recs)} records, map has {len(entries)}")
    buf = bytearray(rel)
    n = 0
    for e, (off, field) in zip(entries, recs):
        if field.decode("latin1") != e["en"]:
            raise SystemExit(
                f"slot {e['i']}: expected {e['en']!r}, found "
                f"{field.decode('latin1')!r} — table/revision mismatch, aborting")
        if not e["de_hex"]:
            continue
        de = bytes.fromhex(e["de_hex"])
        assert len(de) <= 16
        buf[off:off + 16] = de + b" " * (16 - len(de))   # space-pad, keep 4-NUL term
        n += 1
    return bytes(buf), n


def main():
    entries = json.load(open(MAP))
    rel = load_us_rel(US_ISO)
    patched, n = patch(rel, entries)
    assert len(patched) == len(rel), "length changed — refusing to write"
    os.makedirs("output", exist_ok=True)
    comp = relpack.yaz0_compress(patched)
    assert relpack.yaz0_decompress(comp) == patched, "recompress round-trip failed"
    open(OUT, "wb").write(comp)
    print(f"patched {n} labels; {OUT} ({len(comp)} bytes, "
          f"rel {len(rel)} -> {len(comp)} compressed)")


if __name__ == "__main__":
    main()
