# Pipeline Localiser: Planning Blueprint

Planning and R&D for THE LINE's lightweight, host-aware pipeline localiser. A dedicated sync command resolves, copies and verifies immutable bundles before Maya, Blender or Nuke starts. Host startup only loads the prepared local selection.

**Status: R&D complete for host exposure on Windows (Blender 5.2, Maya 2026, Nuke 17.0v3). The stdlib-only core and publisher are implemented and tested, and a test workstation in [`structure/`](structure) localises real bundles and exposes them in all three hosts (Blender add-ons and splash, the Maya menu and paths, the Nuke core and toolchains). The core side of a per-user installation is built too: enabled hosts, `sync-all`/`check-all`, per-host entries that need no environment variables, the pin and dev mode, and the tray app (status, settings, background check and sync). Not yet built: packaging and login start-up, and cleanup of old releases.** The original eight planning documents have been consolidated into:

| Document | Contents |
|---|---|
| [Design brief](.copilot/01_design_brief.md) | Scope, architecture, manifests, runtime flow, host research, trust model, testing strategy and phased implementation plan. |
| [Open decisions and risks](.copilot/02_open_decisions.md) | Confirmed decisions, unresolved questions and deployment/host validation gates. Recommendations are not decisions. |
| [User discovery worksheet](.copilot/03_user_discovery.md) | Host-level verification tasks with blanks to fill in once tested on real workstations/DCCs. |

[`discovery-tests/`](discovery-tests) contains throwaway, stdlib-only stubs to deploy into real Maya/Nuke/Blender installs to produce the evidence the worksheet asks for (not localiser code).

The [platform and installer assessment](.copilot/01_design_brief.md#51-rd-assessment-platform-locations-and-lightweight-installation) compares Windows, macOS and Linux user/system directories and recommends a **shared workstation-local store**, not separate pipelines per user. A lightweight installer would provision protected bootstrap/configuration, writable data directories for an approved studio group, and stable host discovery. Unrestricted public write access is not recommended for executable pipeline code.

A TD's override during explicit sync selects a bundle in that shared store and pulls it if missing; it does not change the studio default or other running sessions. DCC startup does not resolve overrides or pull bundles. Explicit repair of an already-cached bundle is separate. Exact permissions, installer details and supported OSes remain subject to review.

## Code and tests

- [`src/localiser/`](src/localiser): the core (config/manifest parsing, resolution, staged verify-and-extract install, locking, publisher). Stdlib-only, no DCC imports. `python -m localiser publish <source> <host> <version> --shared <folder>` publishes a bundle source (shared packages merged in, entry point from host defaults or `bundle.json`) as an immutable release; see [`structure/DATA.md`](structure/DATA.md). `sync_release(host, series, config)` installs and atomically selects a complete bundle; `load_prepared_release(host, series)` is the local-only host entry point. The lower-level `localise` / `ensure_local_release` installation APIs remain available for explicit preparation, not DCC startup. `expose_environment` sets `TLS_PIPELINE_<HOST>` to the bundle path. `TLS_PIPELINE` names the pipeline root holding `config.json`.
- [`src/localiser_tray/`](src/localiser_tray): the tray app, `python -m localiser_tray` (`pip install .[tray]` adds PySide6; the core never imports it). It checks for updates at start and then on the configured interval, installs them when `auto_sync` is on, and has a window for status and settings (applications, repository, local folder, interval). All decisions live in `model.py`, which has no Qt in it; the app only calls the core. See [`structure/DATA.md`](structure/DATA.md).
- [`tests/`](tests): unit tests using temp dirs and synthetic zips; no share access needed. The tray GUI tests run offscreen and are skipped when PySide6 isn't installed.

```powershell
python -m unittest discover -s tests -t .
```

Passes on Python 3.11 (Maya 2026's `mayapy`; Nuke 17.0v3's bundled `python.exe`, 3.11.11), 3.13 (Blender 5.2) and 3.14. The supported floor is 3.11.

## Dedicated sync and launch

With the package installed (or `src` on `PYTHONPATH`), run synchronization independently of the DCC, for example at login or the day before use:

```powershell
python -m localiser --pipeline "C:\THE-LINE\pipeline" sync maya 2026
python -m localiser --pipeline "C:\THE-LINE\pipeline" check maya 2026
python -m localiser --pipeline "C:\THE-LINE\pipeline" launch maya 2026 "C:\Program Files\Autodesk\Maya2026\bin\maya.exe"
```

Omit `--pipeline` when `TLS_PIPELINE` is already set. `remote_repository` in the pipeline's `config.json` is a share folder or an `https://` address with the same layout (see [`structure/DATA.md`](structure/DATA.md)). Repeat sync for each required host/series, e.g. `blender 5.2` and `nuke 17.0`. A scheduler can periodically run `check` or `sync`; no background service or DCC-time download is required. `check` returns **0** when current, **1** when a sync is needed, and **2** on error (including an offline update check). It may refresh the cached studio config, but never downloads or activates a bundle. `sync` returns **0** on success and **2** on failure; offline sync can reuse cached configuration and complete bundles.

Selections are stored separately per host and DCC series under `state/prepared/`, and change atomically only after successful installation. Failed updates leave the previous selection usable. Releases are immutable and older releases are retained: running DCCs keep their existing code; **restart the DCC after sync to use an update**. Startup reads only the local selection and completion marker, with no network access, extraction or repair. A missing/incomplete selection reports that sync is required; the host stubs allow the DCC to continue without pipeline code.

To run something other than the selection without changing it: `python -m localiser pull <host> <release>` installs a release without selecting it, and `TLS_PIPELINE_<HOST>_BUNDLE=<release>` (or `launch --bundle`) pins one session to it. `TLS_PIPELINE_<HOST>_SOURCE=<folder>` (or `launch --source`) runs an unpublished bundle source for testing. See [`structure/DATA.md`](structure/DATA.md).

`launch` never syncs. It sets `TLS_PIPELINE_<HOST>` and the host's bootstrap discovery variable in the child process, preserving existing Maya/Nuke search paths, and returns the child exit code. A sync process cannot alter its parent shell or an already-running DCC's environment. For launches outside this command, the installer must provide `TLS_PIPELINE` and the bootstrap discovery variable; the host stub then exposes the prepared bundle locally. The native OS installer/provisioning remains a separate deployment task.

## Test workstation

[`structure/`](structure) is a working prototype of the blueprint: a pipeline root (`THE-LINE/pipeline`) with a shared entry, per-host bootstrap stubs, a fake remote repository and fake bundle sources. Hosts find their stub through their own variable; the stub detects the DCC version, loads the prepared local selection, and runs the bundle's `__init__.py`.

| Variable | Set by | Value |
|---|---|---|
| `TLS_PIPELINE` | you / installer | the pipeline root |
| `PYTHONPATH` (Maya), `NUKE_PATH`, `BLENDER_SYSTEM_SCRIPTS` | you / installer | `<root>/bootstrap/<host>` |
| `TLS_PIPELINE_MAYA` / `_NUKE` / `_BLENDER` | the localiser | the resolved bundle path |

```powershell
python structure\build_test_workstation.py   # copy the core in; publish fake bundles to the fake remote
python -m localiser --pipeline structure\THE-LINE\pipeline sync maya 2026
python -m localiser --pipeline structure\THE-LINE\pipeline sync blender 5.2
python -m localiser --pipeline structure\THE-LINE\pipeline sync nuke 17.0
python structure\run_host.py maya            # or nuke / blender; add --gui for the full application
```

[`structure/DATA.md`](structure/DATA.md) explains which script writes which folder and how to make a new bundle. `run_host.py` prints the variables it sets. Old discovery stubs left in a DCC's user folders or preferences will also run and add noise (check `BLENDER_SYSTEM_SCRIPTS` isn't still set machine-wide to a `discovery-tests` folder).

