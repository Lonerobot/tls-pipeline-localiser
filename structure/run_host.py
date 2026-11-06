"""Launch a DCC with the environment variables the studio would define.

    python structure/run_host.py maya            # headless: starts the host, runs the stubs, exits
    python structure/run_host.py nuke --gui      # full application
    python structure/run_host.py blender --exe "D:\\Blender\\blender.exe"

Run build_test_workstation.py and explicitly sync the host/series first (see README).
The variables each host needs are in ENVIRONMENT below.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent / "THE-LINE" / "pipeline"
BOOTSTRAP = PIPELINE / "bootstrap"

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

# (gui command, headless command)
COMMANDS = {
    "maya": (
        [MAYA / "maya.exe"],
        [MAYA / "mayapy.exe", "-c", "import maya.standalone as s; s.initialize(name='python')"],
    ),
    "nuke": ([NUKE / "Nuke17.0.exe"], [NUKE / "Nuke17.0.exe", "-t"]),
    "blender": ([BLENDER / "blender.exe"], [BLENDER / "blender.exe", "-b", "--python-expr", "pass"]),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", choices=sorted(ENVIRONMENT))
    parser.add_argument("--gui", action="store_true", help="launch the full application instead of headless")
    parser.add_argument("--exe", help="override the executable path")
    args = parser.parse_args()

    gui, headless = COMMANDS[args.host]
    command = [str(part) for part in (gui if args.gui else headless)]
    if args.exe:
        command[0] = args.exe

    env = dict(os.environ)
    env.update({name: str(value) for name, value in ENVIRONMENT[args.host].items()})
    for name, value in ENVIRONMENT[args.host].items():
        print(f"{name}={value}")
    print("run:", " ".join(command))
    # Closing stdin lets Nuke's terminal mode exit instead of waiting at its prompt.
    return subprocess.run(command, env=env, stdin=subprocess.DEVNULL).returncode


if __name__ == "__main__":
    sys.exit(main())
