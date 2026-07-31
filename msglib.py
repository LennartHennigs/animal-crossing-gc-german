#!/usr/bin/env python3
"""Load and normalize Animal Crossing message banks (US string tables, PAL BMG)."""
import struct

# The 10 secondary text banks (forest_1st.arc); shared by p10/p11/p13.
BANKS = ["mail", "maila", "mailb", "mailc", "ps", "psz",
         "select", "string", "super", "superz"]

# From Cuyler36 Animal-Crossing-Text-Editor GCNParser.cs — total size of each
# 0x7F-escaped control code (including the 0x7F and id bytes).
CC_SIZE = [
    0x02,0x02,0x02,0x03,0x02,0x05,0x02,0x02,0x05,0x05,0x05,0x05,0x05,0x02,0x04,0x04,
    0x04,0x04,0x04,0x06,0x08,0x0A,0x06,0x08,0x0A,0x02,0x02,0x02,0x02,0x02,0x02,0x02,
    0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,
    0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,
    0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,
    0x06,0x03,0x03,0x03,0x03,0x02,0x04,0x04,0x03,0x03,0x03,0x02,0x02,0x02,0x02,0x02,
    0x02,0x02,0x02,0x06,0x03,0x03,0x04,0x03,0x02,0x02,0x06,0x02,0x02,0x03,0x03,0x03,
    0x03,0x02,0x02,0x02,0x02,0x02,0x02,0x04,0x04,0x0C,0x0E,0x02,0x03,
]

# PAL dialog text wraps quoted words in typographic quotation marks „…" (bytes
# 0xD6 open / 0xD5 close). The US module's font has no glyph at those codepoints,
# so they render as blank gaps ("seltsam  ?" instead of a quoted „seltsam"?).
# The US font quotes with plain ASCII 0x22, as the English bank does ("mad cool"),
# so remap PAL text quotes to it. Apply ONLY to copied *text* bytes in convert()'s
# passthrough branch — never to control-code payloads (0x80 tags handle those).
PAL_TEXT_REMAP = {0xD6: 0x22, 0xD5: 0x22}

def load_bmg(path):
    """PAL msg.bin: ROOT wrapper at 0x0, MESGbmg1 at 0x100. Returns raw message bytes."""
    bmg = open(path, "rb").read()
    if bmg[:4] == b"ROOT":          # legacy shifted extraction
        bmg = bmg[0x100:]
    assert bmg[:8] == b"MESGbmg1", path
    inf_size = struct.unpack_from(">I", bmg, 0x24)[0]
    n, esz = struct.unpack_from(">HH", bmg, 0x28)
    # INF1 size is section-relative in most files but file-absolute in some
    # (string.bin); accept whichever candidate lands on the DAT1 magic.
    for dat_o in (0x20 + inf_size, inf_size):
        if bmg[dat_o:dat_o+4] == b"DAT1":
            break
    else:
        dat_o = bmg.find(b"DAT1", 0x20)
        assert dat_o > 0, path
    dat_size = struct.unpack_from(">I", bmg, dat_o+4)[0]
    pool = bmg[dat_o+8:dat_o+dat_size]
    offs = [struct.unpack_from(">I", bmg, 0x30 + i*esz)[0] for i in range(n)]
    # bound each message by the next-largest DAT1 offset, then trim padding
    order = sorted(set(offs) | {len(pool)})
    nxt = {o: order[k+1] for k, o in enumerate(order[:-1])}
    msgs = []
    for o in offs:
        msgs.append(pool[o:nxt.get(o, len(pool))].rstrip(b"\0"))
    return msgs

def load_table(data_path, table_path, count=None):
    """US-style string table pair. table[i] is the END offset of message i
    (per mMsg_Get_BodyParam in ac-decomp): msg[i] = data[table[i-1]:table[i]]."""
    t = open(table_path, "rb").read()
    d = open(data_path, "rb").read()
    offs = struct.unpack(f">{len(t)//4}I", t)
    if count: offs = offs[:count]
    msgs = []
    prev = 0
    for o in offs:
        msgs.append(d[prev:o])
        prev = o
    return msgs