**Blender bundle contents.** The Blender stub exposes whatever the bundle ships (`bundle_sources/blender/1.0.1` is a real-world example): `splash/splash.png` is set as `BLENDER_CUSTOM_SPLASH`; the bundle root is registered as the `THELINE_PIPELINE` script directory; `extensions/<id>/` folders (with a `blender_manifest.toml`, named after its `id`) load from a local `tls_pipeline` extension repository; and `addons/` holds legacy `bl_info` add-ons. Keep extensions out of `addons/`, or Blender lists them twice. Everything shipped is enabled and recorded in the user's preferences, because add-ons read their settings through `context.preferences.addons[...]`. Each launch rewrites the script-directory and repository paths and drops `tls_pipeline` extensions the release no longer ships, before Blender loads saved add-ons. Add-ons are enabled on the first `load_post`, because Blender only creates the extension namespace after startup scripts have run.

## Scope and research

V1 covers a stdlib-only core, publisher, lightweight installer, native-host stubs, per-DCC release selection and offline reuse of cached bundles. AYON integration, project overrides and manifest signing are deferred; future AYON integration must call the same core.

[`reference/`](reference/) contains existing pipeline code used for lifecycle research, not a localiser implementation. Key findings are in the design brief's host sections (see §8.4 for the discovery results): Nuke needs location-independent root resolution, Maya can run more than one `userSetup.py`, and Blender exposes a release in-session when set up during startup registration, before saved add-ons load.

Review the brief and open decisions before changing host settings or adding host stubs. Verify platform permissions and host behaviour on the supported workstation images rather than assuming the proposed mechanisms work.
