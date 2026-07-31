#!/usr/bin/env python3
"""Final rebuild (v2, clean extraction): entry-level German substitution.

- maps/entry_map_v2.json: US entry -> PAL id (near-identity, 16,263 mapped)
- tag table: context votes (n>=2 plurality) + structural formulas
- gender-variant tags (group 19 with payload): inline first variant
- unmapped or oversize entries keep original US bytes

Outputs: build/new_message_data(.table).bin, build/rebuild_v2_report.json,
         maps/tag_map_v2_final.json
"""
import json, os, struct
from collections import defaultdict, Counter
from msglib import *

MSG_BUF_MAX = 1536

def pal_tags(m):
    i, out = 0, []
    while i < len(m):
        if m[i] == 0x80 and i+1 < len(m) and m[i+1] >= 5:
            sz = m[i+1]; out.append(bytes(m[i:i+sz])); i += sz
        else:
            i += 1
    return out

def build_table(us, en, emap):
    uss = [strip_us(m) for m in us]; ens = [strip_pal(m) for m in en]
    votes = defaultdict(Counter); tmpls = defaultdict(Counter)
    exact_votes = defaultdict(Counter)
    for u, e in emap.items():
        if not uss[u] or uss[u] != ens[e]:
            continue
        cs, ts = us_codes(us[u]), pal_tags(en[e])
        if len(cs) != len(ts) or not cs:
            continue
        for c, t in zip(cs, ts):
            tk = f"{t[1]},{t[2]},{(t[3]<<8)|t[4]}"
            votes[tk][c[1]] += 1
            tmpls[(tk, c[1])][c] += 1
            # payload-exact mapping: PAL tags carry params (color, scale, bgm
            # id) in trailing payload bytes; a single per-tk template replays
            # one frozen param everywhere (tiny first letters, wrong music)
            exact_votes[f"{tk}|{t[5:].hex()}"][c] += 1
    exact = {k: ctr.most_common(1)[0][0].hex() for k, ctr in exact_votes.items()}
    # pass-through tags: payload bytes == US code params in every training pair
    # (e.g. BgmMake/BgmDelete ids) -> unseen payloads can be forwarded verbatim
    pairs_by_tk = defaultdict(set)
    for k, ctr in exact_votes.items():
        tk, pay = k.rsplit("|", 1)
        for cbytes in ctr:
            pairs_by_tk[tk].add((bytes.fromhex(pay), cbytes))
    passthru = {}
    for tk, prs in pairs_by_tk.items():
        ids = {c[1] for _, c in prs}
        if len(ids) != 1 or len(prs) < 2:
            continue
        cid = ids.pop(); n = CC_SIZE[cid] - 2
        if n > 0 and all(len(p) >= n and p[-n:] == c[2:] and not any(p[:-n])
                         for p, c in prs):
            passthru[tk] = cid
    # PAL stateful color family {80 06 ff 00 00 xx}: color id -> RGB, harvested
    # from learned US codes (7f05 RGB / 7f50 RGB n). Converted to count-based
    # 7f50 with the count measured on the German span (see color_span).
    palrgb = {}
    for k, v in exact.items():
        if k.startswith("6,255,0|") and v[:4] in ("7f05", "7f50"):
            palrgb[k.rsplit("|", 1)[1]] = v[4:10]
    table = {}
    for tk, ctr in votes.items():
        (code, n), = ctr.most_common(1)
        if n >= 2 or len(ctr) == 1:   # majority, or unique single witness
            table[tk] = tmpls[(tk, code)].most_common(1)[0][0].hex()
    # structural fallbacks
    table.setdefault("5,1,1", "7f00"); table.setdefault("5,1,2", "7f01")
    table.setdefault("5,1,3", "7f02")
    # confirmed against EN PAL alignment; 7..13 = year,month,week,day,h,m,s
    g4 = {0: 0x1A, 1: 0x1B, 2: 0x1C, 3: 0x2E, 4: 0x40, 5: 0x2F, 6: 0x71,
          7: 0x1D, 8: 0x1E, 9: 0x1F, 10: 0x20, 11: 0x21, 12: 0x22, 13: 0x23,
          14: 0x30, 16: 0x75, 17: 0x74, 22: 0x28}
    for k in range(20):
        g4[18+k] = 0x24+k if k <= 9 else 0x36+(k-10)
    for j in range(5):
        g4[38+j] = 0x31+j
    for idx, code in g4.items():
        table.setdefault(f"5,4,{idx}", bytes([0x7F, code]).hex())
    for idx in range(64):
        p = 0xFF if idx == 0 else idx
        table.setdefault(f"5,6,{idx}", bytes([0x7F, 0x09, 0, 0, p]).hex())
    return table, exact, passthru, palrgb

def color_span(m, j):
    """Count glyphs from PAL offset j to the next stateful color tag
    (the reset) or message end; newlines (0xCD) don't count."""
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

