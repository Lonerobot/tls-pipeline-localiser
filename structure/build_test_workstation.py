"""Prepare the test workstation. Safe to re-run; it rebuilds everything it generates.

1. Copies the core (src/localiser) into the pipeline root, as the installer eventually would.
2. Publishes each bundle source folder (bundle_sources/<host>/<version>) into the fake remote
   repository as hosts/<host>/<version>/{pipeline.zip, manifest.json}, with the core's publisher. Every
   package in shared_sources is merged into each bundle, so a release stays one self-contained,
   verified zip.

    python structure/build_test_workstation.py

To publish one bundle to a real repository, use the same publisher directly:

    python -m localiser publish <source folder> <host> <version> --shared structure/shared_sources
"""
import shutil
import sys
from pathlib import Path

STRUCTURE = Path(__file__).resolve().parent
PIPELINE = STRUCTURE / "THE-LINE" / "pipeline"
SOURCES = STRUCTURE / "bundle_sources"
SHARED = STRUCTURE / "shared_sources"
REMOTE = PIPELINE / "fake_remote_repository"
CORE = STRUCTURE.parent / "src" / "localiser"

sys.path.insert(0, str(CORE.parent))
from localiser import plan_bundle, publish_plan  # noqa: E402


def main():
    installed_core = PIPELINE / "localiser"
    shutil.rmtree(installed_core, ignore_errors=True)
    shutil.copytree(CORE, installed_core, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"core    -> {installed_core}")

    shutil.rmtree(REMOTE / "hosts", ignore_errors=True)  # generated; releases are immutable, so rebuild from scratch
    for host_dir in sorted(SOURCES.iterdir()):
        for version_dir in sorted(host_dir.iterdir()):
            plan = plan_bundle(version_dir, host_dir.name, [SHARED])
            manifest = publish_plan(plan, REMOTE, version_dir.name)
            print(
                f"bundle  -> hosts/{manifest.package_id}/{manifest.release_id}  "
                f"python_root={manifest.python_root!r}  shared={list(plan.shared)}"
            )


if __name__ == "__main__":
    main()
