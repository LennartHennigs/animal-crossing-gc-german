#!/usr/bin/env python3
"""Patch German item names (and suppress articles) in foresta.rel (Group B).

In-game item names (fruit, tools, clothing, furniture, ...) are fixed 16-byte
space-padded records in the main module's .data (`itemName_*` / `ftrName*`
tables). The US module ships them in English and the port loads them verbatim,
so pockets/shop/catalog stay English even on the German build — this is the
item-name counterpart to p14's menu-command labels.

This step runs after p14 and patches the *same* module p14 produced
(`output/foresta_de.rel.szs`), so both menu labels and item names land in one
output that p13 injects:

  1. decompress output/foresta_de.rel.szs (relpack / Yaz0),
  2. calibrate the module's vaddr->file base from a content anchor,
  3. for every translated slot in maps/rel_item_map.json (built by
     make_rel_item_map.py), assert the record still holds the expected English
     text, then overwrite its 16-byte field in place with the German bytes,
  4. zero the `itemArt_*`/`ftrArt` article tables so no article is prepended.

Every write is in-place and same-length, so no pointers/relocations shift. Each
name slot is content-checked before writing; a mismatch (different ROM revision,
or p14 output not present) aborts rather than corrupting the module.

Articles: the engine prepends "a"/"an"/"the" (localized to ein/eine/der/die in
the string bank) picked per item from the `itemArt_*` tables, but those encode
English a/an-by-vowel — not German gender — so agreement is wrong ("eine Apfel").
German gender/case can't be expressed in the US 4-slot article model and the PAL
`forestd` module carries no article table to harvest, so we suppress articles:
zero the tables -> `mIN_get_item_article` returns NONE -> bare item names.
"""
import json, os, re
import relpack
from make_rel_item_map import calibrate, field, REC, US_ANCHOR, us_inner, parse_map

REL = "output/foresta_de.rel.szs"   # produced by p14, patched again here
MAP = "maps/rel_item_map.json"
mIN_ARTICLE_NUM = 5                  # enum: NONE, A, AN, THE, SOME


def article_tables():
    """From foresta.map: {symbol: (vaddr, size)} for the 16 itemArt_* tables +
    ftrArt. Excludes `itemArt_table$420` (a pointer array, not article data)."""
    keep = re.compile(r"^(itemArt_[A-Za-z]+|ftrArt)$").match
    return parse_map(us_inner("foresta.map"), lambda s: bool(keep(s)))


def suppress_articles(buf, base):
    """Zero every itemArt_*/ftrArt entry so mIN_get_item_article returns NONE and
    the engine prepends no article. Sanity-guards that each table currently holds
    only article enums (0..4) before zeroing, so a wrong base can't clobber code."""
    n = 0
    for name, (v, sz) in article_tables().items():
        off = base + v
        cur = buf[off:off + sz]
        if any(c >= mIN_ARTICLE_NUM for c in cur):
            raise SystemExit(
                f"{name} at {off:#x} isn't article data ({list(cur[:8])}) — "
                f"base/revision mismatch, aborting")
        buf[off:off + sz] = b"\x00" * sz
        n += sz
    return n


def patch(mod, tables, base):
    buf = bytearray(mod)
    n = 0
    for t in tables:
        vaddr = t["vaddr"]
        for s in t["slots"]:
            i, en = s["i"], s["en"]
            cur = field(mod, base, vaddr, i).decode("latin1")
            if cur != en:
                raise SystemExit(
                    f"{t['name']}[{i}]: expected {en!r}, found {cur!r} — "
                    f"table/revision mismatch, aborting")
            de = bytes.fromhex(s["de_hex"])
            assert len(de) <= REC, f"{en!r} -> {de!r} too long"
            off = base + vaddr + i * REC
            buf[off:off + REC] = de + b" " * (REC - len(de))  # space-pad to 16
            n += 1
    return buf, n


def main():
    if not os.path.exists(REL):
        raise SystemExit(f"{REL} missing — run p14_patch_rel.py first")
    tables = json.load(open(MAP))
    mod = relpack.yaz0_decompress(open(REL, "rb").read())
    mp = {t["name"]: (t["vaddr"], t["size"]) for t in tables}
    # The base is derived from an English record (US_ANCHOR) that p15 itself
    # translates, so a *second* run couldn't recalibrate. Detect the already-
    # patched module up front and no-op, keeping the step idempotent (p14 normally
    # regenerates a fresh module first, so this only matters on a manual re-run).
    de0 = bytes.fromhex(tables[0]["slots"][0]["de_hex"])
    if mod.find(de0.ljust(REC, b" ")) >= 0:
        print(f"{REL} already has German item names — nothing to do")
        return
    base = calibrate(mod, mp, US_ANCHOR)
    buf, n = patch(mod, tables, base)
    na = suppress_articles(buf, base)
    patched = bytes(buf)
    assert len(patched) == len(mod), "length changed — refusing to write"
    comp = relpack.yaz0_compress(patched)
    assert relpack.yaz0_decompress(comp) == patched, "recompress round-trip failed"
    open(REL, "wb").write(comp)
    print(f"patched {n} item names, zeroed {na} article bytes; {REL} "
          f"({len(comp)} bytes, rel {len(mod)} -> {len(comp)} compressed)")


if __name__ == "__main__":
    main()
