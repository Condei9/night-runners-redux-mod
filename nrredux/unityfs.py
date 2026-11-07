import hashlib
import lzma
import struct

import lz4.block

BLOCK = 0x20000


def _lzma(buf, size):
    props = buf[0]
    dict_size = struct.unpack_from('<I', buf, 1)[0]
    lc = props % 9
    props //= 9
    filters = [{'id': lzma.FILTER_LZMA1, 'dict_size': dict_size, 'lc': lc, 'lp': props % 5, 'pb': props // 5}]
    return lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filters).decompress(buf[5:], size)


def decompress(buf, size, flags):
    kind = flags & 0x3F
    if kind == 0:
        return bytes(buf)
    if kind == 1:
        return _lzma(buf, size)
    if kind in (2, 3):
        return lz4.block.decompress(bytes(buf), uncompressed_size=size)
    raise ValueError('unsupported compression %d' % kind)


def compress(buf):
    return lz4.block.compress(bytes(buf), mode='high_compression', compression=9, store_size=False)


class Bundle:
    def __init__(self, data):
        self.raw = data
        p = data.index(0) + 1
        self.signature = data[:p - 1]
        if self.signature != b'UnityFS':
            raise ValueError('not a UnityFS bundle')
        self.format = struct.unpack_from('>I', data, p)[0]
        p += 4
        e = data.index(0, p)
        self.engine = data[p:e]
        p = e + 1
        e = data.index(0, p)
        self.revision = data[p:e]
        p = e + 1
        self.header_end = p
        total, csize, usize, flags = struct.unpack_from('>qIII', data, p)
        p += 20
        if self.format >= 7:
            p = (p + 15) & ~15
        if flags & 0x80:
            raise ValueError('block info at end of file is not supported')
        self.flags = flags
        info = decompress(data[p:p + csize], usize, flags)
        p += csize
        if flags & 0x200:
            p = (p + 15) & ~15
        count = struct.unpack_from('>i', info, 16)[0]
        self.blocks = []
        q = 20
        for _ in range(count):
            self.blocks.append(struct.unpack_from('>IIH', info, q))
            q += 10
        chunks = []
        self.block_cache = {}
        for us, cs, bf in self.blocks:
            piece = data[p:p + cs]
            plain = decompress(piece, us, bf)
            chunks.append(plain)
            if bf & 0x3F in (2, 3):
                self.block_cache[hashlib.sha1(plain).digest()] = (bytes(piece), bf)
            p += cs
        stream = b''.join(chunks)
        nodes = struct.unpack_from('>i', info, q)[0]
        q += 4
        self.entries = []
        for _ in range(nodes):
            off, size, nf = struct.unpack_from('>qqI', info, q)
            q += 20
            e = info.index(0, q)
            name = info[q:e].decode()
            q = e + 1
            self.entries.append([name, nf, stream[off:off + size]])
        self.block_flags = next((bf for _, _, bf in self.blocks if bf & 0x3F), 0x43)

    def entry(self, name):
        for n, f, d in self.entries:
            if n == name:
                return d
        raise KeyError(name)

    def serialized_name(self):
        for n, f, d in self.entries:
            if f & 4:
                return n
        return self.entries[0][0]

    def build(self, entries):
        stream = bytearray()
        nodes = []
        for name, nf, payload in entries:
            nodes.append((len(stream), len(payload), nf, name))
            stream += payload
        blocks = []
        bodies = []
        for s in range(0, len(stream), BLOCK):
            plain = bytes(stream[s:s + BLOCK])
            cached = self.block_cache.get(hashlib.sha1(plain).digest())
            if cached:
                piece, bf = cached
            else:
                piece = compress(plain)
                bf = (self.block_flags & ~0x3F) | 3
                if len(piece) >= len(plain):
                    piece = plain
                    bf = self.block_flags & ~0x3F
            blocks.append((len(plain), len(piece), bf))
            bodies.append(piece)
        info = bytearray(16)
        info += struct.pack('>i', len(blocks))
        for b in blocks:
            info += struct.pack('>IIH', *b)
        info += struct.pack('>i', len(nodes))
        for off, size, nf, name in nodes:
            info += struct.pack('>qqI', off, size, nf) + name.encode() + b'\0'
        packed_info = compress(info)
        flags = (self.flags & ~0x3F & ~0x80) | 3
        head = bytearray(self.raw[:self.header_end])
        fixed = len(head) + 20
        if self.format >= 7:
            fixed = (fixed + 15) & ~15
        start = fixed + len(packed_info)
        if flags & 0x200:
            start = (start + 15) & ~15
        total = start + sum(len(b) for b in bodies)
        head += struct.pack('>qIII', total, len(packed_info), len(info), flags)
        head += bytes(fixed - len(head))
        head += packed_info
        head += bytes(start - len(head))
        for b in bodies:
            head += b
        return bytes(head)
