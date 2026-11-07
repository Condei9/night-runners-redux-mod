import struct

MAGIC = 0x0DE38942
NONE = 0xFFFFFFFF

E36 = dict(
    donor_key='d1c2b4f472e4445b894c93d71bb9995c',
    bundle_file='catalog_carorigins_assets_carorigin_bmw_e36_m3_92_677070ff253ff1a72eb56ad122893370.bundle',
    bundle_name='6a8fd0f28b5723c98b0070e63f7f88c5',
    bundle_hash='4785a3085f4d10b65e0b3f933fa3de2e',
    prefab_path='Assets/PlanetJem/__Legacy/_OBJECTS/_CARS/_BMW_E36/carorigin_BMW_E36_M3.prefab',
    address='carorigin_BMW_E36_M3',
    guid='4501b1e73bfb2835e5c4df44c24f1696',
)


class Catalog:
    def __init__(self, data):
        self.b = bytearray(data)
        self.hdr = list(struct.unpack_from('<8I', self.b, 0))
        if self.hdr[:2] != [MAGIC, 2]:
            raise ValueError('unsupported Addressables catalog')

    def u32(self, o):
        return struct.unpack_from('<I', self.b, o)[0]

    def size(self, o):
        return self.u32(o - 4)

    def text(self, o, sep='/'):
        if o == NONE:
            return None
        flags = o & 0xC0000000
        o &= 0x3FFFFFFF
        if flags & 0x40000000:
            parts = []
            node = o
            while node != NONE:
                p, prev = struct.unpack_from('<II', self.b, node)
                parts.append(self.text(p, sep))
                node = prev
            return sep.join(reversed(parts))
        return bytes(self.b[o:o + self.size(o)]).decode('utf-16le' if flags & 0x80000000 else 'latin1')

    def pairs(self, k):
        return [struct.unpack_from('<II', self.b, k + 8 * i) for i in range(self.size(k) // 8)]

    def key(self, ko):
        t, o = struct.unpack_from('<II', self.b, ko)
        ref, sep = struct.unpack_from('<II', self.b, o)
        return self.text(ref, chr(sep) if sep else '/'), t

    def locations(self, lo):
        return [self.u32(lo + 4 * j) for j in range(self.size(lo) // 4)]

    def location(self, at):
        return list(struct.unpack_from('<7I', self.b, at))

    def put(self, data):
        self.b.extend(struct.pack('<I', len(data)))
        at = len(self.b)
        self.b.extend(data)
        return at

    def string(self, text):
        return self.put(text.encode('ascii'))

    def keys(self):
        return {self.key(ko)[0]: (ko, lo) for ko, lo in self.pairs(self.hdr[2])}

    def add_cloned_bundle(self, ids, bundle_size):
        names = self.keys()
        for k in (ids['guid'], ids['address'], ids['bundle_file']):
            if k in names:
                raise ValueError('catalog already contains %s' % k)
        ko, lo = names[ids['donor_key']]
        string_type = self.key(ko)[1]
        asset_loc, = self.locations(lo)
        asset = self.location(asset_loc)
        if not self.text(asset[2], '.').endswith('BundledAssetProvider'):
            raise ValueError('donor entry is not a bundled asset')
        deps = self.locations(asset[3])
        bundle = self.location(deps[0])
        if not self.text(bundle[2], '.').endswith('AssetBundleProvider'):
            raise ValueError('donor dependency is not an asset bundle')
        opt_type, opt = struct.unpack_from('<II', self.b, bundle[5])
        _, _, crc, _, common = struct.unpack_from('<5I', self.b, opt)
        n_hash = self.put(bytes.fromhex(ids['bundle_hash']))
        n_opts = self.put(struct.pack('<5I', n_hash, self.string(ids['bundle_name']), crc, bundle_size, common))
        n_extra = self.put(struct.pack('<II', opt_type, n_opts))
        bundle_id = self.text(bundle[1]).replace(self.text(bundle[0]), ids['bundle_file'])
        n_bundle = self.put(struct.pack('<7I', self.string(ids['bundle_file']), self.string(bundle_id), bundle[2], NONE, bundle[4], n_extra, bundle[6]))
        n_deps = self.put(struct.pack('<%dI' % len(deps), n_bundle, *deps[1:]))
        n_asset = self.put(struct.pack('<7I', self.string(ids['address']), self.string(ids['prefab_path']), asset[2], n_deps, asset[4], asset[5], asset[6]))
        new = []
        for text, locs in ((ids['guid'], [n_asset]), (ids['address'], [n_asset]), (ids['bundle_file'], [n_bundle])):
            k = self.put(struct.pack('<II', self.string(text), 0))
            new.append((self.put(struct.pack('<II', string_type, k)), self.put(struct.pack('<%dI' % len(locs), *locs))))
        old = self.pairs(self.hdr[2])
        self.hdr[2] = self.put(b''.join(struct.pack('<II', *p) for p in old + new))
        struct.pack_into('<8I', self.b, 0, *self.hdr)
        check = self.keys()
        loc, = self.locations(check[ids['guid']][1])
        if self.text(self.location(loc)[1]) != ids['prefab_path']:
            raise ValueError('catalog verification failed')
        return bytes(self.b)
