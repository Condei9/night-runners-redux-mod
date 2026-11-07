import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrredux.assetdelta import apply_bundle, apply_serialized, write_patch, read_patch
from nrredux.serialized import SerializedFile
from nrredux.unityfs import Bundle

DATA = 'NIGHT-RUNNERS PRIVATE ALPHA_Data'
AA = 'StreamingAssets/aa/StandaloneWindows64'
KEY = 16
STRIDE = 8


class Blob:
    def __init__(self):
        self.b = bytearray()
        self.seen = {}

    def add(self, data):
        data = bytes(data)
        h = hashlib.sha1(data).digest()
        if h in self.seen:
            return self.seen[h]
        at = len(self.b)
        self.b += data
        self.seen[h] = (at, len(data))
        return at, len(data)


class Index:
    def __init__(self):
        self.map = {}
        self.src = {}

    def feed(self, pid, data):
        if pid in self.src:
            return
        self.src[pid] = data
        m = self.map
        for i in range(0, len(data) - KEY + 1, STRIDE):
            m.setdefault(data[i:i + KEY], (pid, i))


def match_ops(t, index, blob):
    ops = []
    lit = 0
    i = 0
    n = len(t)
    m = index.map

    def flush(end):
        if end > lit:
            a, ln = blob.add(t[lit:end])
            ops.append(['a', a, ln])

    while i <= n - KEY:
        hit = m.get(t[i:i + KEY])
        if hit is None:
            i += 1
            continue
        pid, off = hit
        src = index.src[pid]
        s, o = i, off
        while s > lit and o > 0 and src[o - 1] == t[s - 1]:
            s -= 1
            o -= 1
        e, f = i + KEY, off + KEY
        while e < n and f < len(src) and src[f] == t[e]:
            e += 1
            f += 1
        if e - s < 24:
            i += 1
            continue
        flush(s)
        if ops and ops[-1][0] == 'c' and ops[-1][1] == pid and ops[-1][2] + ops[-1][3] == o:
            ops[-1][3] += e - s
        else:
            ops.append(['c', pid, o, e - s])
        lit = e
        i = e
    lit_end = n
    if lit_end > lit:
        a, ln = blob.add(t[lit:lit_end])
        ops.append(['a', a, ln])
    return ops


def same_size_ops(pid, old, new, blob):
    x = np.frombuffer(old, np.uint8)
    y = np.frombuffer(new, np.uint8)
    idx = np.nonzero(x != y)[0]
    runs = []
    for k in idx.tolist():
        if runs and k - runs[-1][1] <= 16:
            runs[-1][1] = k + 1
        else:
            runs.append([k, k + 1])
    ops = []
    pos = 0
    for a, b in runs:
        if a > pos:
            ops.append(['c', pid, pos, a - pos])
        r = blob.add(new[a:b])
        ops.append(['a', r[0], r[1]])
        pos = b
    if pos < len(new):
        ops.append(['c', pid, pos, len(new) - pos])
    return ops


def encode_serialized(src_bytes, dst_bytes, blob, report):
    s = SerializedFile(src_bytes)
    d = SerializedFile(dst_bytes)
    src_types = {t.raw: i for i, t in enumerate(s.types)}
    if [t.raw for t in s.types] == [t.raw for t in d.types]:
        types = None
    else:
        types = []
        for t in d.types:
            if t.raw in src_types:
                types.append({'src': src_types[t.raw]})
            else:
                types.append({'raw': list(blob.add(t.raw))})
    by_class = {}
    for o in s.objects:
        by_class.setdefault(s.types[o[3]].class_id, []).append(o[0])
    indexes = {}
    objects = []
    stats = dict(keep=0, edit=0, new=0, literal=0)
    for pid, start, size, tindex in d.objects:
        t = d.object_bytes(pid)
        if pid in s.by_pid:
            old = s.object_bytes(pid)
            if old == t:
                objects.append([pid, tindex, 'k'])
                stats['keep'] += 1
                continue
            stats['edit'] += 1
            if len(old) == len(t):
                objects.append([pid, tindex, same_size_ops(pid, old, t, blob)])
                continue
            idx = Index()
            idx.feed(pid, old)
            ops = match_ops(t, idx, blob)
        else:
            stats['new'] += 1
            cls = d.types[tindex].class_id
            if cls not in indexes:
                ix = Index()
                for p in by_class.get(cls, []):
                    ix.feed(p, s.object_bytes(p))
                indexes[cls] = ix
            ops = match_ops(t, indexes[cls], blob)
        stats['literal'] += sum(o[2] for o in ops if o[0] == 'a')
        objects.append([pid, tindex, ops])
    rec = dict(source_types=hashlib.sha256(b''.join(t.raw for t in s.types)).hexdigest(), types=types, objects=objects,
               scripts=None if s.scripts == d.scripts else [list(x) for x in d.scripts],
               externals=None if s.externals == d.externals else [[a.hex(), b.hex(), c, p.decode()] for a, b, c, p in d.externals])
    report.append(stats)
    return rec


