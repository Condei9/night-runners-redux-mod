import bisect
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

import capstone
import numpy as np
from capstone import x86

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nrredux.dllpatch import apply, pack_bytes, unpack_bytes
from nrredux.pe import Image
from methodmap import method_map

cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
cs.detail = True
CODE = ('.text', 'il2cpp')


def functions(img):
    t = img.exception_table()
    rows = sorted(struct.iter_unpack('<III', t))
    return [r[0] for r in rows], [r[1] for r in rows]


def disasm(img, start, end):
    return list(cs.disasm(img.read(start, end - start), start))


def ref(insn):
    for op in insn.operands:
        if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
            return insn.address + insn.size + op.mem.disp, insn.disp_offset, False
        if op.type == x86.X86_OP_MEM and op.mem.index != 0 and insn.disp_size == 4 and 0x1000 <= op.mem.disp < 0x3400000:
            return op.mem.disp, insn.disp_offset, True
        if op.type == x86.X86_OP_IMM and (insn.group(capstone.CS_GRP_JUMP) or insn.group(capstone.CS_GRP_CALL)):
            return op.imm, insn.imm_offset, False
    return None


class Mapper:
    def __init__(self, img8, img7, meta8, meta7):
        self.a = img8
        self.b = img7
        ma = method_map(bytes(img8.b), meta8)
        self.mb = method_map(bytes(img7.b), meta7)
        self.by8 = {}
        for k, v in ma.items():
            self.by8.setdefault(v, []).append(k)
        self.fa = functions(img8)
        self.fb = functions(img7)
        self.cache = {}
        self.dcache = {}
        self.code8 = [img8.section(n) for n in CODE]
        self.code7 = [img7.section(n) for n in CODE]

    def is_code8(self, rva):
        return any(s['rva'] <= rva < s['rva'] + s['vsize'] for s in self.code8)

    def func(self, table, rva):
        i = bisect.bisect_right(table[0], rva) - 1
        if i < 0:
            raise ValueError(hex(rva))
        return table[0][i], table[1][i], i

    def same(self, s8, e8, s7, e7):
        if e8 - s8 != e7 - s7:
            return False
        x = self.a.read(s8, e8 - s8)
        y = self.b.read(s7, e7 - s7)
        if x == y:
            return True
        ia = list(cs.disasm(x, s8))
        ib = list(cs.disasm(y, s7))
        if len(ia) != len(ib):
            return False
        for p, q in zip(ia, ib):
            if p.size != q.size or p.mnemonic != q.mnemonic:
                return False
            if p.bytes == q.bytes:
                continue
            r = ref(p)
            if r is None:
                return False
            off = r[1]
            n = 4 if off and off + 4 <= p.size else 0
            if not off or p.bytes[:off] != q.bytes[:off] or p.bytes[off + n:] != q.bytes[off + n:]:
                return False
        return True

    def match(self, idx):
        if idx in self.cache:
            return self.cache[idx]
        s8, e8 = self.fa[0][idx], self.fa[1][idx]
        lo = bisect.bisect_left(self.fb[0], s8 - 0x4000)
        hi = bisect.bisect_right(self.fb[0], s8 + 0x4000)
        best = []
        for j in range(lo, hi):
            s7, e7 = self.fb[0][j], self.fb[1][j]
            if e7 - s7 != e8 - s8 or not self.same(s8, e8, s7, e7):
                continue
            score = 0
            for k in range(-4, 5):
                if k == 0 or not (0 <= idx + k < len(self.fa[0])) or not (0 <= j + k < len(self.fb[0])):
                    continue
                if self.fa[0][idx + k] - s8 == self.fb[0][j + k] - s7 and self.same(self.fa[0][idx + k], self.fa[1][idx + k], self.fb[0][j + k], self.fb[1][j + k]):
                    score += 1
            best.append((score, j))
        best.sort(reverse=True)
        if not best or (len(best) > 1 and best[0][0] == best[1][0]):
            raise ValueError('no unique match for function %x (%s)' % (s8, best[:3]))
        self.cache[idx] = best[0][1]
        return best[0][1]

    def neighbour_delta(self, idx):
        votes = Counter()
        for k in list(range(1, 40)) + list(range(-1, -40, -1)):
            try:
                j = self.match(idx + k)
            except (ValueError, IndexError):
                continue
            votes[self.fb[0][j] - self.fa[0][idx + k]] += 1
            if sum(votes.values()) >= 6:
                break
        return votes.most_common(1)[0][0]

    def by_name(self, idx):
        s8 = self.fa[0][idx]
        keys = [k for k in self.by8.get(s8, []) if k in self.mb]
        if not keys:
            raise ValueError('function %x has no metadata name' % s8)
        d = self.neighbour_delta(idx)
        cands = sorted({self.mb[k] for k in keys}, key=lambda v: abs(v - s8 - d))
        if len(cands) > 1 and abs(cands[0] - s8 - d) == abs(cands[1] - s8 - d):
            raise ValueError('ambiguous metadata match for %x' % s8)
        if abs(cands[0] - s8 - d) > 0x400:
            raise ValueError('metadata match for %x too far' % s8)
        return cands[0]

    def masked(self, insns):
        out = []
        for i in insns:
            raw = bytearray(i.bytes)
            r = ref(i)
            if r:
                off = r[1]
                n = 4 if off + 4 <= i.size else i.size - off
                for k in range(off, off + n):
                    raw[k] = 0x100 - 1
                out.append((bytes(raw), set(range(off, off + n))))
            else:
                out.append((bytes(raw), set()))
        return out

    def anchor(self, rva, s8, e8, s7, e7):
        ia = disasm(self.a, s8, max(e8, rva + 32))
        idx = next((k for k, i in enumerate(ia) if i.address <= rva < i.address + i.size), None)
        if idx is None:
            tables = [(ref(i)[0], i) for i in ia if ref(i) and ref(i)[2] and ref(i)[0] <= rva]
            if not tables:
                raise ValueError('cannot anchor %x' % rva)
            v8, insn = max(tables, key=lambda x: x[0])
            twin = self.anchor(insn.address, s8, e8, s7, e7)
            j = next(cs.disasm(self.b.read(twin, 16), twin))
            return ref(j)[0] + rva - v8
        ib = disasm(self.b, s7, e7 + 0x200)
        for before, after in ((3, 4), (6, 8), (10, 12)):
            lo = max(0, idx - before)
            pat = self.masked(ia[lo:idx + after])
            hits = []
            for k in range(len(ib) - len(pat)):
                ok = True
                for (pa, wild), q in zip(pat, ib[k:k + len(pat)]):
                    if len(pa) != q.size or any(pa[x] != q.bytes[x] for x in range(len(pa)) if x not in wild):
                        ok = False
                        break
                if ok:
                    hits.append(ib[k + idx - lo].address + rva - ia[idx].address)
            if len(hits) == 1:
                return hits[0]
        raise ValueError('cannot anchor %x' % rva)

    def code(self, rva):
        s8, e8, i = self.func(self.fa, rva)
        try:
            j = self.match(i)
            return self.fb[0][j] + rva - s8
        except ValueError:
            pass
        s7 = self.by_name(i)
        if rva == s8:
            return s7
        k = bisect.bisect_right(self.fb[0], s7) - 1
        return self.anchor(rva, s8, e8, s7, self.fb[1][k])

    def data(self, rva):
        if rva in self.dcache:
            return self.dcache[rva]
        votes = Counter()
        for s in self.code8:
            raw = np.frombuffer(self.a.read(s['rva'], s['rsize'] - 8), dtype=np.uint8)
            n = len(raw) - 4
            v = (raw[:n].astype(np.int64) | (raw[1:n + 1].astype(np.int64) << 8) | (raw[2:n + 2].astype(np.int64) << 16) | (raw[3:n + 3].astype(np.int64) << 24))
            v = np.where(v >= 2 ** 31, v - 2 ** 32, v)
            pos = np.arange(n, dtype=np.int64) + s['rva']
            for tail in (4, 5, 8):
                hits = np.nonzero(pos + tail + v == rva)[0]
                for h in hits[:40]:
                    p8 = int(pos[h])
                    try:
                        p7 = self.code(p8)
                    except ValueError:
                        continue
                    d7 = struct.unpack('<i', self.b.read(p7, 4))[0]
                    votes[p7 + tail + d7] += 1
        if not votes:
            raise ValueError('no xrefs for data %x' % rva)
        (top, n), *rest = votes.most_common()
        if rest and rest[0][1] * 2 >= n:
            raise ValueError('ambiguous data map %x %s' % (rva, votes.most_common(3)))
        self.dcache[rva] = top
        return top

    def any(self, rva):
        return self.code(rva) if self.is_code8(rva) else self.data(rva)


