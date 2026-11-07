import struct


def align(n, a):
    return (n + a - 1) // a * a


class Image:
    def __init__(self, data):
        self.b = bytearray(data)
        self.pe = self.u32(0x3C)
        self.opt = self.pe + 24
        self.sh = self.opt + self.u16(self.pe + 20)

    def u16(self, o):
        return struct.unpack_from('<H', self.b, o)[0]

    def u32(self, o):
        return struct.unpack_from('<I', self.b, o)[0]

    @property
    def sections(self):
        out = []
        for i in range(self.u16(self.pe + 6)):
            p = self.sh + 40 * i
            name = bytes(self.b[p:p + 8]).rstrip(b'\0').decode()
            vsize, rva, rsize, rptr = struct.unpack_from('<IIII', self.b, p + 8)
            out.append(dict(name=name, vsize=vsize, rva=rva, rsize=rsize, rptr=rptr, flags=self.u32(p + 36), header=p))
        return out

    def section(self, name):
        for s in self.sections:
            if s['name'] == name:
                return s
        raise KeyError(name)

    def off(self, rva):
        for s in self.sections:
            if s['rva'] <= rva < s['rva'] + s['rsize']:
                return s['rptr'] + rva - s['rva']
        raise ValueError(hex(rva))

    def read(self, rva, n):
        o = self.off(rva)
        return bytes(self.b[o:o + n])

    def write(self, rva, data):
        o = self.off(rva)
        self.b[o:o + len(data)] = data

    def directory(self, i):
        return struct.unpack_from('<II', self.b, self.opt + 112 + 8 * i)

    def set_directory(self, i, rva, size):
        struct.pack_into('<II', self.b, self.opt + 112 + 8 * i, rva, size)

    @property
    def size_of_image(self):
        return self.u32(self.opt + 56)

    def exports(self):
        rva, _ = self.directory(0)
        e = self.off(rva)
        funcs, names, ords = (self.off(x) for x in struct.unpack_from('<III', self.b, e + 28))
        out = {}
        for i in range(self.u32(e + 24)):
            k = self.off(self.u32(names + 4 * i))
            name = bytes(self.b[k:self.b.index(0, k)]).decode()
            out[name] = self.u32(funcs + 4 * self.u16(ords + 2 * i))
        return out

    def exception_table(self):
        rva, size = self.directory(3)
        return self.read(rva, size)

    def add_section(self, name, rva, vsize, content, flags):
        count = self.u16(self.pe + 6)
        h = self.sh + 40 * count
        if h + 40 > self.u32(self.opt + 60):
            raise ValueError('no room for another section header')
        rptr = align(len(self.b), 512)
        rsize = align(len(content), 512)
        self.b.extend(bytes(rptr - len(self.b)) + content + bytes(rsize - len(content)))
        struct.pack_into('<8sIIIIIIHHI', self.b, h, name.encode(), vsize, rva, rsize, rptr, 0, 0, 0, 0, flags)
        struct.pack_into('<H', self.b, self.pe + 6, count + 1)
        struct.pack_into('<I', self.b, self.opt + 56, align(rva + vsize, 4096))