NEAR_TKS = {"7,255,1"}   # SetCharScale/SetLineScale: PAL units differ, use
                         # the nearest seen payload's learned US code

def build_near(exact):
    near = defaultdict(list)
    for k, v in exact.items():
        tk, pay = k.rsplit("|", 1)
        if tk in NEAR_TKS and pay:
            near[tk].append((int(pay, 16), v))
    for tk in near:
        near[tk].sort()
    return dict(near)

def convert(m, maps, dropped):
    table, exact, passthru, near, palrgb = maps
    out = bytearray(); i = 0
    while i < len(m):
        c = m[i]
        if c == 0x80 and i+1 < len(m) and m[i+1] >= 5:
            sz = m[i+1]; grp = m[i+2]; idx = (m[i+3] << 8) | m[i+4]
            data = m[i+5:i+sz]
            tk = f"{sz},{grp},{idx}"
            ek = f"{tk}|{data.hex()}"
            if sz == 6 and grp == 0xFF and idx == 0:
                # stateful color on/off -> count-based SetColorChar sized to
                # the German span; the off tag emits nothing
                if data != b"\x00" and data.hex() in palrgb:
                    n = min(color_span(m, i+sz), 255)
                    out += bytes.fromhex("7f50" + palrgb[data.hex()]) + bytes([n])
            elif grp == 19 and sz > 5:
                out += data.split(b"\xfe")[0]      # gender variants: take first
            elif ek in exact:
                out += bytes.fromhex(exact[ek])   # payload-aware (params kept)
            elif tk in passthru:
                cid = passthru[tk]; n = CC_SIZE[cid] - 2
                out += bytes([0x7F, cid]) + data[-n:]
            elif tk in near and data:
                v = int(data.hex(), 16)
                out += bytes.fromhex(min(near[tk], key=lambda pv: abs(pv[0]-v))[1])
            elif tk in table:
                out += bytes.fromhex(table[tk])
            else:
                dropped[tk] = dropped.get(tk, 0) + 1
            i += sz
        else:
            out.append(PAL_TEXT_REMAP.get(c, c)); i += 1   # remap „…" -> "
    return bytes(out)

def main():
    us = load_table("extracted/us_message_data.bin", "extracted/us_message_data_table.bin", 16744)
    en = load_bmg("extracted/en_msg.bin")
    de = load_bmg("extracted/de_msg.bin")
    emap = {int(k): v for k, v in json.load(open("maps/entry_map_v2.json")).items()}
    nslots = os.path.getsize("extracted/us_message_data_table.bin") // 4

    table, exact, passthru, palrgb = build_table(us, en, emap)
    json.dump({"tags": table, "exact": exact, "passthru": passthru,
               "palrgb": palrgb},
              open("maps/tag_map_v2_final.json", "w"), indent=0)
    maps = (table, exact, passthru, build_near(exact), palrgb)
    print(f"tag table: {len(table)} | exact: {len(exact)} | "
          f"passthru: {len(passthru)} | colors: {len(palrgb)}")

    # rescue lookup for PAL stub entries: US stripped text -> unique EN PAL index
    uss = [strip_us(m) for m in us]
    en_hits = defaultdict(list)
    for j, m in enumerate(en):
        s = strip_pal(m)
        if s:
            en_hits[s].append(j)

    dropped = {}
    new = bytearray()
    new_offs = []
    replaced = kept_en = oversize = flow_fixed = rescued = 0
    for i in range(16744):
        if i in emap:
            g = convert(de[emap[i]], maps, dropped)
            if not strip_us(g) and uss[i]:
                # PAL entry at this index is a flow stub; the real text lives at
                # another index — find it via the (index-aligned) EN PAL bank
                js = en_hits.get(uss[i])
                if js and len(js) == 1:
                    g = convert(de[js[0]], maps, dropped)
                    rescued += 1
                else:
                    g = b""          # unrescuable stub -> keep English
            if g:
                fixed = fix_flow(g, us[i])
                flow_fixed += fixed != g
                g = fixed
            if 0 < len(g) <= MSG_BUF_MAX:
                new += g; replaced += 1
            else:
                new += us[i]; kept_en += 1
                if len(g) > MSG_BUF_MAX: oversize += 1
        else:
            new += us[i]; kept_en += 1 if us[i] else 0
        new_offs.append(len(new))
    new_offs += [len(new)] * (nslots - 16744)

    open("build/new_message_data.bin", "wb").write(new)
    open("build/new_message_data_table.bin", "wb").write(
        struct.pack(f">{nslots}I", *new_offs))
    rep = {"replaced": replaced, "kept_english_nonempty": kept_en,
           "oversize_reverts": oversize, "flow_fixed": flow_fixed,
           "stub_rescued": rescued, "new_len": len(new),
           "dropped_tags": dict(sorted(dropped.items(), key=lambda kv: -kv[1])[:15])}
    json.dump(rep, open("build/rebuild_v2_report.json", "w"), indent=1)
    print(rep)

if __name__ == "__main__":
    main()
