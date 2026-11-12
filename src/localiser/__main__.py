"""Prepare bundles outside the DCC, check for updates, or launch with prepared local code."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from .api import ROOT_VARIABLE
from .config import default_pipeline_root
from .errors import ConfigError, LocaliserError, ReleaseUnavailableError
from .hosts import HOSTS, detect_installed_series
from .install_code import install_pipeline_code
from .launch import launch_environment
from .layout import DataLayout
from .provision import provision, unprovision
from .publisher import plan_bundle, publish_plan
from .resolve import SOURCE_LAST_KNOWN, override_variable, resolve_release
from .status import PROBLEMS, EntryStatus, check_enabled, needs_sync, sync_enabled
from .studio import set_studio_bundle, studio_entries
from .sync import (
    SHARED_VARIABLE,
    pipeline_config,
    pipeline_root,
    prepared_release,
    pull_release,
    source_variable,
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
    studio = commands.add_parser("studio", help="show or change which bundle the studio config selects (repository must be a folder)")
    studio_actions = studio.add_subparsers(dest="studio_action", required=True)
    studio_actions.add_parser("show", help="list the studio config's entries")
    studio_set = studio_actions.add_parser("set", help="select a bundle for a host and series")
    studio_set.add_argument("host", choices=sorted(DISCOVERY_VARIABLES))
    studio_set.add_argument("series")
    studio_set.add_argument("bundle", help='the release ID, or "none" to select no bundle (the pipeline then loads nothing)')
    commands.add_parser("check-all", help="check every enabled host and series for updates, installing nothing")
    commands.add_parser("hosts", help="show the supported hosts, the versions installed here and which are enabled")
    commands.add_parser(
        "install", help="put the stubs, pipeline entry and core into the pipeline root (the tray app does this at every start)"
    )
    entries = commands.add_parser(
        "provision",
        help="optional: install (or with --remove, remove) a per-user entry each enabled DCC finds at startup, so a DCC "
        "started any other way also loads the pipeline. The tray app does not install these",
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
        if args.action == "install":
            root = Path(env[ROOT_VARIABLE]) if env.get(ROOT_VARIABLE, "").strip() else default_pipeline_root(env)
            if root is None:
                raise ConfigError("no place to keep the pipeline could be found for this user; set TLS_PIPELINE")
            actions = install_pipeline_code(root)
            for action in actions:
                print(f"{action.change:9} {action.path}")
            print(f"{root}: " + (f"{len(actions)} files changed" if actions else "up to date"))
            return 0
        config = pipeline_config(env)
        if args.action == "studio":
            if args.studio_action == "show":
                for (host, series), version in sorted(studio_entries(config).items()):
                    print(f"{host:8} {series:8} {version or '(no bundle)'}")
                return 0
            version = None if args.bundle.lower() == "none" else args.bundle
            set_studio_bundle(config, args.host, args.series, version)
            print(f"Studio config: {args.host} {args.series} -> {version or 'no bundle'}. Machines pick it up at their next sync.")
            return 0
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
            if not syncing and any(needs_sync(entry) for entry in entries):
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
        env = launch_environment(args.host, args.series, config, env)
        return subprocess.run(args.command, env=env).returncode
    except (LocaliserError, OSError) as exc:
        print(f"localiser: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
