import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrredux.dllpatch import pack_bytes, apply
from nrredux.pe import Image


def runs(a, b, lo, hi, gap=8):
    out = []
    i = lo
    while i < hi:
        if a[i] != b[i]:
            if out and i - out[-1][1] <= gap:
                out[-1][1] = i + 1
            else:
                out.append([i, i + 1])
        i += 1
    return out


def main(clean_path, modded_path, out_path):
    clean = Path(clean_path).read_bytes()
    modded = Path(modded_path).read_bytes()
    c = Image(clean)
    m = Image(modded)
    game_table = c.exception_table()
    sites = []
    for s in c.sections:
        lo, hi = s['rptr'], s['rptr'] + s['rsize']
        ca = memoryview(clean)[lo:hi]
        ma = memoryview(modded)[lo:hi]
        if bytes(ca) == bytes(ma):
            continue
        for a, b in runs(clean, modded, lo, hi):
            rva = s['rva'] + a - s['rptr']
            sites.append(dict(rva='%x' % rva, old=clean[a:b].hex(), new=modded[a:b].hex()))
    known = {s['name'] for s in c.sections}
    active = m.directory(3)[0]
    sections = []
    for s in m.sections:
        if s['name'] in known:
            continue
        raw = modded[s['rptr']:s['rptr'] + s['rsize']]
        segs = []
        pos = 0
        while True:
            k = raw.find(game_table, pos)
            if k < 0:
                break
            if k > pos:
                segs.append(['bytes', pack_bytes(raw[pos:k])])
            end = k + len(game_table)
            tail = end
            while tail + 12 <= len(raw) and raw[tail:tail + 12] != bytes(12):
                a, b, u = struct.unpack_from('<III', raw, tail)
                if not (s['rva'] <= a < b <= s['rva'] + s['vsize'] + 0x100000):
                    break
                tail += 12
            seg = ['game_exceptions', pack_bytes(raw[end:tail])]
            if s['rva'] + k == active:
                seg.append(m.directory(3)[1] - len(game_table))
            segs.append(seg)
            pos = tail
        while len(raw) > pos and raw.endswith(b'\0'):
            raw = raw[:-1]
        if len(raw) > pos:
            segs.append(['bytes', pack_bytes(raw[pos:])])
        sections.append(dict(name=s['name'], rva='%x' % s['rva'], vsize='%x' % s['vsize'], rsize='%x' % s['rsize'], flags='%x' % s['flags'], segments=segs))
    header_sites = [x for x in sites if int(x['rva'], 16) < 0x1000]
    spec = dict(stock_sha256=hashlib.sha256(clean).hexdigest(), result_sha256=hashlib.sha256(modded).hexdigest(),
                sites=[x for x in sites if x not in header_sites], sections=sections)
    out = apply(clean, dict(spec, result_sha256=None))
    if out != modded:
        diff = [i for i in range(min(len(out), len(modded))) if out[i] != modded[i]][:20]
        raise SystemExit('rebuild mismatch %d %d %s' % (len(out), len(modded), diff))
    Path(out_path).write_text(json.dumps(spec, indent=1), encoding='utf-8')
    print('sites', len(spec['sites']), 'sections', [(s['name'], [x[0] for x in s['segments']]) for s in sections])


if __name__ == '__main__':
    main(*sys.argv[1:4])
