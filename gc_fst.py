#!/usr/bin/env python3
"""Parse a GameCube disc image (or TGC) filesystem; list or extract files."""
import struct, sys, os

def u32(b, o): return struct.unpack_from(">I", b, o)[0]

def parse_disc(f, base=0, fst_off_field=0x424):
    f.seek(base)
    hdr = f.read(0x440)
    game_id = hdr[0:6].decode("ascii", "replace")
    title = hdr[0x20:0x60].split(b"\0")[0].decode("ascii", "replace")
    fst_off = u32(hdr, fst_off_field)
    fst_size = u32(hdr, 0x428)
    return game_id, title, fst_off, fst_size

def read_fst(f, base, fst_off, fst_size, file_area_shift=0):
    f.seek(base + fst_off)
    fst = f.read(fst_size)
    num_entries = u32(fst, 8)
    str_base = num_entries * 12
    entries = []
    def name_at(off):
        end = fst.index(b"\0", str_base + off)
        return fst[str_base + off:end].decode("shift-jis", "replace")
    def walk(i, end, path):
        while i < end:
            flags = fst[i*12]
            name_off = u32(fst, i*12) & 0xFFFFFF
            a, b = u32(fst, i*12+4), u32(fst, i*12+8)
            name = name_at(name_off)
            if flags == 1:
                walk(i+1, b, path + name + "/")
                i = b
            else:
                entries.append((path + name, a + file_area_shift, b, i))
                i += 1
    walk(1, num_entries, "")
    return entries

def parse_tgc_header(f, base):
    f.seek(base)
    h = f.read(0x40)
    assert u32(h, 0) == 0xAE0F38A2 or h[:4] == bytes.fromhex("AE0F38A2"), hex(u32(h,0))
    tgc_hdr_size = u32(h, 8)
    fst_off = u32(h, 0x10)
    fst_size = u32(h, 0x14)
    file_area_off = u32(h, 0x24)  # offset of file area in tgc
    virt_file_area = u32(h, 0x34) # original/virtual file area offset
    return tgc_hdr_size, fst_off, fst_size, file_area_off, virt_file_area

if __name__ == "__main__":
    mode, iso = sys.argv[1], sys.argv[2]
    with open(iso, "rb") as f:
        gid, title, fst_off, fst_size = parse_disc(f)
        print(f"# {gid} '{title}' FST@{fst_off:#x} size={fst_size:#x}", file=sys.stderr)
        entries = read_fst(f, 0, fst_off, fst_size)
        if mode == "ls":
            pat = sys.argv[3].lower() if len(sys.argv) > 3 else ""
            for p, off, size, _ in entries:
                if pat in p.lower():
                    print(f"{off:#12x} {size:10d} {p}")
        elif mode == "x":
            want, out = sys.argv[3], sys.argv[4]
            for p, off, size, _ in entries:
                if p == want:
                    f.seek(off)
                    with open(out, "wb") as o:
                        o.write(f.read(size))
                    print(f"extracted {p} ({size} bytes) -> {out}")
                    break
            else:
                sys.exit(f"not found: {want}")
