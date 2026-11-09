# Test workstation data flow

How the folders in [`structure/`](.) relate, which script writes each one, and how to make a new bundle. The diagrams are Mermaid sources in [`docs/diagrams/`](../docs/diagrams), rendered to SVG with `python docs/build_diagrams.py` (needs Node.js and Chrome or Edge). Edit the `.mmd` files, not the SVGs.

`bundle_sources` is **not** unpacked from `fake_remote_repository`. It is the other way round: `bundle_sources` holds the editable source, and the remote holds the published, zipped output built from it.

## Data flow

![Data flow from bundle_sources through publish and sync to the running DCC](../docs/diagrams/data-flow.svg)

## What each area is

![Folder map grouped by who writes each area](../docs/diagrams/folder-map.svg)

| Area | Role | Written by |
|---|---|---|
| `bundle_sources/` | Source folders, one per release. This is where bundles are authored. | You |
| `shared_sources/` | Packages every bundle needs, such as `tls_common` (logging). Copied into each bundle at publish time. | You |
| `THE-LINE/pipeline/fake_remote_repository/hosts/` | Stand-in for the network share: the zip and a manifest holding its sha256. | `build_test_workstation.py`, through `localiser publish` (wipes and republishes all of `hosts/` every run) |
| `THE-LINE/pipeline/fake_remote_repository/config.json` | The studio default: which bundle version each host and DCC series uses. | You, by hand |
| `THE-LINE/pipeline/localiser/` | A copy of `src/localiser`, as the installer would place it. | `build_test_workstation.py` |
| `THE-LINE/pipeline/bundles/` | Local store of extracted bundles, plus the per-host selection under `state/`. | `localiser sync` |
| `THE-LINE/pipeline/bootstrap/<host>/` | Stable stubs the DCCs find through their environment variables. | You, by hand |
| `THE-LINE/pipeline/config.json` | Local machine config pointing at the remote and the bundle store. | You, by hand |
| `THE-LINE/pipeline/__init__.py` | Shared entry the stubs call: loads the prepared bundle and runs its entry point. | You, by hand |
| `run_host.py` | Launches a DCC with the environment variables the studio would set. | You run it |

`fake_remote_repository/hosts/`, `localiser/` and `bundles/` are gitignored and can be regenerated.

## Making a new bundle

![New bundle workflow](../docs/diagrams/new-bundle-workflow.svg)

Do not add to `fake_remote_repository`: it is generated, and the build script deletes anything placed there.

1. Create `structure/bundle_sources/<host>/<new version>/`. For Blender, copy the previous version as a starting point.
2. Run `python structure/build_test_workstation.py`. It publishes every version found in `bundle_sources`, including the new one, using the core's publisher. To publish just one bundle, anywhere, run `python -m localiser publish <source folder> <host> <version> --shared structure/shared_sources [--remote <repository>]`. Without `--remote` it publishes to `remote_repository` in the pipeline config.
3. In `fake_remote_repository/config.json`, set that host and series to `"bundle_version": "<new version>"`.
4. Sync, then restart the DCC:

   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python.exe -m localiser --pipeline structure\THE-LINE\pipeline sync blender 5.2
   ```

   Use `maya 2026` or `nuke 17.0` for the other hosts.

Without step 3, sync keeps resolving the old version: the new bundle is published but never selected.

Release IDs are immutable. If you change a version's contents after publishing it, rebuild and also delete its local copy first, otherwise sync keeps the old one:

- `THE-LINE/pipeline/bundles/hosts/<host>/<version>/`
- `THE-LINE/pipeline/bundles/state/manifests/<host>/<version>.json`

If you delete bundles from `bundles/` by hand, run sync again. The selection under `state/prepared/` remains, and DCC startup reports "prepared bundle is incomplete" until sync reinstalls it.

## What sync does

![Sync sequence: resolve, install, select](../docs/diagrams/sync-sequence.svg)

Version resolution prefers the override variable, then the studio `config.json` on the remote, then the last-known-good copy kept locally for offline use. An already-installed release is reused without touching the network or hashing the zip.

## Where the remote repository lives

`remote_repository` in the local `config.json` is either a folder (a share) or an `https://` address. The layout is the same either way and is addressed by relative path, so one base holds everything:

```
<remote_repository>/config.json                          the studio config
<remote_repository>/hosts/<host>/<release>/manifest.json
<remote_repository>/hosts/<host>/<release>/pipeline.zip
```

`"remote_repository": "https://pipeline.example.com/line"` therefore needs only static file hosting (Firebase Hosting, a bucket behind a CDN, any web server). To move from a share to the web, publish to the folder behind the address with `localiser publish --remote <folder>` and change one line in the local config.

