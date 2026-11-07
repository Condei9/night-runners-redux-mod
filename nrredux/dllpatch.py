import base64
import hashlib
import json
import zlib

from .pe import Image


def pack_bytes(data):
    return base64.b64encode(zlib.compress(bytes(data), 9)).decode()


def unpack_bytes(text):
    return zlib.decompress(base64.b64decode(text))


def load_spec(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def apply(stock, spec):
    if hashlib.sha256(stock).hexdigest() != spec['stock_sha256']:
        raise ValueError('GameAssembly.dll is not the stock build this patch expects')
    img = Image(stock)
    game_table = img.exception_table()
    for site in spec['sites']:
        rva = int(site['rva'], 16)
        old = bytes.fromhex(site['old'])
        if img.read(rva, len(old)) != old:
            raise ValueError('unexpected bytes at %s' % site['rva'])
        img.write(rva, bytes.fromhex(site['new']))
    exception_dir = None
    for sec in spec['sections']:
        content = bytearray()
        rva = int(sec['rva'], 16)
        for seg in sec['segments']:
            if seg[0] == 'game_exceptions':
                start = rva + len(content)
                content += game_table
                extra = unpack_bytes(seg[1]) if len(seg) > 1 else b''
                content += extra
                if len(seg) > 2:
                    exception_dir = (start, len(game_table) + seg[2])
            else:
                content += unpack_bytes(seg[1])
        content += bytes(int(sec['rsize'], 16) - len(content))
        img.add_section(sec['name'], rva, int(sec['vsize'], 16), bytes(content), int(sec['flags'], 16))
    if exception_dir:
        img.set_directory(3, *exception_dir)
    out = bytes(img.b)
    if spec.get('result_sha256') and hashlib.sha256(out).hexdigest() != spec['result_sha256']:
        raise ValueError('patched GameAssembly.dll does not match the expected result')
    return out
