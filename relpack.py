#!/usr/bin/env python3
"""Yaz0 (de)compression for the GameCube main module `foresta.rel.szs`.

The build pipeline (p8..p13) never touched `foresta.rel`, so labels baked into
that module stayed English. p14 patches those strings; this module handles the
Yaz0 wrapper the module ships in.

`yaz0_compress` is a bounded greedy encoder (hash-chained match search). It does
not match Nintendo's ratio but produces a valid stream; since p14's edits are
in-place and same-length, only validity matters. `store` gives an all-literal
fallback if the greedy pass is ever too slow.
"""
import struct

MAX_DIST = 0x1000   # 12-bit back-reference distance
MAX_MATCH = 0x111   # 273 = 0xFF + 0x12
MIN_MATCH = 3


def yaz0_decompress(data):
    assert data[:4] == b"Yaz0", data[:4]
    size = struct.unpack_from(">I", data, 4)[0]
    src = 16
    out = bytearray()
    while len(out) < size:
        code = data[src]; src += 1
        for _ in range(8):
            if len(out) >= size:
                break
            if code & 0x80:
                out.append(data[src]); src += 1
            else:
                b1 = data[src]; b2 = data[src + 1]; src += 2
                dist = ((b1 & 0x0F) << 8) | b2
                start = len(out) - dist - 1
                n = b1 >> 4
                if n == 0:
                    n = data[src] + 0x12; src += 1
                else:
                    n += 2
                for _ in range(n):
                    out.append(out[start]); start += 1
            code <<= 1
    return bytes(out)


def _emit(groups, size):
    """Assemble Yaz0 header + packed control-groups into a bytes stream."""
    out = bytearray(b"Yaz0")
    out += struct.pack(">I", size)
    out += b"\0" * 8
    out += groups
    return bytes(out)


def yaz0_compress(data, max_chain=64):
    """Bounded greedy Yaz0 encoder using zlib-style hash chains."""
    n = len(data)
    head = {}                    # 3-byte key -> most recent position
    prev = [-1] * n              # position -> previous position with same key
    out = bytearray()
    group = bytearray()
    code = 0
    nbits = 0
    i = 0

    def key(p):
        return data[p] << 16 | data[p + 1] << 8 | data[p + 2]

    while i < n:
        best_len = 0
        best_dist = 0
        if i + MIN_MATCH <= n:
            k = key(i)
            j = head.get(k, -1)
            limit = max(0, i - MAX_DIST)
            chain = max_chain
            while j >= limit and chain > 0:
                # quick reject on the byte past the current best
                if best_len == 0 or (i + best_len < n and data[j + best_len] == data[i + best_len]):
                    ln = 0
                    maxln = min(MAX_MATCH, n - i)
                    while ln < maxln and data[j + ln] == data[i + ln]:
                        ln += 1
                    if ln > best_len:
                        best_len = ln
                        best_dist = i - j
                        if ln == maxln:
                            break
                j = prev[j]
                chain -= 1

        if best_len >= MIN_MATCH:
            dist = best_dist - 1
            if best_len < 0x12:
                group += bytes(((best_len - 2) << 4 | (dist >> 8), dist & 0xFF))
            else:
                group += bytes((dist >> 8, dist & 0xFF, best_len - 0x12))
            advance = best_len
        else:
            code |= 0x80 >> nbits
            group.append(data[i])
            advance = 1

        nbits += 1
        if nbits == 8:
            out.append(code)
            out += group
            code = 0
            nbits = 0
            group = bytearray()

        # register hash positions we are skipping over
        end = min(i + advance, n - MIN_MATCH + 1)
        p = i
        while p < end:
            k = key(p)
            prev[p] = head.get(k, -1)
            head[k] = p
            p += 1
        i += advance

    if nbits:
        out.append(code)
        out += group
    return _emit(out, n)


def store(data):
    """All-literal valid Yaz0 (9/8 size). Fast fallback, no matching."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        chunk = data[i:i + 8]
        out.append(0xFF >> (8 - len(chunk)) << (8 - len(chunk)) if len(chunk) < 8 else 0xFF)
        out += chunk
        i += 8
    return _emit(out, n)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1]
    if mode == "d":
        open(sys.argv[3], "wb").write(yaz0_decompress(open(sys.argv[2], "rb").read()))
    elif mode == "c":
        open(sys.argv[3], "wb").write(yaz0_compress(open(sys.argv[2], "rb").read()))
    elif mode == "check":
        raw = yaz0_decompress(open(sys.argv[2], "rb").read())
        comp = yaz0_compress(raw)
        assert yaz0_decompress(comp) == raw, "round-trip mismatch"
        print(f"ok: {len(raw)} raw -> {len(comp)} recompressed "
              f"({len(comp)/len(raw)*100:.1f}%)")