Web addresses are read-only, plain `http` is accepted only for loopback testing, and credentials, queries and fragments in the address are rejected. A redirect is followed only to an address that passes the same rules, so a downgrade to plain `http` is refused. Text files are limited to 1 MB and every request times out after 15 seconds. Integrity is unchanged: the zip's sha256 comes from the manifest. Unreachable web addresses behave exactly like an unreachable share: `check` reports offline, and `sync` reuses the last-known-good config and any installed release.

Firebase Realtime Database serves one JSON tree rather than files, so it can't be the whole repository, and its keys can't contain `.` (our `5.2` and `17.0` series). It would only fit if the studio config were separate from the artifacts, which is not built.

## Running something other than the selected release

`sync` selects one release per host and series for the whole machine. Three tools run something else without touching that selection:

| Need | How |
|---|---|
| Install a release now, for later use | `python -m localiser pull <host> <release>`. It installs but does not select, and it is the only step that needs the remote. |
| Run an installed release for one session, such as a project | Set `TLS_PIPELINE_<HOST>_BUNDLE=<release>`, or `launch --bundle <release> <host> <series> <exe>`. Startup never downloads, so the release must have been pulled; otherwise it fails and says which `pull` to run. |
| Test an unpublished bundle source | Set `TLS_PIPELINE_<HOST>_SOURCE=<source folder>` and `TLS_PIPELINE_SHARED_SOURCES=<folder of shared packages>`, or `launch --source <dir> --shared <dir> ...`, or `python structure/run_host.py <host> --source <dir>`. |

Dev mode copies the source into a throwaway folder under `bundles/dev/<host>/`, laid out exactly as a published release would extract (same entry point, same shared packages), so what you test is what would ship. There is no zip, no checksum and no remote, so each restart picks up your edits. Copies older than three days are removed the next time one is made.

A session starts with the first of these that applies: the source folder, then the pin, then the release `sync` selected. A source or pin that can't be used is an error, never a quiet fallback. The pipeline entry prints `RUNNING UNPUBLISHED SOURCE` or `PINNED ... bundle` so a session can't pass for a normal one. Both variables apply to every series of their host, and both only ever come from the environment, never from shared configuration. Treat a source folder like any code you run: the variable decides what executes in the DCC.

`sync` honours the same pin variable, and `sync --bundle <release>` is the shortcut: it selects that release machine-wide instead of the studio default, which stays sticky until the next plain `sync`. Options go before the host, because everything after the series belongs to the DCC command.

## Shared code

Bundles are per host, so code every host needs lives in `shared_sources/<package>/`, and the core's publisher (`localiser.plan_bundle` / `python -m localiser publish --shared <folder>`) merges each package into every bundle before zipping: to the bundle root, or to `modules/` for Blender. A release therefore stays one self-contained, checksummed zip that works offline, and rolling back a bundle rolls back its shared code too. A bundle can't ship a package with the same name as a shared one.

