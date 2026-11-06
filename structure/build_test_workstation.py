"""Prepare the test workstation. Safe to re-run; it rebuilds everything it generates.

1. Copies the core (src/localiser) into the pipeline root, as the installer eventually would.
2. Publishes each bundle source folder (bundle_sources/<host>/<version>) into the fake remote
   repository as hosts/<host>/<version>/{pipeline.zip, manifest.json}.

    python structure/build_test_workstation.py
"""
import shutil
import sys
from pathlib import Path

STRUCTURE = Path(__file__).resolve().parent
PIPELINE = STRUCTURE / "THE-LINE" / "pipeline"
SOURCES = STRUCTURE / "bundle_sources"
REMOTE = PIPELINE / "fake_remote_repository"
CORE = STRUCTURE.parent / "src" / "localiser"

# The bundle's own entry point is <python_root>/__init__.py. Blender's bundle keeps it in startup/.
PYTHON_ROOT = {"blender": "startup"}

sys.path.insert(0, str(CORE.parent))
from localiser import publish_release  # noqa: E402


def main():
    installed_core = PIPELINE / "localiser"
    shutil.rmtree(installed_core, ignore_errors=True)
    shutil.copytree(CORE, installed_core, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"core    -> {installed_core}")

    shutil.rmtree(REMOTE / "hosts", ignore_errors=True)  # generated; releases are immutable, so rebuild from scratch
    for host_dir in sorted(SOURCES.iterdir()):
        for version_dir in sorted(host_dir.iterdir()):
            manifest = publish_release(
                version_dir, REMOTE, host_dir.name, version_dir.name, python_root=PYTHON_ROOT.get(host_dir.name, ".")
            )
            print(f"bundle  -> hosts/{manifest.package_id}/{manifest.release_id}  python_root={manifest.python_root!r}")


if __name__ == "__main__":
    main()
