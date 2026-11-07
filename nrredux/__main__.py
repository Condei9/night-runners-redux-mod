import argparse
import sys

from . import NAME, __version__
from .patcher import Patcher, PatchError


def main(argv=None):
    p = argparse.ArgumentParser(prog='nrredux', description=NAME)
    p.add_argument('game', nargs='?', help='NIGHT-RUNNERS PRIVATE ALPHA game folder')
    p.add_argument('--restore', action='store_true', help='restore the stock files from the REDUX backup')
    p.add_argument('--check', action='store_true', help='only detect the game version and patch state')
    p.add_argument('--version', action='version', version='%s %s' % (NAME, __version__))
    args = p.parse_args(argv)
    if not args.game:
        from .gui import run
        return run()
    patcher = Patcher(args.game)
    try:
        if args.check:
            version, patched = patcher.detect()
            print('%s, %s' % (version, 'REDUX installed' if patched else 'stock'))
        elif args.restore:
            patcher.restore()
        else:
            patcher.install()
    except PatchError as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
