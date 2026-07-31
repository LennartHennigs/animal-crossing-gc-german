#!/usr/bin/env python3
"""Build maps/rel_item_map.json: US item names -> German bytes.

In-game item names (pockets, shop, catalog, letters, ...) are fixed 16-byte
space-padded records baked into the main module's .data as the `itemName_*` and
`ftrName*` tables. The US module (`foresta.rel`) holds them in English, so the
port shows "orange" / "green shirt" / "wave print" even on the German build:
unlike the dialog banks, these strings are not in the message archives, and
unlike the menu-command labels (patched by p14), they are a separate, much
larger set of tables.

The German PAL disc keeps the same item names in a *different* overlay,
`forestd.rel` (inside `german.tgc`), at different offsets — but with the SAME
per-table record counts and the SAME slot order as US (verified: every one of
the 18 tables has byte-identical size in both linker maps, and spot-checked
slot-for-slot: net->Kescher, spooky wardrobe->Kürbisschrank, ...). So the German
bytes can be copied verbatim, which also keeps the game-font charmap encoding
(ä=0x5d, ö=0x8c, ü=0x92, ...) correct by construction — same principle as the
menu-label harvest in make_rel_label_map.py.

This builder:
  1. reads both linker maps (`foresta.map` from the US ISO, `forestd.map` from
     `german.tgc`) to get each table's (vaddr, size) — no hardcoded offsets,
  2. decompresses both modules and calibrates each one's vaddr->file base from a
     content anchor, then validates that every table lands on printable 16-byte
     records (guards against a bad base / revision drift),
  3. for each table, aligns US<->German slot-for-slot and records the German
     bytes for every slot whose English and German are both real (printable,
     non-blank) and actually differ.

Output mirrors maps/rel_label_map.json: a list of per-table objects
{name, vaddr, size, slots:[{i, en, de_hex}]}, where `de_hex` is the German bytes
with trailing padding stripped (p15 re-pads to 16). Slots left English are
omitted. `vaddr` is the US module address; p15 recalibrates the base and asserts
each slot's English before writing, so a revision mismatch aborts rather than
corrupting the module.
"""
import json, os
import relpack
from gc_fst import parse_disc, read_fst, parse_tgc_header
from make_rel_label_map import glyph
from config import US_ISO

TGC = "extracted/german.tgc"
REC = 16
OUT = "maps/rel_item_map.json"

# The 18 item-name tables, by symbol name. Order is cosmetic (output only).
TABLES = [
    "itemName_paper", "itemName_money", "itemName_tool", "itemName_fish",
    "itemName_cloth", "itemName_etc", "itemName_carpet", "itemName_wall",
    "itemName_fruit", "itemName_plant", "itemName_minidisk", "itemName_dummy",
    "itemName_ticket", "itemName_insect", "itemName_hukubukuro", "itemName_kabu",
    "ftrName_table", "ftrName2_table",
]

# Content anchors used to calibrate each module's vaddr->file-offset base. Each
# is (table, slot, exact_text): a record we can predict in that module. The US
# anchor is a distinctive English paper name; the German anchor is a distinctive
# German fruit name (both verified unique enough that the full record matches).
US_ANCHOR = ("itemName_paper", 0, b"airmail paper")
DE_ANCHOR = ("itemName_fruit", 7, b"Kokosnuss")


def us_inner(name):
    """Read a file from the US ISO by its FST name."""
    with open(US_ISO, "rb") as f:
        _, _, fo, fs = parse_disc(f)
        for p, off, size, _ in read_fst(f, 0, fo, fs):
            if p == name:
                f.seek(off)
                return f.read(size)
    raise SystemExit(f"{name} not found in US ISO")


def de_inner(name):
    """Read a file from german.tgc by its inner FST name (TGC offset shift)."""
    with open(TGC, "rb") as f:
        _, fo, fs, fa, vfa = parse_tgc_header(f, 0)
        for p, off, size, _ in read_fst(f, 0, fo, fs, file_area_shift=fa - vfa):
            if p == name:
                f.seek(off)
                return f.read(size)
    raise SystemExit(f"{name} not found in {TGC}")


def parse_map(mapbytes, want=lambda s: s in TABLES):
    """Parse a CodeWarrior linker map: symbol -> (vaddr, size). First hit wins.
    `want(symbol)` picks which symbols to keep (default: the item-name TABLES)."""
    out = {}
    for line in mapbytes.decode("latin1", "replace").splitlines():
        p = line.split()
        # columns: vaddr size fileoff align symbol \t object
        if len(p) >= 5 and want(p[4]) and p[4] not in out:
            try:
                out[p[4]] = (int(p[0], 16), int(p[1], 16))
            except ValueError:
                pass
    return out


