#!/usr/bin/env python3
"""Extract sources for the secondary text banks.

- extracted/en_forest_1st_script.arc from english.tgc (German copy already extracted)
- per-bank BMGs from both script arcs -> build/banks/{de,en}_<bank>.bin
- US table pairs from us_forest_1st.arc -> build/banks/us_<bank>_data(.table).bin
- npc_name_str_table.bin from US forest_2nd.arc and German forest_2nd.arc
"""
import os, struct
import rarc
from msglib import BANKS

def tgc_extract(tgc_path, want, out):
    f = open(tgc_path, "rb").read()
    u = lambda o: struct.unpack_from(">I", f, o)[0]
    shift = u(0x24) - u(0x34)
    fst = f[u(0x10):u(0x10)+u(0x14)]
    n = struct.unpack_from(">I", fst, 8)[0]; sb = n*12
    for i in range(1, n):
        nm = struct.unpack_from(">I", fst, i*12)[0] & 0xFFFFFF
        a, b = struct.unpack_from(">II", fst, i*12+4)
        name = fst[sb+nm:fst.index(b"\0", sb+nm)].decode()
        if name == want:
            open(out, "wb").write(f[a+shift:a+shift+b])
            print(f"{tgc_path}:{want} -> {out} ({b})")
            return
    raise SystemExit(f"{want} not in {tgc_path}")

_arcs = {}  # path -> (data, parsed files); each arc is read once

def arc_extract(arc_path, inner, out):
    if arc_path not in _arcs:
        d = open(arc_path, "rb").read()
        _arcs[arc_path] = (d, rarc.parse(d))
    d, files = _arcs[arc_path]
    for p, o, s, _ in files:
        if p == inner:
            blob = d[o:o+s]
            open(out, "wb").write(blob)
            return blob
    raise SystemExit(f"{inner} not in {arc_path}")

def main():
    os.makedirs("build/banks", exist_ok=True)
    if not os.path.exists("extracted/en_forest_1st_script.arc"):
        tgc_extract("extracted/english.tgc", "forest_1st_script.arc",
                    "extracted/en_forest_1st_script.arc")
    for b in BANKS:
        arc_extract("extracted/de_forest_1st_script.arc", f"data/{b}.bin",
                    f"build/banks/de_{b}.bin")
        arc_extract("extracted/en_forest_1st_script.arc", f"data/{b}.bin",
                    f"build/banks/en_{b}.bin")
        arc_extract("extracted/us_forest_1st.arc", f"data/{b}_data.bin",
                    f"build/banks/us_{b}_data.bin")
        arc_extract("extracted/us_forest_1st.arc", f"data/{b}_data_table.bin",
                    f"build/banks/us_{b}_data_table.bin")
        print("bank", b, "ok")
    us = arc_extract("extracted/us_forest_2nd.arc", "data/npc_name_str_table.bin",
                     "build/banks/us_npc_names.bin")
    de = arc_extract("extracted/de_forest_2nd.arc", "data/npc_name_str_table.bin",
                     "build/banks/de_npc_names.bin")
    print("npc name tables identical:", us == de)

if __name__ == "__main__":
    main()
