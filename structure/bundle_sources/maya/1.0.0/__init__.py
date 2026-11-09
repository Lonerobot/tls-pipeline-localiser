"""Maya bundle entry. The localiser runs this as a package inside Maya's userSetup, without syncing.

1. Exposes the bundle's directories on sys.path, so everything shipped is importable by name.
2. Builds the THE LINE menu from the script library.

Nothing here may stop Maya starting: failures are printed and the session carries on.
"""
import sys
import traceback
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parent


def expose_paths(root=BUNDLE_ROOT):
    """Add the bundle root and each top-level directory to sys.path, at the end.

    The root makes packages such as playblast_plus and LineTools importable; each directory makes its
    contents importable as top-level modules. They go last, so they can't shadow anything Maya or
    another tool already provides. Directories added to the bundle later are picked up on the next start.
    """
    directories = sorted(
        (item for item in root.iterdir() if item.is_dir() and not item.name.startswith((".", "__"))),
        key=lambda item: item.name.casefold(),
    )
    for path in [root, *directories]:
        if str(path) not in sys.path:
            sys.path.append(str(path))


try:
    expose_paths()
    from LineTools import menu

    menu.install()
except Exception:
    traceback.print_exc()
    print("TLS pipeline: maya bundle failed to initialise")
