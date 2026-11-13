# Pipeline Localiser: Planning Blueprint

Planning and R&D for THE LINE's lightweight, host-aware pipeline localiser. A dedicated sync command resolves, copies and verifies immutable bundles before Maya, Blender or Nuke starts. Host startup only loads the prepared local selection.

**Status: R&D complete for host exposure on Windows (Blender 5.2, Maya 2026, Nuke 17.0v3). The stdlib-only core and publisher are implemented and tested, and a test workstation in [`structure/`](structure) localises real bundles and exposes them in all three hosts (Blender add-ons and splash, the Maya menu and paths, the Nuke core and toolchains). The core side of a per-user installation is built too: enabled hosts, `sync-all`/`check-all`, per-host entries that need no environment variables, the pin and dev mode, and the tray app (status, settings, background check and sync). An experimental per-user Windows installer is now buildable; clean-system validation and cleanup of old releases remain.** The original eight planning documents have been consolidated into:

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
- [`src/localiser_tray/`](src/localiser_tray): the tray app, `python -m localiser_tray` (`pip install .[tray]` adds PySide6; the core never imports it). It checks for updates at start and then on the configured interval, installs them when `auto_sync` is on, and has a launcher window and a manager window (status with overrides, a Create tab to make local bundles or publish a new studio release, an admin mode (Shift on Settings...) to choose the studio release of each version, settings; applications, repository, local folder, interval). All decisions live in `model.py`, which has no Qt in it; the app only calls the core. See [`structure/DATA.md`](structure/DATA.md).
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

To run something other than the selection without changing it: `python -m localiser pull <host> <release>` installs a release without selecting it, and `TLS_PIPELINE_<HOST>_BUNDLE=<release>` (or `launch --bundle`) pins one session to it. `TLS_PIPELINE_<HOST>_SOURCE=<folder>` (or `launch --source`) runs an unpublished bundle source in place, without copying it. See [`structure/DATA.md`](structure/DATA.md).

`launch` never syncs. It sets `TLS_PIPELINE_<HOST>` and the host's bootstrap discovery variable in the child process, preserving existing Maya/Nuke search paths, and returns the child exit code. A sync process cannot alter its parent shell or an already-running DCC's environment. For DCCs started outside this command, a separate per-user or studio deployment must provide `TLS_PIPELINE` and the bootstrap discovery variable; the host stub then exposes the prepared bundle locally. The Windows user installer packages the tray app and bootstrap payload; it does not provision DCC startup hooks.

### Harmony's external Python

