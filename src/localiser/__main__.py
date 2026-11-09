"""Prepare bundles outside the DCC, check for updates, or launch with prepared local code."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from .api import ROOT_VARIABLE, expose_environment
from .errors import ConfigError, LocaliserError, ReleaseUnavailableError
from .hosts import HOSTS, detect_installed_series
from .layout import DataLayout
from .provision import provision, unprovision
from .publisher import plan_bundle, publish_plan
from .resolve import SOURCE_LAST_KNOWN, override_variable, resolve_release
from .status import NOT_PREPARED, PROBLEMS, UPDATE_AVAILABLE, EntryStatus, check_enabled, sync_enabled
from .sync import (
    SHARED_VARIABLE,
    pipeline_config,
    pipeline_root,
    prepared_release,
    pull_release,
    source_variable,
    startup_release,
    sync_release,
)

DISCOVERY_VARIABLES = {name: info.discovery_variable for name, info in HOSTS.items()}


def _describe(entry: EntryStatus) -> str:
    """One line per host and series: what it runs, what the studio asks for, and any reason it can't."""
    detail = {
        "current": f"up to date: {entry.selected}",
        "update_available": f"update: {entry.selected} -> {entry.target}",
        "not_prepared": f"not prepared; target {entry.target}",
    }.get(entry.state, f"{entry.state}: {entry.message}")
    return f"{entry.host} {entry.series}: {detail}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", help="pipeline root containing config.json (defaults to TLS_PIPELINE)")
    commands = parser.add_subparsers(dest="action", required=True)
    publish = commands.add_parser("publish", help="publish a bundle source folder as a new immutable release")
    publish.add_argument("source", help="the bundle source folder")
    publish.add_argument("host", choices=sorted(DISCOVERY_VARIABLES))
    publish.add_argument("version", help="the release ID, such as 1.0.3")
    publish.add_argument(
        "--shared", action="append", default=[], metavar="DIR", help="folder of packages to merge into the bundle (repeatable)"
    )
    publish.add_argument("--remote", help="repository to publish to (defaults to remote_repository in the pipeline config)")
    pull = commands.add_parser("pull", help="install a release locally without selecting it (for pins and project launches)")
    pull.add_argument("host", choices=sorted(DISCOVERY_VARIABLES))
    pull.add_argument("release", help="the release ID to install, such as 1.0.3")
    commands.add_parser("sync-all", help="sync every host and series enabled in the local config")
    commands.add_parser("check-all", help="check every enabled host and series for updates, installing nothing")
    commands.add_parser("hosts", help="show the supported hosts, the versions installed here and which are enabled")
    entries = commands.add_parser(
        "provision", help="install (or with --remove, remove) the per-user entry each enabled DCC finds at startup"
    )
    entries.add_argument("--remove", action="store_true")
    for action in ("sync", "check", "launch"):
        command = commands.add_parser(action)
        command.add_argument("host", choices=sorted(DISCOVERY_VARIABLES))
        command.add_argument("series")
        if action in ("sync", "launch"):
            what = "select this release machine-wide instead of the studio default" if action == "sync" else (
                "use this installed release for this launch only"
            )
            command.add_argument("--bundle", metavar="RELEASE", help=what)
        if action == "launch":
            command.add_argument("--source", metavar="DIR", help="run this unpublished bundle source folder (dev mode)")
            command.add_argument(
                "--shared", action="append", default=[], metavar="DIR",
                help="folder of shared packages to merge into --source (repeatable)",
            )
            command.add_argument("command", nargs=argparse.REMAINDER, help="DCC executable and arguments")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    if args.pipeline:
        env[ROOT_VARIABLE] = str(Path(args.pipeline).absolute())
    try:
        if args.action == "publish":
            if args.remote:
                remote = Path(args.remote)
            else:
                remote = pipeline_config(env).remote_repository
                if not isinstance(remote, Path):
                    raise ConfigError(
                        f"remote_repository is a web address ({remote.location}); publish to its folder with --remote <folder>"
                    )
            plan = plan_bundle(args.source, args.host, args.shared)
            manifest = publish_plan(plan, remote, args.version)
            shared = ", ".join(plan.shared) or "none"
            print(f"Published {manifest.package_id}/{manifest.release_id} to {remote}")
            print(f"  python_root={manifest.python_root!r}  files={len(plan.entries)}  shared={shared}")
            print(f"  sha256={manifest.sha256}")
            print("Set bundle_version in the remote config.json to select it, then run sync.")
            return 0
        if args.action == "hosts":
            try:
                enabled = pipeline_config(env).hosts
            except ConfigError:
                enabled = {}
            for name, info in HOSTS.items():
                installed = detect_installed_series(name)
                print(
                    f"{info.display_name:8} installed: {', '.join(installed) or 'none found'}"
                    f"   enabled: {', '.join(enabled.get(name, ())) or 'none'}"
                )
            return 0
        config = pipeline_config(env)
        if args.action == "provision":
            actions = unprovision(config, env) if args.remove else provision(pipeline_root(env), config, env)
            if not actions:
                print('No hosts are enabled. Add them to "hosts" in the local config.json first.')
            for action in actions:
                print(f"{action.host:8} {action.change:9} {action.path}")
            return 0
        if args.action in ("sync-all", "check-all"):
            syncing = args.action == "sync-all"
            entries = (sync_enabled if syncing else check_enabled)(config, env)
            if not entries:
                print('No hosts are enabled. Add them to "hosts" in the local config.json, for example {"nuke": ["17.0"]}.')
                return 0
            for entry in entries:
                print(_describe(entry))
            if any(entry.state in PROBLEMS for entry in entries):
                return 2
            if not syncing and any(entry.state in (UPDATE_AVAILABLE, NOT_PREPARED) for entry in entries):
                print("Run sync-all, then restart the DCCs to use the updates.")
                return 1
            return 0
        if args.action == "pull":
            release = pull_release(args.host, args.release, config)
            print(f"Installed {args.host} {args.release} at {release.release_root}")
            print(f"Not selected. Use it for one launch with: {override_variable(args.host)}={args.release}")
            return 0
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
            if args.bundle:
                env[override_variable(args.host)] = args.bundle
            release = sync_release(args.host, args.series, config, env)
            print(f"Prepared {args.host} {args.series}: {release.release_id} at {release.release_root}")
            print("Running DCC sessions are unchanged; restart to use this selection.")
            return 0
        if not args.command:
            parser.error("launch requires a DCC executable")
        if args.bundle:
            env[override_variable(args.host)] = args.bundle
        if args.source:
            env[source_variable(args.host)] = str(Path(args.source).absolute())
        if args.shared:
            env[SHARED_VARIABLE] = os.pathsep.join(str(Path(p).absolute()) for p in args.shared)
        if env.get(source_variable(args.host), "").strip():
            # The stub in the DCC lays the source out itself; check now that it can be.
            plan_bundle(env[source_variable(args.host)], args.host, [p for p in env.get(SHARED_VARIABLE, "").split(os.pathsep) if p])
        else:
            expose_environment(startup_release(args.host, args.series, config, env), env)
        bootstrap = pipeline_root(env) / "bootstrap" / args.host
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
