#!/usr/bin/env python3
"""Map, convert and rebuild the 10 secondary banks.

Per bank: US table pair + EN/DE BMGs -> build/banks/new_<bank>_data(.table).bin
Mapping: difflib matching blocks on stripped text + equal-size gap fill.
Conversion: tag_map_v2_final.json + group-19 first-variant inlining.
Guard: revert entry to English if converted size > max(orig_max, 64) * 1.5.
"""
import json, struct, difflib
from collections import Counter, defaultdict
from msglib import *   # incl. BANKS

_maps = json.load(open("maps/tag_map_v2_final.json"))
table, exact, passthru, palrgb = (_maps["tags"], _maps["exact"],
                                  _maps["passthru"], _maps["palrgb"])

def color_span(m, j):
    n = 0
    while j < len(m):
        if m[j] == 0x80 and j+1 < len(m) and m[j+1] >= 5:
            if m[j+1] == 6 and m[j+2] == 0xFF:
                break
            j += m[j+1]
        else:
            if m[j] != 0xCD:
                n += 1
            j += 1
    return n
NEAR_TKS = {"7,255,1"}
near = defaultdict(list)
for _k, _v in exact.items():
    _tk, _pay = _k.rsplit("|", 1)
    if _tk in NEAR_TKS and _pay:
        near[_tk].append((int(_pay, 16), _v))
for _tk in near:
    near[_tk].sort()

def strip_grammar_prefix(m):
    """PAL string-bank entries start with a 3-byte grammar prefix
    (gender/number/class, e.g. 00 ff ff or 02 00 04) that the PAL engine uses
    for article agreement. The US engine copies these strings raw into
    fixed-size name fields (mString_Load_StringFromRom), so the prefix renders
    as junk glyphs and pushes the text past its slot — strip it. Constrained
    match so umlaut glyph bytes (0x92 'u-umlaut' etc.) are never eaten."""
    if (len(m) >= 3 and m[0] in (0, 1, 2, 0xFF)
            and m[1] in (0, 1, 2, 5, 0xFF) and m[2] in (2, 3, 4, 5, 0xFF)):
        return m[3:]
    return m

def convert(m, dropped):
    out = bytearray(); i = 0
    while i < len(m):
        c = m[i]
        if c == 0x80 and i+1 < len(m) and m[i+1] >= 5:
            sz = m[i+1]; grp = m[i+2]; idx = (m[i+3] << 8) | m[i+4]
            tk = f"{sz},{grp},{idx}"
            data = m[i+5:i+sz]
            ek = f"{tk}|{data.hex()}"
            if sz == 6 and grp == 0xFF and idx == 0:
                if data != b"\x00" and data.hex() in palrgb:
                    n = min(color_span(m, i+sz), 255)
                    out += bytes.fromhex("7f50" + palrgb[data.hex()]) + bytes([n])
            elif grp == 19 and sz > 5:
                out += data.split(b"\xfe")[0]
            elif ek in exact:
                out += bytes.fromhex(exact[ek])
            elif tk in passthru:
                cid = passthru[tk]; n = CC_SIZE[cid] - 2
                out += bytes([0x7F, cid]) + data[-n:]
            elif tk in near and data:
                v = int(data.hex(), 16)
                out += bytes.fromhex(min(near[tk], key=lambda pv: abs(pv[0]-v))[1])
            elif tk in table:
                out += bytes.fromhex(table[tk])
            else:
                dropped[tk] += 1
            i += sz
        else:
            out.append(PAL_TEXT_REMAP.get(c, c)); i += 1   # remap „…" -> "
    return bytes(out)

def load_us_bank(b):
    t = open(f"build/banks/us_{b}_data_table.bin", "rb").read()
    d = open(f"build/banks/us_{b}_data.bin", "rb").read()
    offs = list(struct.unpack(f">{len(t)//4}I", t))
    # valid region: offsets monotonically non-decreasing and within data
    n = 0
    prev = 0
    for o in offs:
        if o < prev or o > len(d):
            break
        prev = o; n += 1
    msgs = []
    prev = 0
    for o in offs[:n]:
        msgs.append(d[prev:o]); prev = o
    return msgs, offs, len(d)

def main():
    report = {}
    for b in BANKS:
        us, offs, dlen = load_us_bank(b)
        en = load_bmg(f"build/banks/en_{b}.bin")
        de = load_bmg(f"build/banks/de_{b}.bin")
        uss = [strip_us(m) for m in us]
        ens = [strip_pal(m) for m in en]
        en_hits = defaultdict(list)
        for j, s in enumerate(ens):
            if s:
                en_hits[s].append(j)
        vocab = {}; tok = lambda s: vocab.setdefault(s, len(vocab))
        sm = difflib.SequenceMatcher(None, [tok(s) for s in uss],
                                     [tok(s) for s in ens], autojunk=False)
        mapping = {}
        for i, j, n in sm.get_matching_blocks():
            for k in range(n):
                mapping[i+k] = j+k
        ml = sorted(mapping.items())
        for (u0, e0), (u1, e1) in zip(ml, ml[1:]):
            gu, ge = range(u0+1, u1), range(e0+1, e1)
            if len(gu) == len(ge):
                for u, e in zip(gu, ge):
                    mapping[u] = e

        limit = max(64, max((len(m) for m in us if m), default=64)) * 1.5
        dropped = Counter()
        new = bytearray(); new_offs = []
        replaced = kept = 0
        for i in range(len(us)):
            # never fill a slot the US bank leaves empty: the engine treats
            # size 0 as "clear to spaces" (name-entry prefill reads these)
            g = convert(de[mapping[i]], dropped) if i in mapping and us[i] else b""
            if b == "string":
                g = strip_grammar_prefix(g)
            if g and not strip_us(g) and uss[i]:
                # PAL stub entry: real text lives elsewhere — rescue via EN bank
                js = en_hits.get(uss[i])
                g = convert(de[js[0]], dropped) if js and len(js) == 1 else b""
            if g:
                g = fix_flow(g, us[i])
            if 0 < len(g) <= limit:
                new += g; replaced += 1
            else:
                new += us[i]
                kept += 1 if uss[i] else 0
            new_offs.append(len(new))
        # preserve original slot count; unused slots -> data end
        new_offs += [len(new)] * (len(offs) - len(new_offs))
        open(f"build/banks/new_{b}_data.bin", "wb").write(new)
        open(f"build/banks/new_{b}_data_table.bin", "wb").write(
            struct.pack(f">{len(new_offs)}I", *new_offs))
        report[b] = {"entries": len(us), "bmg": len(en), "replaced": replaced,
                     "kept_english_nonempty": kept, "new_len": len(new),
                     "old_len": dlen,
                     "dropped": dict(dropped.most_common(5))}
        print(b, report[b])
    json.dump(report, open("build/banks/rebuild_report.json", "w"), indent=1)

if __name__ == "__main__":
    main()
