import hashlib
import json
import lzma
import struct

from .serialized import SerializedFile, SerializedType
from .unityfs import Bundle

MAGIC = b'NRD1'


def read_patch(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != MAGIC:
        raise ValueError('%s is not a patch file' % path)
    n = struct.unpack_from('<I', data, 4)[0]
    head = json.loads(lzma.decompress(data[8:8 + n]).decode('utf-8'))
    blob = lzma.decompress(data[8 + n:]) if len(data) > 8 + n else b''
    return head, blob


def write_patch(path, head, blob):
    h = lzma.compress(json.dumps(head, separators=(',', ':')).encode('utf-8'), preset=9)
    with open(path, 'wb') as f:
        f.write(MAGIC + struct.pack('<I', len(h)) + h + (lzma.compress(blob, preset=9 | lzma.PRESET_EXTREME) if blob else b''))


def run_ops(ops, blob, fetch):
    out = bytearray()
    for op in ops:
        if op[0] == 'c':
            src = fetch(op[1])
            piece = src[op[2]:op[2] + op[3]]
            if len(piece) != op[3]:
                raise ValueError('copy out of range')
            out += piece
        else:
            out += blob[op[1]:op[1] + op[2]]
    return bytes(out)


def apply_serialized(data, rec, blob):
    sf = SerializedFile(data)
    if rec.get('source_types') and hashlib.sha256(b''.join(t.raw for t in sf.types)).hexdigest() != rec['source_types']:
        raise ValueError('serialized file type table differs from the one this patch was made for')
    if rec['types'] is None:
        types = sf.types
    else:
        types = []
        for t in rec['types']:
            if 'src' in t:
                types.append(sf.types[t['src']])
            else:
                raw = blob[t['raw'][0]:t['raw'][0] + t['raw'][1]]
                types.append(SerializedType(raw, *struct.unpack_from('<i', raw, 0), -1, b'', b''))
    cache = {}

    def fetch(pid):
        if pid not in cache:
            cache[pid] = sf.object_bytes(pid)
        return cache[pid]

    objects = []
    payload = {}
    for pid, tindex, op in rec['objects']:
        objects.append((pid, tindex))
        if op == 'k':
            payload[pid] = fetch(pid)
        else:
            payload[pid] = run_ops(op, blob, fetch)
    scripts = sf.scripts if rec['scripts'] is None else [tuple(x) for x in rec['scripts']]
    externals = sf.externals if rec['externals'] is None else [(bytes.fromhex(a), bytes.fromhex(b), c, d.encode()) for a, b, c, d in rec['externals']]
    return sf.build(types, objects, scripts, externals, payload)


def apply_blob(src, rec, blob):
    if rec == 'same':
        return src
    return run_ops(rec, blob, lambda _: src)


def apply_bundle(data, head, blob):
    b = Bundle(data)
    src = {n: (f, d) for n, f, d in b.entries}
    out = []
    for e in head['entries']:
        base = src[e['from']][1] if e.get('from') else b''
        if 'sf' in e:
            payload = apply_serialized(base, e['sf'], blob)
        else:
            payload = apply_blob(base, e['blob'], blob)
        out.append((e['name'], e['flags'], payload))
    return b.build(out), out