# Flow-critical US control codes: choice menu (0x0D), forced/branch next-message
# links (0x0E-0x15, 0x63, 0x77, 0x78), select-window option strings (0x16-0x18,
# 0x79, 0x7A), B-button choice handling (0x5E, 0x62). The PAL tag system encodes
# these differently (per-message payloads the vote-based tag map can't learn),
# so converted German text must inherit them from the US original.
CRIT = frozenset({0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,
                  0x5E,0x62,0x63,0x77,0x78,0x79,0x7A})

def us_codes(m):
    """Full byte sequences of all 0x7F control codes in a US message."""
    i, out = 0, []
    while i < len(m):
        if m[i] == 0x7F and i+1 < len(m) and m[i+1] < len(CC_SIZE):
            sz = CC_SIZE[m[i+1]]; out.append(bytes(m[i:i+sz])); i += sz
        else:
            i += 1
    return out

# Cutscene drivers: SetDemoOrder* (0x08-0x0C) stage the intro/demo scripts and
# MsgTimeEnd (0x58) auto-advances timed messages. Unlike CRIT these may sit
# mid-text with position semantics, so correctly converted ones stay in place;
# only occurrences the conversion lost are appended (a late trigger beats a
# soft-lock: e.g. the player-select name question stalled without its
# SetDemoOrder tail).
DEMO = frozenset({0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x58})

def _insert_before_term(g, blk):
    """Splice blk before g's trailing terminator code (LAST/CONTINUE/...)."""
    if not blk:
        return bytes(g)
    if len(g) >= 2 and g[-2] == 0x7F and g[-1] in (0x00, 0x01, 0x02):
        return bytes(g[:-2]) + blk + bytes(g[-2:])
    return bytes(g) + blk

def fix_flow(g, u):
    """Make converted message g carry exactly the flow-critical codes of US
    original u (strip + splice before the terminator, in US order), and append
    any DEMO codes of u that the conversion lost."""
    cu = [c for c in us_codes(u) if c[1] in CRIT]
    if [c for c in us_codes(g) if c[1] in CRIT] != cu:
        out = bytearray(); i = 0
        while i < len(g):
            if g[i] == 0x7F and i+1 < len(g) and g[i+1] < len(CC_SIZE):
                sz = CC_SIZE[g[i+1]]
                if g[i+1] not in CRIT:
                    out += g[i:i+sz]
                i += sz
            else:
                out.append(g[i]); i += 1
        g = _insert_before_term(out, b"".join(cu))
    have = {}
    for c in us_codes(g):
        if c[1] in DEMO:
            have[c] = have.get(c, 0) + 1
    missing = []
    for c in us_codes(u):
        if c[1] in DEMO:
            if have.get(c, 0):
                have[c] -= 1
            else:
                missing.append(c)
    return _insert_before_term(g, b"".join(missing))

def strip_us(m):
    """Remove 0x7F control codes (sized via CC_SIZE) and non-text bytes."""
    out = bytearray(); i = 0
    while i < len(m):
        c = m[i]
        if c == 0x7F and i+1 < len(m) and m[i+1] < len(CC_SIZE):
            i += CC_SIZE[m[i+1]]
        else:
            if 0x20 <= c < 0x7F: out.append(c)
            i += 1
    return bytes(out)

def strip_pal(m):
    """Remove 0x80 message tags (self-sized) and non-text bytes."""
    out = bytearray(); i = 0
    while i < len(m):
        c = m[i]
        if c == 0x80 and i+1 < len(m) and m[i+1] >= 5:
            i += m[i+1]
        else:
            if 0x20 <= c < 0x7F: out.append(c)
            i += 1
    return bytes(out)
