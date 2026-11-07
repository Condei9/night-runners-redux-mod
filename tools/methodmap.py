import re
import struct
from struct import unpack_from as u


def method_map(dll, metadata):
    m = metadata
    b = dll
    tables = [u('<III', m, i) for i in range(8, 500, 12)]

    def name(i):
        p = tables[2][0] + i
        return m[p:m.index(0, p)].decode(errors='replace')

    pe = u('<I', b, 60)[0]
    n = u('<H', b, pe + 6)[0]
    sh = pe + 24 + u('<H', b, pe + 20)[0]
    base = 0x180000000
    ss = [u('<IIII', b, sh + 40 * i + 8) for i in range(n)]

    def va(o):
        return next(base + r + o - p for _, r, s, p in ss if p <= o < p + s)

    def off(a):
        return next(p + a - base - r for _, r, s, p in ss if base + r <= a < base + r + s)

    mods = []
    for k in [x.start() for x in re.finditer(re.escape(b'Assembly-CSharp.dll\0'), b)]:
        for q in [x.start() for x in re.finditer(re.escape(struct.pack('<Q', va(k))), b)]:
            mods.append(u('<QQQ', b, q))
    _, cnt, mp = [x for x in mods if 1000 < x[1] < 200000][0]
    ptrs = u('<%dQ' % cnt, b, off(mp))
    out = {}
    seen = {}
    for i in range(tables[5][1] // 30):
        o = tables[5][0] + 30 * i
        nm = name(u('<I', m, o)[0])
        t = u('<H', m, o + 4)[0]
        rid = u('<I', m, o + 18)[0] & 0xffffff
        ty = name(u('<I', m, tables[19][0] + 66 * t)[0])
        key = (ty, nm)
        k = seen.get(key, 0)
        seen[key] = k + 1
        if 0 < rid <= cnt and ptrs[rid - 1]:
            out[(ty, nm, k)] = ptrs[rid - 1] - base
    return out
