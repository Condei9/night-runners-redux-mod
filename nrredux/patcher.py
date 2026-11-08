import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .assetdelta import apply_bundle, apply_serialized, read_patch
from .catalog import Catalog, E36
from .dllpatch import apply as apply_dll, load_spec
from .unityfs import Bundle

DATA = 'NIGHT-RUNNERS PRIVATE ALPHA_Data'
AA = DATA + '/StreamingAssets/aa'
BUNDLES = AA + '/StandaloneWindows64'
CATALOG = AA + '/catalog.bin'
BACKUP = '_redux_backup'
STATE = 'redux-state.json'

VERSIONS = {
    '63d0258940797d14abc49192b130afdaecb2eb3eb54e6c48ef49219dbfed660f': '3.2.7',
    '9f918e73ac505805079519ad6c2730449ab01ccdd742282356191771039759f4': '3.2.8',
}


def resource_root():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def long_path(path):
    path = Path(os.path.abspath(path))
    if os.name != 'nt':
        return path
    s = str(path)
    if s.startswith('\\\\?\\'):
        return path
    if s.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + s[2:])
    return Path('\\\\?\\' + s)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


class PatchError(Exception):
    pass


class Patcher:
    def __init__(self, game, log=print):
        self.shown = Path(game)
        self.game = long_path(game)
        self.log = log
        self.patches = resource_root() / 'patches'
        self.plan = json.loads((self.patches / 'assets.json').read_text(encoding='utf-8'))

    def path(self, rel):
        return self.game / rel

    def check_game(self):
        exe = self.path('NIGHT-RUNNERS PRIVATE ALPHA.exe')
        dll = self.path('GameAssembly.dll')
        if not exe.exists() or not dll.exists() or not self.path(DATA).is_dir():
            raise PatchError('%s does not look like a NIGHT-RUNNERS PRIVATE ALPHA folder' % self.shown)

    def state(self):
        p = self.path(BACKUP) / STATE
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
        return None

    def detect(self):
        self.check_game()
        state = self.state()
        h = sha256(self.path('GameAssembly.dll'))
        if h in VERSIONS:
            return VERSIONS[h], False
        if state and h == state.get('dll_result'):
            return state['version'], True
        raise PatchError('GameAssembly.dll is neither a stock 3.2.7/3.2.8 build nor a REDUX-patched one (sha256 %s)' % h)

    def resolve(self, item):
        if item['kind'] == 'serialized':
            return DATA + '/' + item['source']
        hits = sorted(self.path(BUNDLES).glob(item['source']))
        hits = [h for h in hits if not h.name.endswith('.bak')]
        if len(hits) != 1:
            raise PatchError('expected exactly one bundle matching %s, found %d' % (item['source'], len(hits)))
        return BUNDLES + '/' + hits[0].name

    def plan_files(self):
        out = []
        for item in self.plan:
            src = self.resolve(item)
            dst = BUNDLES + '/' + item['target'] if item.get('target') else src
            out.append((item, src, dst))
        return out

    def backup(self, rels, version, dll_result, created):
        root = self.path(BACKUP)
        root.mkdir(exist_ok=True)
        for rel in rels:
            dst = root / rel
            if dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path(rel), dst)
        state = dict(patcher=__version__, version=version, dll_result=dll_result, files=sorted(rels), created=sorted(created))
        (root / STATE).write_text(json.dumps(state, indent=1), encoding='utf-8')

    def write(self, rel, data):
        p = self.path(rel)
        tmp = p.with_name(p.name + '.redux-tmp')
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def install(self):
        version, patched = self.detect()
        if patched:
            raise PatchError('this game folder is already patched with REDUX (%s); restore it first to re-apply' % version)
        self.log('Detected stock NIGHT-RUNNERS %s' % version)
        spec = load_spec(self.patches / version / 'GameAssembly.json')
        files = self.plan_files()
        for _, _, dst in files:
            if dst not in [s for _, s, _ in files] and self.path(dst).exists():
                raise PatchError('%s already exists; the folder is not stock' % dst)
        outputs = {}
        self.log('Patching GameAssembly.dll')
        try:
            outputs['GameAssembly.dll'] = apply_dll(self.path('GameAssembly.dll').read_bytes(), spec)
        except ValueError as e:
            raise PatchError(str(e))
        bundle_sizes = {}
        for item, src, dst in files:
            self.log('Patching %s' % Path(dst).name)
            head, blob = read_patch(self.patches / 'assets' / item['patch'])
            data = self.path(src).read_bytes()
            try:
                if item['kind'] == 'serialized':
                    out = apply_serialized(data, head['sf'], blob)
                else:
                    out, _ = apply_bundle(data, head, blob)
                    Bundle(out)
            except (ValueError, KeyError) as e:
                raise PatchError('%s: %s' % (src, e))
            outputs[dst] = out
            bundle_sizes[Path(dst).name] = len(out)
        self.log('Registering the BMW E36 M3 in the Addressables catalog')
        try:
            outputs[CATALOG] = Catalog(self.path(CATALOG).read_bytes()).add_cloned_bundle(E36, bundle_sizes[E36['bundle_file']])
        except (ValueError, KeyError) as e:
            raise PatchError('catalog.bin: %s' % e)
        originals = [rel for rel in outputs if self.path(rel).exists()]
        created = [rel for rel in outputs if not self.path(rel).exists()]
        self.log('Backing up %d original files to %s' % (len(originals), BACKUP))
        self.backup(originals, version, spec['result_sha256'], created)
        for rel, data in outputs.items():
            self.write(rel, data)
        if sha256(self.path('GameAssembly.dll')) != spec['result_sha256']:
            raise PatchError('GameAssembly.dll verification failed after writing')
        self.log('Done. NIGHT-RUNNERS REDUX is installed on %s.' % version)

    def restore(self):
        self.check_game()
        state = self.state()
        if not state:
            raise PatchError('no REDUX backup found in this folder')
        root = self.path(BACKUP)
        for rel in state['files']:
            self.log('Restoring %s' % Path(rel).name)
            shutil.copy2(root / rel, self.path(rel))
        for rel in state['created']:
            p = self.path(rel)
            if p.exists():
                self.log('Removing %s' % p.name)
                p.unlink()
        shutil.rmtree(root)
        self.log('Stock %s restored.' % state['version'])
