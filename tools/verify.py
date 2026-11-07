import hashlib
import sys
from collections import Counter
from pathlib import Path

import UnityPy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrredux.serialized import SerializedFile
from nrredux.unityfs import Bundle

DATA = 'NIGHT-RUNNERS PRIVATE ALPHA_Data'
AA = DATA + '/StreamingAssets/aa/StandaloneWindows64'


def entries(path):
    data = Path(path).read_bytes()
    if data[:7] == b'UnityFS':
        return {n: (f, d) for n, f, d in Bundle(data).entries}
    return {'': (4, data)}


def objects(data):
    sf = SerializedFile(data)
    return sf, {o[0]: (sf.types[o[3]].raw, sf.object_bytes(o[0])) for o in sf.objects}


def value_map(a, b):
    out = {}
    for pid in a:
        if pid in b and a[pid][1] != b[pid][1] and len(a[pid][1]) == len(b[pid][1]):
            x, y = a[pid][1], b[pid][1]
            i = 0
            while i < len(x):
                if x[i] != y[i]:
                    s = i - (i % 4)
                    e = s + 8
                    out[x[s:e]] = y[s:e]
                    i = e
                else:
                    i += 1
    return out


def manifest(path):
    for o in UnityPy.load(str(path)).objects:
        if o.type.name == 'AssetBundle':
            return o.read_typetree()


def manifest_delta(out, stock):
    pre = lambda t: Counter((p['m_FileID'], p['m_PathID']) for p in t['m_PreloadTable'])
    container = [(k, v['preloadIndex'], v['preloadSize'], v['asset']['m_PathID']) for k, v in out['m_Container']]
    return pre(out) - pre(stock), pre(stock) - pre(out), container, out['m_AssetBundleName'], out['m_Dependencies'], len(out['m_PreloadTable'])


def substitute(data, mapping):
    out = bytearray(data)
    for k in range(0, len(out) - 7, 4):
        v = bytes(out[k:k + 8])
        if v in mapping:
            out[k:k + 8] = mapping[v]
    return bytes(out)


def compare_same(a_path, b_path):
    ea, eb = entries(a_path), entries(b_path)
    if list(ea) != list(eb):
        return 'entry names differ'
    for n in ea:
        fa, da = ea[n]
        fb, db = eb[n]
        if fa & 4:
            sa, oa = objects(da)
            sb, ob = objects(db)
            if sa.externals != sb.externals or sa.scripts != sb.scripts or [t.raw for t in sa.types] != [t.raw for t in sb.types]:
                return '%s metadata differs' % n
            if oa != ob:
                bad = [p for p in set(oa) | set(ob) if oa.get(p) != ob.get(p)]
                return '%s: %d objects differ' % (n, len(bad))
        elif da != db:
            return '%s blob differs' % n
    return None


def main(stock7, stock8, out7, out8, reference):
    ok = True
    for rel in [DATA + '/sharedassets0.assets'] + sorted(AA + '/' + p.name for p in (Path(out8) / AA).glob('*.bundle')):
        why = compare_same(Path(out8) / rel, Path(reference) / rel)
        print('3.2.8 %-70s %s' % (Path(rel).name[:70], why or 'matches the installed reference'))
        ok &= why is None
    for name in ('GameAssembly.dll',):
        same = hashlib.sha256((Path(out8) / name).read_bytes()).digest() == hashlib.sha256((Path(reference) / name).read_bytes()).digest()
        print('3.2.8 GameAssembly.dll', 'identical' if same else 'DIFFERENT')
        ok &= same
    _, a = objects((Path(out8) / DATA / 'sharedassets0.assets').read_bytes())
    _, b = objects((Path(out7) / DATA / 'sharedassets0.assets').read_bytes())
    _, c = objects((Path(stock8) / DATA / 'sharedassets0.assets').read_bytes())
    edited = [p for p in a if c.get(p) != a[p]]
    same = all(a[p] == b.get(p) for p in edited)
    print('3.2.7 sharedassets0.assets edited objects identical to 3.2.8:', same)
    ok &= same
    for p8 in sorted((Path(out8) / AA).glob('*.bundle')):
        prefix = p8.name.rsplit('_', 1)[0]
        p7 = next((Path(out7) / AA).glob(prefix + '_*.bundle'))
        s8 = next((Path(stock8) / AA).glob(prefix + '_*.bundle'), None)
        s7 = next((Path(stock7) / AA).glob(prefix + '_*.bundle'), None)
        if s8 is None:
            s8 = next((Path(stock8) / AA).glob('catalog_carorigins_assets_carorigin_sykina_89_sedansunroofzenki_*.bundle'))
            s7 = next((Path(stock7) / AA).glob('catalog_carorigins_assets_carorigin_sykina_89_sedansunroofzenki_*.bundle'))
        e7, e8 = entries(p7), entries(p8)
        st7, st8 = entries(s7), entries(s8)
        problems = []
        if list(e7) != list(e8):
            problems.append('entry names differ')
        mapping = {}
        for n in st8:
            if st8[n][0] & 4 and n in st7:
                _, a = objects(st8[n][1])
                _, b = objects(st7[n][1])
                mapping.update(value_map(a, b))
        changed = 0
        for n in e8:
            if n not in e7:
                continue
            if e8[n][0] & 4:
                _, o8 = objects(e8[n][1])
                _, o7 = objects(e7[n][1])
                if set(o8) != set(o7):
                    problems.append('object sets differ')
                for pid in o8:
                    if o7.get(pid) == o8[pid]:
                        continue
                    if pid == 1 and o8[pid][0] == o7[pid][0]:
                        if manifest_delta(manifest(p7), manifest(s7)) != manifest_delta(manifest(p8), manifest(s8)):
                            problems.append('AssetBundle manifest')
                        continue
                    if o7[pid][0] != o8[pid][0] or substitute(o8[pid][1], mapping) != o7[pid][1]:
                        problems.append('object %d' % pid)
                    else:
                        changed += 1
            elif e8[n][1] != e7[n][1]:
                problems.append('blob %s' % n)
        print('3.2.7 %-60s %s' % (p7.name[:60], ('OK (%d objects differ only by the 3.2.7 path IDs)' % changed) if not problems else problems[:5]))
        ok &= not problems
    print('ALL OK' if ok else 'PROBLEMS FOUND')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:6]))
