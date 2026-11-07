import struct


def _align(n, a):
    return (n + a - 1) // a * a


class Reader:
    def __init__(self, data, pos=0, endian='<'):
        self.d = data
        self.p = pos
        self.e = endian

    def take(self, fmt):
        fmt = self.e + fmt
        v = struct.unpack_from(fmt, self.d, self.p)
        self.p += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]

    def raw(self, n):
        v = bytes(self.d[self.p:self.p + n])
        self.p += n
        return v

    def cstr(self):
        e = self.d.index(0, self.p)
        v = bytes(self.d[self.p:e])
        self.p = e + 1
        return v

    def align(self, a=4):
        self.p = _align(self.p, a)


class SerializedType:
    def __init__(self, raw, class_id, script_index, script_id, old_hash):
        self.raw = raw
        self.class_id = class_id
        self.script_index = script_index
        self.script_id = script_id
        self.old_hash = old_hash

    def key(self):
        return self.raw.hex()


class SerializedFile:
    def __init__(self, data):
        self.data = data
        r = Reader(data, 0, '>')
        self.legacy = r.take('IIII')
        self.version = self.legacy[2]
        if self.version < 21:
            raise ValueError('unsupported serialized file version %d' % self.version)
        self.endian_byte = r.take('B')
        self.reserved = r.raw(3)
        if self.version >= 22:
            self.metadata_size, self.file_size, self.data_offset, self.unknown = r.take('IQQQ')
        else:
            self.metadata_size, self.file_size, _, self.data_offset = self.legacy
        self.entry = 'qQIi' if self.version >= 22 else 'qIIi'
        self.header_size = r.p
        e = '>' if self.endian_byte else '<'
        r.e = e
        self.e = e
        self.unity_version = r.cstr()
        self.platform = r.take('i')
        self.typetree = r.take('B')
        self.types = [self._read_type(r, False) for _ in range(r.take('i'))]
        count = r.take('i')
        self.objects = []
        for _ in range(count):
            r.align(4)
            pid, start, size, tindex = r.take(self.entry)
            self.objects.append([pid, start, size, tindex])
        self.scripts = []
        for _ in range(r.take('i')):
            fi = r.take('i')
            r.align(4)
            self.scripts.append((fi, r.take('q')))
        self.externals = []
        for _ in range(r.take('i')):
            empty = r.cstr()
            guid = r.raw(16)
            kind = r.take('i')
            path = r.cstr()
            self.externals.append((empty, guid, kind, path))
        self.ref_types = [self._read_type(r, True) for _ in range(r.take('i'))]
        self.user_info = r.cstr()
        self.metadata_end = r.p
        if self.metadata_end != self.header_size + self.metadata_size:
            raise ValueError('metadata size mismatch')
        self.by_pid = {o[0]: o for o in self.objects}

    def _read_type(self, r, is_ref):
        start = r.p
        class_id = r.take('i')
        r.take('B')
        script_index = r.take('h')
        script_id = b''
        if (is_ref and script_index >= 0) or class_id == 114:
            script_id = r.raw(16)
        old_hash = r.raw(16)
        if self.version >= 23 and self.typetree:
            r.raw(16)
        if self.typetree:
            if self.version >= 23:
                size = r.take('I')
                r.p += size
            else:
                nodes, strings = r.take('ii')
                r.p += nodes * 32 + strings
            if is_ref:
                r.cstr()
                r.cstr()
                r.cstr()
            else:
                deps = r.take('i')
                r.p += 4 * deps
        return SerializedType(bytes(r.d[start:r.p]), class_id, script_index, script_id, old_hash)

    def object_bytes(self, pid):
        o = self.by_pid[pid]
        s = self.data_offset + o[1]
        return bytes(self.data[s:s + o[2]])

    def type_of(self, pid):
        return self.types[self.by_pid[pid][3]]

    def build(self, types, objects, scripts, externals, payload, align_objects=8):
        e = self.e
        meta = bytearray()
        meta += self.unity_version + b'\0'
        meta += struct.pack(e + 'iB', self.platform, self.typetree)
        meta += struct.pack(e + 'i', len(types))
        for t in types:
            meta += t.raw
        meta += struct.pack(e + 'i', len(objects))
        old = {o[0]: o for o in self.objects}
        end = max([o[1] + o[2] for o in self.objects] or [0])
        cursor = _align(end, align_objects)
        placed = []
        for pid, tindex in objects:
            size = len(payload[pid])
            o = old.get(pid)
            if o is not None and size <= o[2]:
                start = o[1]
            else:
                start = cursor
                cursor = _align(cursor + size, align_objects)
            placed.append((pid, start, size, tindex))
        for entry in placed:
            meta += b'\0' * ((-len(meta) - self.header_size) % 4)
            meta += struct.pack(e + self.entry, *entry)
        meta += struct.pack(e + 'i', len(scripts))
        for fi, lid in scripts:
            meta += struct.pack(e + 'i', fi)
            meta += b'\0' * ((-len(meta) - self.header_size) % 4)
            meta += struct.pack(e + 'q', lid)
        meta += struct.pack(e + 'i', len(externals))
        for empty, guid, kind, path in externals:
            meta += empty + b'\0' + guid + struct.pack(e + 'i', kind) + path + b'\0'
        meta += struct.pack(e + 'i', len(self.ref_types))
        for t in self.ref_types:
            meta += t.raw
        meta += self.user_info + b'\0'
        if self.header_size + len(meta) <= self.data_offset:
            data_offset = self.data_offset
        else:
            data_offset = _align(self.header_size + len(meta), 16)
        old_body = self.data[self.data_offset:]
        body_len = max([len(old_body)] + [s + z for _, s, z, _ in placed])
        body = bytearray(body_len)
        body[:len(old_body)] = old_body
        for o in self.objects:
            body[o[1]:o[1] + o[2]] = bytes(o[2])
        for pid, start, size, _ in placed:
            body[start:start + size] = payload[pid]
        head = bytearray(self.data[:self.header_size])
        if self.version >= 22:
            struct.pack_into('>IQQ', head, 20, len(meta), data_offset + len(body), data_offset)
        else:
            struct.pack_into('>IIII', head, 0, len(meta), data_offset + len(body), self.version, data_offset)
        gap = bytearray(self.data[self.header_size + len(meta):self.data_offset]) if data_offset == self.data_offset else bytearray(data_offset - self.header_size - len(meta))
        if data_offset == self.data_offset:
            keep = self.metadata_end - self.header_size - len(meta)
            if keep > 0:
                gap[:keep] = bytes(keep)
        return bytes(head + meta + gap + body)