def port(clean8, modded8, clean7, spec8, meta8, meta7):
    a = Image(clean8)
    m = Image(modded8)
    b = Image(clean7)
    mp = Mapper(a, b, meta8, meta7)
    base8 = a.size_of_image
    shift = b.size_of_image - base8
    top8 = m.size_of_image
    ours = lambda r: base8 <= r < top8

    def target(t):
        return t + shift if ours(t) else mp.any(t)

    code_ranges = []
    table_rows = []
    for sec in m.sections:
        if not ours(sec['rva']):
            continue
        raw = m.read(sec['rva'], sec['vsize'])
        k = 0
        gt = a.exception_table()
        while True:
            k = raw.find(gt, k)
            if k < 0:
                break
            p = k + len(gt)
            while p + 12 <= len(raw):
                x, y, z = struct.unpack_from('<III', raw, p)
                if not (ours(x) and ours(y) and ours(z) and x < y):
                    break
                table_rows.append(sec['rva'] + p)
                code_ranges.append((x, y))
                p += 12
            k = p
    entries = set()
    for site in spec8['sites']:
        s = int(site['rva'], 16)
        n = len(site['new']) // 2
        for i in cs.disasm(m.read(s, n + 16), s):
            if i.address >= s + n:
                break
            r = ref(i)
            if r and ours(r[0]):
                entries.add(r[0])
    seen = set()
    todo = sorted(entries | {x for x, _ in code_ranges})
    insns = {}
    for x, y in code_ranges:
        for i in disasm(m, x, y):
            insns[i.address] = i
            r = ref(i)
            if r and ours(r[0]) and i.group(capstone.CS_GRP_JUMP) or (r and ours(r[0]) and i.group(capstone.CS_GRP_CALL)):
                todo.append(r[0])
    while todo:
        p = todo.pop()
        while ours(p) and p not in seen:
            seen.add(p)
            try:
                i = next(cs.disasm(m.read(p, 16), p))
            except StopIteration:
                raise ValueError('cannot decode %x' % p)
            insns[p] = i
            r = ref(i)
            if r and ours(r[0]) and (i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL)):
                todo.append(r[0])
            if i.mnemonic in ('jmp', 'ret', 'int3', 'ud2') or i.mnemonic.startswith('ret'):
                break
            p += i.size
    order = sorted(insns)
    bases = set()
    biased = {}
    for k, addr in enumerate(order):
        i = insns[addr]
        if i.mnemonic == 'add' and len(i.operands) == 2 and i.operands[1].type == x86.X86_OP_IMM and i.operands[1].imm < 0 and ours(-i.operands[1].imm):
            base = -i.operands[1].imm
            bases.add(base)
            for back in order[max(0, k - 8):k]:
                j = insns[back]
                r = ref(j)
                if j.mnemonic == 'lea' and r and not r[2] and 0x1000 <= r[0] - base < base8:
                    biased[back] = base
    print('biased leas', {('%x' % k): ('%x' % v) for k, v in biased.items()})
    image = bytearray(m.b)
    patched = Image(image)
    for addr, i in sorted(insns.items()):
        if addr in biased:
            b0 = biased[addr]
            tgt = lambda t, b0=b0: b0 + mp.any(t - b0)
        else:
            tgt = target
        try:
            new = relocate_into(i, addr + shift, tgt)
        except ValueError as e:
            raise ValueError('%s while relocating %x %s %s' % (e, addr, i.mnemonic, i.op_str))
        patched.write(addr, new)
    unwinds = set()
    for row in table_rows:
        x, y, z = struct.unpack('<III', m.read(row, 12))
        patched.write(row, struct.pack('<III', x + shift, y + shift, z + shift))
        unwinds.add(z)
    for z in sorted(unwinds):
        hdr = m.read(z, 4)
        flags = hdr[0] >> 3
        count = hdr[2]
        tail = z + 4 + 2 * (count + (count & 1))
        if flags & 4:
            x, y, w = struct.unpack('<III', m.read(tail, 12))
            if ours(x):
                patched.write(tail, struct.pack('<III', x + shift, y + shift, w + shift))
            else:
                rows7 = {r[0]: r for r in struct.iter_unpack('<III', b.exception_table())}
                rows8 = {r[0]: r for r in struct.iter_unpack('<III', a.exception_table())}
                if rows8.get(x) != (x, y, w):
                    raise ValueError('chained unwind %x does not name a game function' % x)
                x7 = mp.code(x)
                if x7 not in rows7 or rows7[x7][1] - x7 != y - x:
                    raise ValueError('chained unwind %x has no 3.2.7 twin' % x)
                patched.write(tail, struct.pack('<III', *rows7[x7]))
        elif flags & 3:
            h = struct.unpack('<I', m.read(tail, 4))[0]
            patched.write(tail, struct.pack('<I', target(h)))
    sites = []
    for site in spec8['sites']:
        s = int(site['rva'], 16)
        n = len(site['new']) // 2
        fs, fe, _ = mp.func(mp.fa, s)
        jump_table = n >= 4 and all(fs <= v <= fe + 0x1000 for v in struct.unpack_from('<%dI' % ((n + (s % 4)) // 4), a.read(s - s % 4, (n + (s % 4)) // 4 * 4)))
        if jump_table:
            s0 = s - s % 4
            e0 = (s + n + 3) & ~3
            old = a.read(s0, e0 - s0)
            new = m.read(s0, e0 - s0)
            s7 = mp.code(s0) if (s0 - fs) < (fe - fs) else mp.code(fs) + (s0 - fs)
            o7 = b''.join(struct.pack('<I', mp.code(v)) for v in struct.unpack('<%dI' % (len(old) // 4), old))
            n7 = b''.join(struct.pack('<I', target(v)) for v in struct.unpack('<%dI' % (len(new) // 4), new))
            if b.read(s7, len(o7)) != o7:
                raise ValueError('jump table mismatch at %x' % s)
            sites.append(dict(rva='%x' % s7, old=o7.hex(), new=n7.hex()))
            continue
        bounds = [i.address for i in disasm(a, fs, max(fe, s + n + 16))]
        bounds_set = set(bounds)
        s0 = max([x for x in bounds if x <= s] or [s])
        e0 = s + n
        while e0 not in bounds_set and e0 < s + n + 16:
            e0 += 1
        while True:
            new_insns = list(cs.disasm(m.read(s0, e0 - s0), s0))
            if sum(i.size for i in new_insns) == e0 - s0:
                break
            e0 = min(x for x in bounds if x > e0)
        s7 = mp.code(fs) + (s0 - fs)
        old_insns = list(cs.disasm(a.read(s0, e0 - s0), s0))
        o7 = b''.join(relocate_into(i, s7 + i.address - s0, target_game(mp, ours, shift)) for i in old_insns)
        n7 = b''.join(relocate_into(i, s7 + i.address - s0, target) for i in new_insns)
        got = b.read(s7, len(o7))
        if got != o7:
            raise ValueError('site %x -> %x mismatch %s vs %s' % (s, s7, got.hex(), o7.hex()))
        sites.append(dict(rva='%x' % s7, old=o7.hex(), new=n7.hex()))
    sections = []
    for sec in spec8['sections']:
        r8 = int(sec['rva'], 16)
        segs = []
        pos = 0
        size = 0
        content = patched.read(r8, int(sec['rsize'], 16))
        gt = a.exception_table()
        for seg in sec['segments']:
            if seg[0] == 'game_exceptions':
                extra = unpack_bytes(seg[1]) if len(seg) > 1 else b''
                new = list(seg)
                new[1] = pack_bytes(content[pos + len(gt):pos + len(gt) + len(extra)])
                segs.append(new)
                pos += len(gt) + len(extra)
            else:
                ln = len(unpack_bytes(seg[1]))
                segs.append(['bytes', pack_bytes(content[pos:pos + ln])])
                pos += ln
        sections.append(dict(sec, rva='%x' % (r8 + shift), segments=segs))
    spec7 = dict(stock_sha256=hashlib.sha256(clean7).hexdigest(), result_sha256=None, sites=sites, sections=sections)
    out = apply(clean7, spec7)
    spec7['result_sha256'] = hashlib.sha256(out).hexdigest()
    return spec7, out, len(insns), mp


def target_game(mp, ours, shift):
    return lambda t: t + shift if ours(t) else mp.any(t)


def relocate_into(insn, new_address, target):
    r = ref(insn)
    raw = bytearray(insn.bytes)
    if r is None:
        return bytes(raw)
    t, off, absolute = r
    nt = target(t)
    if absolute:
        struct.pack_into('<I', raw, off, nt)
        return bytes(raw)
    disp = nt - (new_address + insn.size)
    is_branch = insn.group(capstone.CS_GRP_JUMP) or insn.group(capstone.CS_GRP_CALL)
    width = insn.size - off if is_branch else 4
    if width >= 4:
        struct.pack_into('<i', raw, off, disp)
    else:
        if not -128 <= disp < 128:
            raise ValueError('short branch out of range at %x' % insn.address)
        struct.pack_into('<b', raw, off, disp)
    return bytes(raw)


def main(clean8, modded8, clean7, spec8_path, out_path, meta8, meta7, dll_out=None):
    spec8 = json.loads(Path(spec8_path).read_text(encoding='utf-8'))
    spec7, out, n, mp = port(Path(clean8).read_bytes(), Path(modded8).read_bytes(), Path(clean7).read_bytes(), spec8, Path(meta8).read_bytes(), Path(meta7).read_bytes())
    Path(out_path).write_text(json.dumps(spec7, indent=1), encoding='utf-8')
    print('relocated instructions', n, 'sites', len(spec7['sites']), 'functions mapped', len(mp.cache), 'data mapped', len(mp.dcache))
    for k, v in sorted(mp.dcache.items()):
        print('data %x -> %x (%+x)' % (k, v, v - k))
    if dll_out:
        Path(dll_out).write_bytes(out)


if __name__ == '__main__':
    main(*sys.argv[1:])