# Charmap glyph bytes that live *below* 0x20: the game font packs the capital
# umlauts and eszett into the control range, so a plain "printable >= 0x20" test
# would wrongly reject real German names ("weiß", "Öko-Outfit", "Äffchen") and
# leave them English. (Lowercase ä/ö/ü and other letters are >= 0x80.)
LOW_GLYPHS = {0x02, 0x17, 0x1d}  # Ä, Ö, ß


def is_real(rec):
    """True if a stripped record is a real, printable name (ASCII or charmap)."""
    return bool(rec) and all(
        0x20 <= c < 0x7F or c >= 0x80 or c in LOW_GLYPHS for c in rec)


def calibrate(blob, mp, anchor):
    """Return the vaddr->file-offset base: base = pos(anchor) - anchor_vaddr."""
    table, slot, text = anchor
    vaddr = mp[table][0] + slot * REC
    pos = blob.find(text.ljust(REC, b" "))
    if pos < 0:
        raise SystemExit(f"calibration anchor {text!r} not found in module")
    return pos - vaddr


def field(blob, base, vaddr, i):
    o = base + vaddr + i * REC
    return blob[o:o + REC].rstrip(b" ")


def validate(blob, base, mp, label):
    """Assert every table lands mostly on printable records (base sanity)."""
    for name in TABLES:
        v, sz = mp[name]
        recs = [field(blob, base, v, i) for i in range(sz // REC)]
        good = sum(1 for r in recs if is_real(r) or r == b"")
        # A correct base leaves tables almost entirely printable (a few unused
        # slots hold junk); a wrong base turns everything to garbage (~0%). 0.7
        # separates the two cleanly while tolerating real unused slots.
        if good < len(recs) * 0.7:
            raise SystemExit(
                f"{label} base {base:#x} looks wrong: table {name} only "
                f"{good}/{len(recs)} printable")


def build():
    usmap = parse_map(us_inner("foresta.map"))
    demap = parse_map(de_inner("forestd.map"))
    missing = [t for t in TABLES if t not in usmap or t not in demap]
    if missing:
        raise SystemExit(f"tables missing from a map: {missing}")
    for t in TABLES:
        if usmap[t][1] != demap[t][1]:
            raise SystemExit(
                f"size mismatch for {t}: US {usmap[t][1]:#x} vs DE {demap[t][1]:#x} "
                f"— slot alignment can't be assumed, aborting")

    us = relpack.yaz0_decompress(us_inner("foresta.rel.szs"))
    de = relpack.yaz0_decompress(de_inner("forestd.rel.szs"))
    us_base = calibrate(us, usmap, US_ANCHOR)
    de_base = calibrate(de, demap, DE_ANCHOR)
    validate(us, us_base, usmap, "US")
    validate(de, de_base, demap, "DE")

    tables = []
    for name in TABLES:
        uv, sz = usmap[name]
        dv, _ = demap[name]
        slots = []
        for i in range(sz // REC):
            en = field(us, us_base, uv, i)
            deb = field(de, de_base, dv, i)
            # Translate only where both sides are real names and they differ;
            # leave shared proper nouns / blank / unused slots as US English.
            if is_real(en) and is_real(deb) and deb != en:
                slots.append({"i": i, "en": en.decode("latin1"), "de_hex": deb.hex()})
        tables.append({"name": name, "vaddr": uv, "size": sz, "slots": slots})
    return tables


if __name__ == "__main__":
    tables = build()
    os.makedirs("maps", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(tables, f, indent=1, ensure_ascii=False)
    total = sum(len(t["slots"]) for t in tables)
    print(f"{OUT}: {total} item names translated across {len(tables)} tables")
    for t in tables:
        print(f"  {t['name']:20} {len(t['slots']):5} / {t['size'] // REC}")
    # small sample for eyeballing
    print("\nsample (first 6 of a few tables):")
    for name in ("itemName_fruit", "itemName_tool", "ftrName_table"):
        t = next(x for x in tables if x["name"] == name)
        print(f"  {name}:")
        for s in t["slots"][:6]:
            print(f"    {s['i']:>4} {s['en']:22} -> {glyph(bytes.fromhex(s['de_hex']))}")