Harmony is the only registered host with an external `python_version` requirement in `src/localiser/hosts.py`: 64-bit Python 3.9. Its internal console requires that version, not the tray app's Python or another DCC's bundled Python. See [Harmony 24's Python documentation](https://docs.toonboom.com/help/harmony-24/premium/go/scripting/python/index.html).

On Windows, the launcher discovers Python 3.9 from PythonCore's per-user/machine registry entries, standard Python installation folders, or `PATH`. It validates the interpreter's version and architecture and requires `python39.dll` beside `python.exe`. An explicit local override takes precedence; add this key to the pipeline root's existing `config.json` for a custom installation:

```json
"python_homes": {
    "harmony": "C:\\Python39"
}
```

Without that override, an inherited `PYTHON_LIB_PATH` is honored and validated before automatic discovery. An invalid explicit path or a missing compatible runtime stops the launch with an actionable error. The runtime must already be installed; it is not installed or downloaded by the launcher.

Only Harmony's child environment gets `PYTHON_LIB_PATH` and its Python folder prepended to `PATH`; existing `PYTHONPATH` is retained. Nothing is written to the Windows environment or Harmony preferences, and Maya, Blender and Nuke retain their bundled runtimes. This enables Harmony's Python console; it does not make the localiser's Python 3.11+ core compatible with Harmony's Python 3.9 interpreter.

## Windows user installer

The experimental installer targets 64-bit Windows and installs per user under `%LOCALAPPDATA%\Programs\TheLinePipeline`. It includes the Python runtime, the tray application, PySide6/Qt, and the host bootstrap payload. It also includes the Python, PySide6/Qt and PyInstaller license notices supplied by the build dependencies. Bundle sources and releases are deliberately excluded. On first install, when no local config exists, it writes `%LOCALAPPDATA%\TheLine\pipeline\config.json` with repository `P:\pipeline\repository` and bundle downloads under `%LOCALAPPDATA%\TheLine\pipeline\bundles`, beside the pipeline code. `TLS_PIPELINE`, if set, overrides the config/code root and first-install bundle downloads default to its `bundles` subfolder. Existing config files are never overwritten, so reinstalling retains a previously chosen bundle location. The repository and download location can be changed in the app. The installer's optional sign-in task starts the tray app for the current user. Uninstall leaves the user's pipeline configuration and downloaded bundles intact.

Build on Windows with Python 3.11 or newer and Inno Setup 6:

```powershell
.\packaging\windows\build.ps1
```

The script installs the tray and packaging build dependencies into the selected Python environment, creates a PyInstaller one-folder application, runs its packaged Qt/payload smoke test, and compiles `dist\installer\TheLinePipeline-Setup-<version>-x64.exe`. Before compiling, an isolated Python also installs the packaged payload into a temporary pipeline root and initializes synthetic prepared Maya, Blender and Nuke bundles offline. The core is shipped as ordinary `.py` files as well as frozen app modules: the DCCs use their own Python runtimes and cannot import the app's frozen archive. It uses `.venv\Scripts\python.exe` when available; pass `-PythonExecutable` to select another Python. Run the resulting installer on a clean Windows account/VM to validate install, first-run repository setup, tray startup, host launch, and uninstall.

Launch DCCs through the tray's Launcher; it supplies bootstrap discovery paths to that process only. The installer does not configure startup hooks for launches from desktop shortcuts or other launchers. The tray launcher deliberately hides console windows and sends stdout/stderr to the null device, so printed startup errors may not be visible in Blender. For diagnosis, launch Blender from a terminal with `TLS_PIPELINE` set to the pipeline root and `BLENDER_SYSTEM_SCRIPTS` to its `bootstrap\blender` folder.

Installer 0.1.1 fixes missing DCC core source files in 0.1.0. Quit the tray, install the update, then start the tray again to repair the pipeline root before restarting the DCCs. Configuration and existing bundles are retained; they do not need to be downloaded again.

Installer 0.1.2 includes Blender bundle asset libraries: immediate `assets/TLP_*` folders are registered with Link imports and absolute paths, and stale pipeline entries are removed without changing other user libraries. Quit the tray before upgrading, then start it again and relaunch Blender to load the updated startup stub. This updates the application and bootstrap code, not bundle contents; bundle entry-point dependencies such as `modules/tls_common` must still be included in the bundle.

Installer 0.1.3 introduced first-install configuration, originally with bundle storage under Documents, and uses lowercase `pipeline` in the Windows config/code root. Windows still resolves existing uppercase `Pipeline` folders; upgrades do not rename them or move existing bundles.

Installer 0.1.4 forces a consistent dark UI. Click the tray icon for the launcher, or Shift-click it for normal Settings. "Applications to keep up to date" is available in normal Settings again. Shift-click **Settings...** in the tray menu for admin mode; the Create tab remains admin-only.

Installer 0.1.5 reads the live keyboard state for Shift-clicking the tray icon, including when the app is unfocused. Settings now shows a selectable application version matching the running installer's release, for troubleshooting.

Installer 0.1.6 changes first-install bundle storage to `%LOCALAPPDATA%\TheLine\pipeline\bundles`. Existing configurations and bundles are retained, not moved. See [AYON launch examples](structure/DATA.md#ayon-launch-examples) for the application-specific discovery variables and optional installed-release pins; published bundles do not need a separate shared-source path.

Installer 0.1.7 adds self-contained Nuke plugins under `plugins/<tool>/`, alongside the existing configured toolchains. Create and Publish show the selected host's icon and larger action buttons. Flat folder shortcuts open the repository and local releases from the existing Settings fields, and the development folder from Create/Publish without adding another setting. Quit the tray before upgrading, then start it again to refresh the Nuke bootstrap.

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