The entry point puts that folder on `sys.path` (Maya's and Nuke's bundle root, Blender's `<bundle>/modules`) and then `from tls_common import MayaLogger` (or `BlenderLogger`, `NukeLogger`).

### Logging: `tls_common`

All loggers live under one stdlib logger, `tls`, which owns the handler and format and does not propagate, so nothing prints twice through a host's or AYON's own handlers. Each tool subclasses its host class:

```python
from tls_common import MayaLogger

class PlayblastLogger(MayaLogger):
    NAME = "playblast"          # logs as tls.maya.playblast

PlayblastLogger.info("Output path %s", path)
```

A host class overrides `make_handler()` if stdout isn't the right place. `get_logger("name")` returns a plain stdlib logger under `tls` for code that prefers one.

| Variable | Effect |
|---|---|
| `TLS_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or a number. Default `INFO`. |
| `TLS_LOG_FILE` | A file that also receives `INFO` and above. |

## Installing for a user

An installation is per user and needs no elevation. The pipeline root is `%LOCALAPPDATA%\TheLine\Pipeline` on Windows (`~/Library/Application Support/TheLine/Pipeline` on macOS, `$XDG_DATA_HOME/theline/pipeline` on Linux), and it holds `config.json`, `bootstrap/`, `localiser/` and `bundles/`. When `TLS_PIPELINE` isn't set, the stubs and the CLI use that location, so no environment variable is needed.

The local `config.json` adds optional keys to `remote_repository` and `bundle_repository`:

| Key | Meaning |
|---|---|
| `hosts` | The hosts and series the user supports, for example `{"maya": ["2026"], "nuke": ["17.0"]}`. Empty or absent enables everything. Once listed, a DCC version that isn't listed (Maya 2025, Blender 4.5) loads nothing and says so. An explicit pin or source always loads. |
| `check_interval_minutes` | How often the tray app checks (5 to 10080, default 240). |
| `auto_sync` | Whether the tray app applies updates itself (default true). |

Commands for the installer and the tray app:

| Command | What it does |
|---|---|
| `python -m localiser hosts` | The supported hosts, the versions installed here (from the standard install folders) and which are enabled. |
| `python -m localiser check-all` | Check every enabled host and series. Exit 0 current, 1 updates available, 2 a problem. Installs nothing. |
| `python -m localiser sync-all` | Sync every enabled host and series. One failing never stops the others; exit 2 if any failed. A series the studio config has no release for is reported as `unsupported`, not as a failure. |
| `python -m localiser provision [--remove]` | Install, or remove, the entry each enabled DCC finds at startup. |

`check-all` and `sync-all` record their result in `bundles/state/status.json`, which the tray app and the hosts read with no network access. `localiser.selection_changed(host, series, loaded_release_id, config)` lets a running DCC ask, from local state only, whether a newer release has been selected since it started.

### How each DCC finds the stub

Each DCC already reads a fixed per-user place at startup, so `provision` puts a small entry there. All three point at `<root>/bootstrap/<host>`, so a stub update needs no change to them, and none touches a global environment variable such as `PYTHONPATH`:

| Host | Entry | Verified |
|---|---|---|
| Maya | `<Documents>/maya/modules/TheLinePipeline.mod` (`+ TheLinePipeline 1.0 <stub folder>` and `PYTHONPATH +:= .`). Maya scans that folder by default. | Maya 2026, Windows |
| Nuke | a marked block in `~/.nuke/init.py` that calls `nuke.pluginAddPath` on the stub folder. The rest of the file is never touched, and `--remove` restores it. | Nuke 17.0v3, through a plugin-path folder |
| Blender | `<user scripts>/startup/tls_pipeline_startup.py`, a forwarder that loads the stub, under `%APPDATA%\Blender Foundation\Blender\<series>\scripts` | Blender 5.2, Windows |

Entries are idempotent. A file that isn't marked as ours is never overwritten or removed. `MAYA_APP_DIR` and `BLENDER_USER_SCRIPTS` are honoured where Maya and Blender honour them. The environment variables in the table below remain as overrides for a launcher such as AYON; the default entries don't need them.

### Updates reach users outside the DCC

A running DCC never polls for updates or interrupts the user. A session keeps the release it started with, and a newly selected release takes effect the next time the DCC starts. The tray app reports the result and applies updates (below). An in-DCC notice was tried (a timer in each host) and removed: on Maya 2026 it could not be shown to be safe during startup, and the stability risk outweighed the benefit.

### The tray app

`python -m localiser_tray` (`pip install .[tray]` for PySide6; add `--show` to open the window at start). It lives in `src/localiser_tray/` and only calls the core. The tray icon is coloured by the worst state (grey nothing enabled, green current, amber updates waiting, red a problem), with a menu: Open pipeline manager, Check for updates, Update now, Settings, Quit. Closing the window hides it; Quit exits.

To try it without touching your profile, `python structure/run_tray.py` runs it against a scratch root in `%TEMP%\tls_tray_test` (its own config pointing at the fake remote repository, its own bundle store, and the Maya, Nuke and Blender entries redirected there). `--enable maya:2026 nuke:17.0` pre-enables hosts, `--reset` starts clean and `--use-real-profile` removes the isolation.

- **When it checks.** At start, then whenever the last check recorded in `status.json` is older than `check_interval_minutes`; the app looks once a minute, which only reads that file. Checks run off the UI thread. With `auto_sync` on, anything newer is installed and selected in the same pass, and a tray notification says which application to restart. With it off, the update is reported once per set of updates and "Update now" applies it.
- **Status tab.** One row per enabled application and version: the release installed (what the next launch will load), the studio release and a sentence for the state. A failed or unreachable repository keeps what is installed.
- **Settings tab.** Tick the installed versions of each application (found in the standard install folders; versions enabled but not found are kept and marked), the pipeline repository (a shared folder or an https address), the local releases folder, the interval and `auto_sync`. Save is one validated write to `config.json` (`localiser.apply_hosts`): nothing changes if any value is rejected. It then installs and removes the per-application entries (`provision`) for what was switched on or off, and runs an update. On a first run with no `config.json`, the app opens on Settings and Save creates it.
- **One copy.** A lock file in the temp folder stops a second tray icon from a second launch.
- **Not in the app yet.** Putting the stubs and core into the pipeline root (the app warns when `<root>/bootstrap` is missing), starting at login, and cleaning up old releases.

## Bundle layout

The bundle's entry point is `<python_root>/__init__.py`. The publisher uses `python_root` `startup` and shared destination `modules` for Blender, and `.` for both for other hosts. A `bundle.json` at the root of a source folder overrides them (`{"schema_version": 1, "python_root": "...", "shared_destination": "..."}`); it is publishing metadata and isn't shipped in the zip.

A Blender bundle may contain, all optional apart from `startup/`:

| Folder | What the Blender stub does with it |
|---|---|
| `startup/` | The bundle entry point, run during startup. |
| `splash/splash.png` | Sets `BLENDER_CUSTOM_SPLASH` to this file. |
| `extensions/<id>/` | Local extension repository `tls_pipeline`. Each folder needs a `blender_manifest.toml` and must be named after its `id`. |
| `addons/<name>/` | Legacy add-ons (`bl_info`). Keep extensions out of this folder, or Blender lists them twice. |
| `modules/`, `presets/` | Available through the `THELINE_PIPELINE` script directory, which points at the bundle root. |

Everything in `extensions/` and `addons/` is enabled and recorded in the user's preferences. Each launch rewrites the script-directory and repository paths and drops `tls_pipeline` extensions the release no longer ships.

A Maya bundle's root `__init__.py` is its entry point (`python_root` is `.`), and it does two things at startup:

- **Paths:** it appends the bundle root and each top-level directory to `sys.path`, last so nothing already on the path is shadowed. `import playblast_plus` and `import LineTools` work, and so does `from anim.PublishPlusCreator import ui`.
- **Menu:** `LineTools/menu.py` builds a **THE LINE** menu by scanning the folders in `LineTools/` on every Maya start, so a new script or folder appears with no menu definition to maintain. Scripts in `_`-prefixed folders (`_global`, `_scene`) are listed at the top level, every other folder becomes a submenu, and empty folders are skipped. Each script runs as `__main__`, so keep its code under `if __name__ == "__main__":`. There is no menu in batch or `mayapy` sessions.
- **Missing tools:** a script that needs a module the bundle doesn't ship (one AYON provides, say) declares it at the top, for example `REQUIRES = {"dwpicker": "comes from the AYON tool descriptor"}`, or a plain list of names. The runner checks before running, logs one warning line without a traceback, and shows the same text as a viewport message. The menu tooltip lists what the script needs. An undeclared missing import gets the same treatment.

A Nuke bundle's root `__init__.py` adds `core/` with `nuke.pluginAddPath`, so Nuke runs `core/init.py` once the stub returns and `core/menu.py` when the UI loads. Everything is derived from where `core/` sits, so nothing depends on `NUKE_PATH`, which stays the studio's. `core/init.py` exports `TLA_COMP_CORE` (the core folder), `TLA_COMP_PIPELINE_ROOT` and `TLA_COMP_TOOLCHAINS`, and `toolchains/<name>/` holds one copy of each tool with no version folders. The release id is the version shown in the banner. Runtime logs go to `bundles/logs` (set as `TLS_LOG_DIR` by the entry), never into a release. `core/utils/PipelineLogger.py` keeps its API but sits on `tls_common`: every pipeline logger is `tls.nuke.<name>`, the console and daily `pipeline_<date>.log` handlers live on the `tls` logger, and Nuke's and AYON's root logger is left alone.

## Environment variables

Every host also has an **About** item that shows the release, where it came from (studio default, pinned or unpublished source) and the bundle path: Nuke under Help (`bootstrap/nuke/menu.py`), Blender under Help (the stub; only when a bundle is loaded) and Maya as the last item of the THE LINE menu (`LineTools/menu.py`, so it ships with the Maya bundle). The text comes from `pipeline/about.py`, which reads the variables below, so a host needs no other access to the pipeline.

| Variable | Set by | Value |
|---|---|---|
| `TLS_PIPELINE` | you / installer | the pipeline root (`structure/THE-LINE/pipeline`) |
| `PYTHONPATH` (Maya), `NUKE_PATH`, `BLENDER_SYSTEM_SCRIPTS` | you / installer / `run_host.py` | `<root>/bootstrap/<host>` |
| `TLS_PIPELINE_MAYA` / `_NUKE` / `_BLENDER` | the localiser | the resolved bundle path |
| `TLS_PIPELINE_<HOST>_RELEASE`, `TLS_PIPELINE_<HOST>_MODE` | the localiser | what this session is running: the release id (`1.1.0`, or `dev-<name>`) and `studio` (following the studio config), `pinned` or `dev`. Identity only: set at startup for anything in the DCC to read (a Nuke label `[getenv TLS_PIPELINE_NUKE_RELEASE]`, MEL `getenv`), never read back by the core. Different from the `_BUNDLE` and `_SOURCE` inputs below. |
| `TLS_PIPELINE_<HOST>_BUNDLE` | you / AYON hook | pin this session to an installed release (also what `sync` selects) |
| `TLS_PIPELINE_<HOST>_SOURCE` | you | run an unpublished bundle source folder (dev mode) |
| `TLS_PIPELINE_SHARED_SOURCES` | you | folders of shared packages to merge into a dev source (`;`-separated on Windows) |
| `BLENDER_CUSTOM_SPLASH` | the Blender stub | the bundle's `splash/splash.png`, when present |
