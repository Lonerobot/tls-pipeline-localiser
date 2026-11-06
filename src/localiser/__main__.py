"""Prepare bundles outside the DCC, check for updates, or launch with prepared local code."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from .api import ROOT_VARIABLE, expose_environment
from .errors import LocaliserError, ReleaseUnavailableError
from .layout import DataLayout
from .resolve import SOURCE_LAST_KNOWN, resolve_release
from .sync import pipeline_config, prepared_release, sync_release

DISCOVERY_VARIABLES = {
    "maya": "PYTHONPATH",
    "nuke": "NUKE_PATH",
    "blender": "BLENDER_SYSTEM_SCRIPTS",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", help="pipeline root containing config.json (defaults to TLS_PIPELINE)")
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("sync", "check", "launch"):
        command = commands.add_parser(action)
        command.add_argument("host", choices=sorted(DISCOVERY_VARIABLES))
        command.add_argument("series")
        if action == "launch":
            command.add_argument("command", nargs=argparse.REMAINDER, help="DCC executable and arguments")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    if args.pipeline:
        env[ROOT_VARIABLE] = str(Path(args.pipeline).absolute())
    try:
        config = pipeline_config(env)
        if args.action == "check":
            target = resolve_release(args.host, args.series, config, DataLayout(config.bundle_repository), env)
            if target.source == SOURCE_LAST_KNOWN:
                raise ReleaseUnavailableError("cannot check for updates while the remote repository is offline")
            try:
                current = prepared_release(args.host, args.series, config).release_id
            except ReleaseUnavailableError:
                current = None
            if current != target.release_id:
                print(f"Update available: {args.host} {args.series}: {current or 'not prepared'} -> {target.release_id}")
                print("Run sync, then restart the DCC to use the update.")
                return 1
            print(f"Up to date: {args.host} {args.series}: {current}")
            return 0
        if args.action == "sync":
            release = sync_release(args.host, args.series, config, env)
            print(f"Prepared {args.host} {args.series}: {release.release_id} at {release.release_root}")
            print("Running DCC sessions are unchanged; restart to use this selection.")
            return 0
        if not args.command:
            parser.error("launch requires a DCC executable")
        release = prepared_release(args.host, args.series, config)
        expose_environment(release, env)
        bootstrap = Path(env[ROOT_VARIABLE]) / "bootstrap" / args.host
        variable = DISCOVERY_VARIABLES[args.host]
        # Blender accepts one system scripts directory; Maya and Nuke accept search paths.
        env[variable] = str(bootstrap)
        if args.host != "blender" and os.environ.get(variable):
            env[variable] += os.pathsep + os.environ[variable]
        return subprocess.run(args.command, env=env).returncode
    except (LocaliserError, OSError) as exc:
        print(f"localiser: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
