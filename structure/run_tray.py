"""Try the tray app without touching your real profile.

    python structure/run_tray.py                       # a scratch pipeline root; opens on the Settings page
    python structure/run_tray.py --enable maya:2026 nuke:17.0 blender:5.2   # start with these hosts enabled in the config
    python structure/run_tray.py --reset               # throw the scratch root away first
    python structure/run_tray.py --use-real-profile    # no isolation: your real %LOCALAPPDATA% root and entries

The scratch root lives in %TEMP%\\tls_tray_test and has its own config.json (pointing at the fake remote
repository built by build_test_workstation.py), its own bundle store and a copy of the bootstrap stubs. Maya,
Nuke and Blender entries that Save installs go to scratch folders too, so nothing outside it changes.
Needs PySide6 (`pip install .[tray]`, or use the repo .venv). Quit the app from its tray menu.
--enable only writes `hosts` into the scratch config; the DCC entries are installed when you press Save in the app.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STRUCTURE = Path(__file__).resolve().parent
SRC = STRUCTURE.parent / "src"
PIPELINE = STRUCTURE / "THE-LINE" / "pipeline"
REMOTE = PIPELINE / "fake_remote_repository"
SCRATCH = Path(tempfile.gettempdir()) / "tls_tray_test"


def parse_enable(items):
    hosts = {}
    for item in items:
        host, _, series = item.partition(":")
        if not host or not series:
            raise SystemExit(f"--enable takes host:series, for example maya:2026 (got {item!r})")
        hosts.setdefault(host, []).append(series)
    return hosts


def prepare(scratch: Path, hosts: dict) -> Path:
    """Make the scratch pipeline root if it isn't there yet. An existing one keeps its state between runs."""
    root = scratch / "root"
    if not (root / "config.json").is_file():
        root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PIPELINE / "bootstrap", root / "bootstrap", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        sys.path.insert(0, str(SRC))
        from localiser import save_local_config

        save_local_config(root / "config.json", {"remote_repository": str(REMOTE), "bundle_repository": "./bundles"})
    if hosts:
        sys.path.insert(0, str(SRC))
        from localiser import save_local_config

        save_local_config(root / "config.json", {"hosts": hosts})
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--enable", nargs="+", default=[], metavar="HOST:SERIES", help="hosts to enable at start")
    parser.add_argument("--reset", action="store_true", help="delete the scratch root first")
    parser.add_argument("--scratch", type=Path, default=SCRATCH, help=f"scratch folder (default {SCRATCH})")
    parser.add_argument("--use-real-profile", action="store_true", help="no isolation; uses your real pipeline root")
    parser.add_argument("--no-show", action="store_true", help="start in the tray only, without opening the window")
    args = parser.parse_args()

    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("PySide6 isn't installed for this Python. Activate the repo .venv or run `pip install PySide6`.")
        return 1
    if not (REMOTE / "hosts").is_dir():
        print("Note: the fake remote repository is empty. Run `python structure/build_test_workstation.py` first.")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    if not args.use_real_profile:
        if args.reset:
            shutil.rmtree(args.scratch, ignore_errors=True)
        root = prepare(args.scratch, parse_enable(args.enable))
        env.update({
            "TLS_PIPELINE": str(root),
            "MAYA_APP_DIR": str(args.scratch / "maya"),
            "APPDATA": str(args.scratch / "appdata"),
            "USERPROFILE": str(args.scratch / "home"),  # where Nuke's ~/.nuke is looked for
        })
        for name in ("BLENDER_USER_SCRIPTS", "BLENDER_USER_CONFIG"):
            env.pop(name, None)
        print(f"scratch root: {root}")
        print(f"entries go under: {args.scratch}")
    else:
        env.pop("TLS_PIPELINE", None)
        print("Using your real profile: Save will write the real config and install the real DCC entries.")

    command = [sys.executable, "-m", "localiser_tray"] + ([] if args.no_show else ["--show"])
    print("run:", " ".join(command))
    return subprocess.run(command, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
