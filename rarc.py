#!/usr/bin/env python3
"""List or extract files from a RARC archive."""
import struct, sys, os

def data_base(data):
    """Absolute offset of the file data area (0x0C = data start rel. header)."""
    return struct.unpack_from(">I", data, 0x0C)[0] + 0x20

def parse(data):
    """Yield (path, abs_data_off, size, entry_off) for every file."""
    assert data[:4] == b"RARC"
    u=lambda o: struct.unpack_from(">I", data, o)[0]
    h=lambda o: struct.unpack_from(">H", data, o)[0]
    doff = data_base(data)
    nnodes = u(0x20); node_off = u(0x24) + 0x20
    nents = u(0x28); ent_off = u(0x2C) + 0x20
    str_off = u(0x34) + 0x20
    def name(o):
        e = data.index(b"\0", str_off+o)
        return data[str_off+o:e].decode("shift-jis","replace")
    files=[]
    def walk(node, path):
        count = h(node_off+node*16+10)
        first = u(node_off+node*16+12)
        for i in range(first, first+count):
            e = ent_off + i*20
            idx = h(e); noff = h(e+6); a = u(e+8); b = u(e+12)
            nm = name(noff)
            if nm in (".",".."): continue
            if idx == 0xFFFF:
                walk(a, path+nm+"/")
            else:
                files.append((path+nm, doff+a, b, e))
    walk(0, "")
    return files

if __name__=="__main__":
    mode, arc = sys.argv[1], sys.argv[2]
    data=open(arc,"rb").read()
    files=parse(data)
    if mode=="ls":
        pat = sys.argv[3].lower() if len(sys.argv)>3 else ""
        for p,o,s,_ in files:
            if pat in p.lower(): print(f"{s:10d} {p}")
    elif mode=="x":
        want,out=sys.argv[3],sys.argv[4]
        for p,o,s,_ in files:
            if p==want:
                open(out,"wb").write(data[o:o+s]); print(f"{want} ({s}) -> {out}"); break
        else: sys.exit("not found")
