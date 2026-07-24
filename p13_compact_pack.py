#!/usr/bin/env python3
"""Compact German ISO build (v4) — replaces p9/p12's append strategy.

The port mounts forest_1st/2nd.arc as ARAM archives (all files attr 0x21) into
a fixed-size pool; the append strategy left the old US data as dead bytes and
grew the ARAM payload from ~5.0 MB to ~8.0 MB, overflowing it (boot segfault
on the Anbernic). Here the data area is rebuilt compactly: each file's blob
(German replacement where we have one, original bytes otherwise) is written
sequentially 32-byte-aligned, entries and header lengths recomputed.

Output: output/forest_1st_de_v4.arc, output/forest_2nd_de_v4.arc,
        and the final ISO (config.OUT_ISO, overwritten).
"""
import os, struct, shutil
import rarc
from gc_fst import u32, parse_disc, read_fst
from msglib import BANKS
from config import US_ISO, OUT_ISO

def p32(b, o, v): struct.pack_into(">I", b, o, v)

def rebuild(src, replacements):
    arc = bytearray(open(src, "rb").read())
    base = rarc.data_base(arc)
    files = sorted(  # keep original data order
        (off, e, replacements.get(p.split("/")[-1], bytes(arc[off:off+size])))
        for p, off, size, e in rarc.parse(arc))
    data = bytearray()
    for _, e, blob in files:
        data += b"\0" * (-len(data) % 32)
        p32(arc, e+8, len(data))
        p32(arc, e+12, len(blob))
        data += blob
    data += b"\0" * (-len(data) % 32)
    arc = arc[:base] + data
    p32(arc, 0x04, len(arc))       # fileSize
    p32(arc, 0x10, len(data))      # total file-data length
    p32(arc, 0x18, len(data))      # ARAM-load length (all files are attr 0x21)
    return bytes(arc)

def build_iso(arcs):
    shutil.copyfile(US_ISO, OUT_ISO)
    with open(OUT_ISO, "r+b") as f:
        _, _, fst_off, fst_size = parse_disc(f)
        idx = {p: i for p, _, _, i in read_fst(f, 0, fst_off, fst_size)}
        f.seek(fst_off)
        fst = bytearray(f.read(fst_size))
        for name, blob in arcs.items():
            f.seek(0, 2)
            pos = f.tell()
            pad = (-pos) % 0x8000
            f.write(b"\0" * pad)
            new_off = pos + pad
            f.write(blob)
            i = idx[name]
            p32(fst, i*12+4, new_off)
            p32(fst, i*12+8, len(blob))
            print(f"{name} -> {hex(new_off)} ({len(blob)})")
        f.seek(fst_off)
        f.write(fst)
        # Pad the trimmed image tail to a 0x8000 sector. The last appended file
        # (foresta.rel.szs) has a non-32-byte-aligned size, so the loader rounds
        # its tail DVD-read up and reads a few bytes past the file; without this
        # pad that runs past EOF -> "disc could not be read" at boot.
        f.seek(0, 2)
        pad = (-f.tell()) % 0x8000
        if pad:
            f.write(b"\0" * pad)
        print("iso size:", f.tell())

def blob(path): return open(path, "rb").read()

if __name__ == "__main__":
    rep2 = {
        "message_data.bin": blob("build/new_message_data.bin"),
        "message_data_table.bin": blob("build/new_message_data_table.bin"),
        "npc_name_str_table.bin": blob("build/banks/de_npc_names.bin"),
    }
    rep1 = {}
    for b in BANKS:
        rep1[f"{b}_data.bin"] = blob(f"build/banks/new_{b}_data.bin")
        rep1[f"{b}_data_table.bin"] = blob(f"build/banks/new_{b}_data_table.bin")

    a2 = rebuild("extracted/us_forest_2nd.arc", rep2)
    a1 = rebuild("extracted/us_forest_1st.arc", rep1)
    open("output/forest_2nd_de_v4.arc", "wb").write(a2)
    open("output/forest_1st_de_v4.arc", "wb").write(a1)
    for out, new in (("forest_2nd", a2), ("forest_1st", a1)):
        was = os.path.getsize(f"extracted/us_{out}.arc")
        print(f"output/{out}_de_v4.arc: {len(new)} (US was {was})")

    arcs = {"forest_2nd.arc": a2, "forest_1st.arc": a1}
    rel = "output/foresta_de.rel.szs"   # produced by p14; optional
    if os.path.exists(rel):
        arcs["foresta.rel.szs"] = blob(rel)
    build_iso(arcs)
