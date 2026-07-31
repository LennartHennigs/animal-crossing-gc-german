#!/usr/bin/env python3
"""Build maps/rel_label_map.json: US menu-command labels -> German bytes.

The action/selection menu labels live in fixed 20-byte records (16-byte
space-padded text + 4 NUL) inside foresta.rel, NOT in the translated message
banks, so they stay English. This builder locates those record tables *by
content anchor* (revision-independent — no hardcoded offsets) in both the US
module and the German module (from german.tgc), aligns them, and copies the
German bytes verbatim so the game-font charmap encoding (e.g. u-umlaut=0x92) is
correct by construction.

Alignment notes (see repo history / plan): the German build splits the labels
into 3 tables (8 + 31 + 32). US table2/3 align 1:1 with German table2/3 except
for one German-only record ("Zurück") that is skipped. US "Open" (x2) and
"Rewrite" have no German source and are left English (null).

Output is position-indexed and carries the expected English text per slot, so
the patcher (p14) can assert the located table still matches before writing —
if a different revision reorders the table, p14 aborts instead of corrupting.
"""
import json, os, struct
import relpack
from gc_fst import u32

US_SZS_INNER = "foresta.rel.szs"


def load_us_rel(us_iso):
    with open(us_iso, "rb") as f:
        from gc_fst import parse_disc, read_fst
        _, _, fo, fs = parse_disc(f)
        for p, off, size, _ in read_fst(f, 0, fo, fs):
            if p == US_SZS_INNER:
                f.seek(off)
                return relpack.yaz0_decompress(f.read(size))
    raise SystemExit("foresta.rel.szs not found in US ISO")


def load_de_rel(tgc="extracted/german.tgc"):
    f = open(tgc, "rb").read()
    u = lambda o: struct.unpack_from(">I", f, o)[0]
    shift = u(0x24) - u(0x34)
    fst = f[u(0x10):u(0x10) + u(0x14)]
    n = struct.unpack_from(">I", fst, 8)[0]; sb = n * 12
    for i in range(1, n):
        nm = struct.unpack_from(">I", fst, i * 12)[0] & 0xFFFFFF
        a, b = struct.unpack_from(">II", fst, i * 12 + 4)
        name = fst[sb + nm:fst.index(b"\0", sb + nm)].decode()
        if name == US_SZS_INNER:
            return relpack.yaz0_decompress(f[a + shift:a + shift + b])
    raise SystemExit("foresta.rel.szs not found in german.tgc")


def is_rec(d, off):
    if off < 0 or off + 20 > len(d) or d[off + 16:off + 20] != b"\0\0\0\0":
        return False
    s = d[off:off + 16].rstrip(b" ")
    return bool(s) and b"\0" not in s and all(32 <= c < 127 or c >= 0x80 for c in s)


def table(d, anchor):
    """Return list of (offset, 16-byte-field) for the contiguous record run
    containing `anchor`."""
    a = d.find(anchor.encode("latin1"))
    if a < 0:
        raise SystemExit(f"anchor not found: {anchor!r}")
    s = a
    while is_rec(d, s - 20):
        s -= 20
    e = a
    while is_rec(d, e + 20):
        e += 20
    e += 20
    return [(o, d[o:o + 16].rstrip(b" ")) for o in range(s, e, 20)]


def build(us_iso):
    us = load_us_rel(us_iso)
    de = load_de_rel()
    us_recs = table(us, "Write Letter")           # one contiguous 73-record run
    de1 = table(de, "Aufstellen")                 # 8
    de2 = table(de, "Wegwerfen")                  # 31 (index 12 = "Zurück", skip)
    de3 = table(de, "Alles wegwerfen")            # 32

    # Position map: US record index -> (de_table, de_index) or None (keep English)
    pairs = {}
    for k in range(8):            # de1 -> US[1..8]
        pairs[1 + k] = (de1, k)
    for k in range(12):           # de2[0..11] -> US[10..21]
        pairs[10 + k] = (de2, k)
    for k in range(13, 31):       # de2[13..30] -> US[22..39]  (skip de2[12] "Zurück")
        pairs[22 + (k - 13)] = (de2, k)
    for k in range(32):           # de3[0..31] -> US[41..72]
        pairs[41 + k] = (de3, k)
    # The German build lists de3[22]="Als Outfit"(clothes) before de3[23]=
    # "Als Schirm"(umbrella), the reverse of US slots 63/64. The US engine
    # indexes by slot, so map per US meaning: swap them back.
    pairs[63] = (de3, 23)         # Drop as Umbrella -> Als Schirm
    pairs[64] = (de3, 22)         # Drop as Clothes  -> Als Outfit

    # US 0/40 (Open) and 9 (Rewrite) have no counterpart in the German command
    # tables. "Öffnen" exists elsewhere in the German module (capital O-umlaut =
    # 0x17) -> harvest verbatim. "Rewrite" exists nowhere in the module; encode
    # a plain-ASCII German string (no charmap glyphs needed), tagged "manual".
    oeffnen = de[de.find(b"\x17ffnen"):de.find(b"\x17ffnen") + 6]  # b"\x17ffnen"
    # English-keyed overrides win over the table mapping (applied to every slot
    # with that English text, so both "Open" slots are covered automatically).
    overrides = {                 # English label -> (bytes, source-tag)
        "Open":    (oeffnen, "de-module"),      # no German-table slot; Ö=0x17
        "Rewrite": (b"Neu schreiben", "manual"),  # nowhere in the German module
        "No":      (b"Nein", "manual"),         # German build stored "No" here
    }

    entries = []
    for i, (_, field) in enumerate(us_recs):
        en = field.decode("latin1")
        if en in overrides:
            de_bytes, src = overrides[en]
        elif i in pairs:
            tbl, idx = pairs[i]
            de_bytes, src = tbl[idx][1], "de-table"
        else:
            entries.append({"i": i, "en": en, "de_hex": None, "src": None})
            continue
        assert len(de_bytes) <= 16, f"{en!r} -> {de_bytes!r} too long"
        entries.append({"i": i, "en": en, "de_hex": de_bytes.hex(), "src": src})
    return entries


def glyph(b):
    """Best-effort display of the game-font charmap for the review dump."""
    m = {0x92: "ü", 0x8c: "ö", 0x5d: "ä", 0x02: "Ä", 0x17: "Ö", 0x1d: "ß", 0x81: "ß"}
    return "".join(chr(c) if 32 <= c < 127 else m.get(c, f"<{c:02x}>") for c in b)


if __name__ == "__main__":
    from config import US_ISO
    entries = build(US_ISO)
    os.makedirs("maps", exist_ok=True)
    with open("maps/rel_label_map.json", "w") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)
    n_de = sum(1 for e in entries if e["de_hex"])
    print(f"maps/rel_label_map.json: {len(entries)} slots, {n_de} translated, "
          f"{len(entries) - n_de} kept English")
    print(f"\n{'idx':>3} | {'EN':18} | {'DE':18} | src")
    for e in entries:
        de = glyph(bytes.fromhex(e["de_hex"])) if e["de_hex"] else "— (English)"
        print(f"{e['i']:>3} | {e['en']:18} | {de:18} | {e['src'] or ''}")
