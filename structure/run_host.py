"""Launch a DCC with the environment variables the studio would define.

    python structure/run_host.py maya            # headless: starts the host, runs the stubs, exits
    python structure/run_host.py nuke --gui      # full application
    python structure/run_host.py blender --exe "D:\\Blender\\blender.exe"
    python structure/run_host.py nuke --gui --source structure/bundle_sources/nuke/1.0.0   # unpublished source
    python structure/run_host.py maya --bundle 1.0.1                                        # an installed release, this run only

Run build_test_workstation.py first. Each run syncs the host's selection to the studio config
(structure/THE-LINE/pipeline/fake_remote_repository/config.json) before launching, so editing that file and
running again is enough; use --no-sync to run exactly what was last synced.
The variables each host needs are in ENVIRONMENT below.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent / "THE-LINE" / "pipeline"
BOOTSTRAP = PIPELINE / "bootstrap"
SHARED = Path(__file__).resolve().parent / "shared_sources"

# What each host needs in its environment. TLS_PIPELINE is common; the other variable is how
# the host finds its bootstrap stub (verified mechanisms, see .copilot/01_design_brief.md section 8.4).
ENVIRONMENT = {
    "maya": {"TLS_PIPELINE": PIPELINE, "PYTHONPATH": BOOTSTRAP / "maya"},
    "nuke": {"TLS_PIPELINE": PIPELINE, "NUKE_PATH": BOOTSTRAP / "nuke"},
    "blender": {"TLS_PIPELINE": PIPELINE, "BLENDER_SYSTEM_SCRIPTS": BOOTSTRAP / "blender"},
}

MAYA = Path(r"C:\Program Files\Autodesk\Maya2026\bin")
NUKE = Path(r"C:\Program Files\Nuke17.0v3")
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2")

SERIES = {"maya": "2026", "nuke": "17.0", "blender": "5.2"}  # the version each executable below is
SRC = Path(__file__).resolve().parent.parent / "src"

# (gui command, headless command)
COMMANDS = {
    "maya": (
        [MAYA / "maya.exe"],
        [MAYA / "mayapy.exe", "-c", "import maya.standalone as s; s.initialize(name='python')"],
    ),
    "nuke": ([NUKE / "Nuke17.0.exe"], [NUKE / "Nuke17.0.exe", "-t"]),
    "blender": ([BLENDER / "blender.exe"], [BLENDER / "blender.exe", "-b", "--python-expr", "pass"]),
}


def sync_first(host, env):
    """Bring the selection up to date with the studio config, as the tray app would, so an edited config.json
    takes effect. A DCC itself never reads the config; it loads whatever was selected by the last sync."""
    sys.path.insert(0, str(SRC))
    from localiser import pipeline_config, sync_entry

    series = SERIES[host]
    try:
        entry = sync_entry(host, series, pipeline_config(env), env)
    except Exception as exc:  # e.g. no config yet; the host then runs what is already installed
        print(f"sync {host} {series}: skipped ({exc})")
        return
    print(f"sync {host} {series}: {entry.state}, selected {entry.selected or 'nothing'}" + (f" ({entry.message})" if entry.message else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", choices=sorted(ENVIRONMENT))
    parser.add_argument("--gui", action="store_true", help="launch the full application instead of headless")
    parser.add_argument("--exe", help="override the executable path")
    parser.add_argument("--source", metavar="DIR", help="run this unpublished bundle source folder in place (dev mode)")
    parser.add_argument("--bundle", metavar="RELEASE", help="use this installed release for this run only")
    parser.add_argument("--no-sync", action="store_true", help="run what was last synced, without checking the studio config")
    args = parser.parse_args()

    gui, headless = COMMANDS[args.host]
    command = [str(part) for part in (gui if args.gui else headless)]
    if args.exe:
        command[0] = args.exe

    env = dict(os.environ)
    env.update({name: str(value) for name, value in ENVIRONMENT[args.host].items()})
    host = args.host.upper()
    if not (args.no_sync or args.source or args.bundle):  # a source or a pin bypasses the selection anyway
        sync_first(args.host, env)
    if args.source:
        env[f"TLS_PIPELINE_{host}_SOURCE"] = str(Path(args.source).resolve())
        env["TLS_PIPELINE_SHARED_SOURCES"] = str(SHARED)  # the packages every bundle gets at publish time; put on sys.path in place
    if args.bundle:
        env[f"TLS_PIPELINE_{host}_BUNDLE"] = args.bundle
    for name in (f"TLS_PIPELINE_{host}_SOURCE", "TLS_PIPELINE_SHARED_SOURCES", f"TLS_PIPELINE_{host}_BUNDLE"):
        if name in env and name not in ENVIRONMENT[args.host]:
            print(f"{name}={env[name]}")
    for name, value in ENVIRONMENT[args.host].items():
        print(f"{name}={value}")
    print("run:", " ".join(command))
    # Closing stdin lets Nuke's terminal mode exit instead of waiting at its prompt.
    return subprocess.run(command, env=env, stdin=subprocess.DEVNULL).returncode


if __name__ == "__main__":
    sys.exit(main())