def encode_blob(src, dst, blob):
    if src == dst:
        return 'same'
    idx = Index()
    if src:
        idx.feed(0, src)
    return match_ops(dst, idx, blob)


def same_serialized(a, b):
    x = SerializedFile(a)
    y = SerializedFile(b)
    if [t.raw for t in x.types] != [t.raw for t in y.types]:
        return 'types'
    if x.scripts != y.scripts or x.externals != y.externals:
        return 'scripts/externals'
    if [(o[0], o[3]) for o in x.objects] != [(o[0], o[3]) for o in y.objects]:
        return 'object table'
    for o in x.objects:
        if x.object_bytes(o[0]) != y.object_bytes(o[0]):
            return 'object %d' % o[0]
    return None


def pattern(name):
    return re.sub(r'_[0-9a-f]{32}\.bundle$', '_*.bundle', name)


def make_bundle(src_path, dst_path, out_file, target_name):
    sb = Bundle(src_path.read_bytes())
    db = Bundle(dst_path.read_bytes())
    blob = Blob()
    src_entries = {n: d for n, f, d in sb.entries}
    src_sf = sb.serialized_name()
    report = []
    entries = []
    for name, flags, data in db.entries:
        if name in src_entries:
            frm = name
        elif flags & 4:
            frm = src_sf
        else:
            suffix = name[name.index('.'):] if '.' in name else ''
            frm = next((n for n in src_entries if suffix and n.endswith(suffix)), None)
        e = dict(name=name, flags=flags, **({'from': frm} if frm else {}))
        if flags & 4:
            e['sf'] = encode_serialized(src_entries[frm], data, blob, report)
        else:
            e['blob'] = encode_blob(src_entries.get(frm, b''), data, blob)
        entries.append(e)
    head = dict(kind='bundle', source=pattern(src_path.name), target=target_name, entries=entries)
    write_patch(out_file, head, bytes(blob.b))
    h, bl = read_patch(out_file)
    _, rebuilt = apply_bundle(src_path.read_bytes(), h, bl)
    for (n1, f1, d1), (n2, f2, d2) in zip(rebuilt, db.entries):
        if n1 != n2 or f1 != f2:
            raise SystemExit('entry mismatch %s' % n1)
        if f1 & 4:
            why = same_serialized(d1, d2)
            if why:
                raise SystemExit('%s: %s' % (n1, why))
        elif d1 != d2:
            raise SystemExit('blob mismatch %s' % n1)
    return report, len(bl)


def make_serialized(src_path, dst_path, out_file, rel):
    blob = Blob()
    report = []
    rec = encode_serialized(src_path.read_bytes(), dst_path.read_bytes(), blob, report)
    write_patch(out_file, dict(kind='serialized', source=rel, sf=rec), bytes(blob.b))
    h, bl = read_patch(out_file)
    out = apply_serialized(src_path.read_bytes(), h['sf'], bl)
    why = same_serialized(out, dst_path.read_bytes())
    if why:
        raise SystemExit('%s: %s' % (rel, why))
    return report, len(bl)


def main(stock, modded, out_dir, plan_path):
    stock = Path(stock) / DATA
    modded = Path(modded) / DATA
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    for item in plan:
        out_file = out_dir / item['patch']
        if item['kind'] == 'serialized':
            rep, n = make_serialized(stock / item['path'], modded / item['path'], out_file, item['path'])
        else:
            src = next((stock / AA).glob(item['source']))
            dst = next((modded / AA).glob(item.get('target_glob', item['source'])))
            rep, n = make_bundle(src, dst, out_file, item.get('target'))
        print('%-45s %8d bytes literal %s' % (item['patch'], out_file.stat().st_size, rep))


if __name__ == '__main__':
    main(*sys.argv[1:5])
