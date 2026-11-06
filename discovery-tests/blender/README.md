# Blender discovery test — G1 / B1 / B2

Question: if a `startup/` script (loaded via `BLENDER_SYSTEM_SCRIPTS`) adds/refreshes a
script-directory entry, adds `modules/` to `sys.path`, and asks `addon_utils` to enable an
add-on — does any of that get picked up **in the same session**, or does it really require a
restart as the 5.0 manual implies for preference-based changes?

## What's here

```text
blender/
  system_scripts/
    startup/
      tls_discovery_startup.py   <- loaded automatically by Blender at startup
  fake_release_v1/
    addons/tls_discovery_addon.py
    modules/tls_discovery_module.py
    presets/tls_discovery_presets/placeholder.txt
  fake_release_v2/
    addons/tls_discovery_addon.py   <- same module name, different version marker, for B2
    modules/tls_discovery_module.py <- v2 module marker
```

`tls_discovery_startup.py`:
1. Logs the environment (`BLENDER_SYSTEM_SCRIPTS`, current `bpy.utils.script_paths()`) — B1.
2. During startup `register()`, before Blender loads saved enabled add-ons: adds or refreshes
   a named script-directory entry (`TLS_DISCOVERY_TEST`) pointing at the fake release, adds
   `modules/` to `sys.path` directly, and calls `bpy.utils.refresh_script_paths()` to update
   Python's import paths.
3. ~0.5s after startup (via `bpy.app.timers`, once Blender has finished initialising): calls
   `bpy.ops.preferences.addon_refresh()` and asks
   `addon_utils.enable()` to enable the fake add-on by module name.
4. ~4s after startup: re-checks (without touching anything) whether the explicitly enabled
   add-on remains loaded. This is not a test of passive discovery.

The startup module uses Blender's `register()` / `unregister()` lifecycle to schedule and
remove its timers.

## Deploy

1. Set `BLENDER_SYSTEM_SCRIPTS` to the absolute path of `system_scripts/` (the folder that
   *contains* `startup/`, not `startup/` itself).
2. Optionally set `TLS_DISCOVERY_FAKE_RELEASE` to an absolute path (defaults to the sibling
   `fake_release_v1/`).
3. Launch Blender 5.0+ **vanilla** (no `--python` argument) and let it fully start up. Repeat via
   your AYON launch if relevant.
4. Inspect the log, and also check **Edit → Preferences → File Paths → Script Directories** and
   **Edit → Preferences → Add-ons** by eye for `TLS_DISCOVERY_TEST` / "TLS Discovery Test Addon".

### B1: AYON and `BLENDER_SYSTEM_SCRIPTS`

Result: AYON does not set `BLENDER_SYSTEM_SCRIPTS` (user-reported), so the install script does
not need to merge with an AYON-provided value. It should still append to any existing value, and
inheritance by AYON-launched Blender is still to be confirmed. The original check follows.

Before setting it yourself, check whether AYON's Blender integration already sets
`BLENDER_SYSTEM_SCRIPTS` in the launch environment (e.g. log it from a shell, or check the
`EVENT=startup_begin BLENDER_SYSTEM_SCRIPTS=...` log line on an AYON launch with *only* AYON's
own environment, before you add this stub's path). If AYON already sets it, decide whether the
install script needs to append/merge rather than overwrite.

### B2: stale-path re-point test

1. Run once with `TLS_DISCOVERY_FAKE_RELEASE` pointing at `fake_release_v1/`. Confirm in the log
   (`EVENT=addon_enable_attempt` / `fake_addon_register_v1`) and in Preferences that the v1
   add-on is the one found.
   Save Preferences before quitting so the script-directory entry and enabled state persist.
2. Quit Blender. Re-launch with `TLS_DISCOVERY_FAKE_RELEASE` pointing at `fake_release_v2/`
   instead (same `BLENDER_SYSTEM_SCRIPTS`).
3. Check the log for `EVENT=script_directory_refreshed old=<v1 path> new=<v2 path>` (not
   `script_directory_created` a second time — that would mean a duplicate entry instead of an
   update) and confirm `fake_addon_register_v2` fires instead of `v1`. The module marker should
   also be `tls_discovery_module_v2_loaded`, and `addon_check source_file` must point into v2.

## Reading the result (G1)

- `EVENT=addon_enable_attempt phase=timer_phase_1 result=<Module object>` (not `None`) plus
  `EVENT=fake_addon_register_v1` (or `_v2`) appearing shortly after means the add-on was
  successfully enabled in-session via `addon_utils.enable()` once the script directory was
  registered — a strong "yes, in-session pickup works via this mechanism" result.
- If `addon_enable_attempt` logs `result=None` in `timer_phase_1` and
  `timer_phase_2_recheck` never shows `loaded_state=True`, this attempt failed. Inspect refresh
  errors and paths before concluding that a restart is required.
- `EVENT=modules_sys_path_import_ok` confirms the plain `sys.path` route for `modules/` always
  works regardless of the above (it doesn't depend on Blender's own add-on discovery).

### Blender 5.2 observation

Adding the preference entry and calling only `bpy.ops.preferences.addon_refresh()` made the
release visible in `bpy.utils.script_paths()`, but left its `addons/` directory out of
`sys.path`. Enabling then returned `None` with `No module named 'tls_discovery_addon'`.
The refresh operator scans add-on metadata; it does not refresh Python's import paths.
Calling `bpy.utils.refresh_script_paths()` after setting the preference entry allowed the
v1 add-on to enable in the same process. Its preset directory was also returned by
`bpy.utils.preset_paths("tls_discovery_presets")`. This was reproduced in a factory-startup
background run and confirmed in a normal UI launch.

The original timer-only re-point test failed B2: Blender auto-enabled the saved v1 add-on
before the timer changed the preference to v2. Calling `enable()` again reused the imported
v1 module, despite `script_paths()` showing v2. A true `loaded_state` alone cannot prove
the selected release loaded. Release selection and import-path refresh now happen during
startup `register()`, before Blender's saved add-ons load; the timer only refreshes metadata
and enables the add-on. This avoids loading the wrong release rather than attempting an
unsafe live replacement of already-running pipeline code.

The original v2 fixture also lacked a `modules/` marker, allowing the v1 module left on the
startup import path to satisfy the module test. Both releases now provide distinct markers,
and the probe logs module and add-on source filenames.

## Verified outcome and implications for future stages

Verified on Windows with Blender 5.2:

- **G1 passed:** a release added during startup can provide an importable module and an
  enabled add-on in the same Blender session. A background check also confirmed preset
  discovery through `bpy.utils.preset_paths("tls_discovery_presets")`.
- **B2 passed:** the normal UI launch at 2026-11-02 17:06:28 changed the persisted directory
  from v2 to v1 before add-ons loaded. Both module and add-on source filenames pointed at v1,
  no v2 registration occurred, and v1 remained enabled at the delayed recheck.
- A separate isolated-preferences background test confirmed the v1-to-v2 direction.
- **B1 remains open:** these runs do not establish whether AYON already owns or sets
  `BLENDER_SYSTEM_SCRIPTS`.

This establishes a route to pipeline deployment **without per-release add-on installation**.
There is still a one-time bootstrap deployment: provision a stable local startup stub and
localiser, and configure `BLENDER_SYSTEM_SCRIPTS` to point at the stub's scripts directory.
The bootstrap must live outside versioned releases to avoid circular startup dependencies.

On each launch, the stub can synchronously ask the future localiser to resolve and sync the
selected build, expose the completed local scripts root, and let Blender load saved enabled
add-ons from it. Updates and rollbacks select a different build for the **next launch**; they
do not hot-swap code inside an already-running Blender process. The selected release path
does not have to be known before process creation, provided setup completes during startup
`register()`, before Blender loads saved add-ons.

### Illustrative stable startup stub

This is a future integration sketch, not an implemented localiser API or production-ready
failure policy. The localiser owns selection, syncing, verification, locking, caching and
offline behaviour; the Blender adapter only exposes its result.

```text
bootstrap/
  blender/                         <- BLENDER_SYSTEM_SCRIPTS points here
    startup/
      tls_pipeline_startup.py
    modules/
      tls_localiser/
        ...
```

Blender makes the stable scripts directory's `modules/` importable. The proposed startup
module would look like:

```python
import logging
from pathlib import Path

import bpy

# Illustrative future API; not implemented yet.
from tls_localiser import ensure_local_release

ENTRY_NAME = "THELINE_PIPELINE"
logger = logging.getLogger(__name__)


def register():
    try:
        # Return the completed local Blender scripts root, accounting for python_root.
        scripts_root = Path(ensure_local_release(host="blender"))
        if not scripts_root.is_absolute() or not scripts_root.is_dir():
            raise RuntimeError(
                f"Invalid local Blender scripts root: {scripts_root}"
            )

        entries = bpy.context.preferences.filepaths.script_directories
        entry = next(
            (item for item in entries if item.name == ENTRY_NAME),
            None,
        )
        if entry is None:
            entry = entries.new()
            entry.name = ENTRY_NAME

        entry.directory = str(scripts_root)
        bpy.utils.refresh_script_paths()
        logger.info("Blender pipeline ready: %s", scripts_root)
    except Exception:
        logger.exception("Blender pipeline bootstrap failed")
        raise


def unregister():
    pass
```

The returned root contains the release's `addons/`, `modules/` and `presets/` as applicable.
Path setup must remain synchronous in `register()`, not deferred to a timer. Updating the
existing named entry avoids adding another entry on every launch. The stub does not need
to save preferences merely to expose the selected release for the current session.

Saved enabled add-ons load through Blender's normal startup machinery. First-time activation
of pipeline add-ons is a separate explicit requirement. The discovery probe's timer and
unconditional `addon_utils.enable()` are instrumentation, not a production requirement:
enabling an already-loaded add-on caused the observed unregister/register pair.

### Production requirements still to resolve

- **Failure policy:** Blender catches startup registration exceptions and may continue
  launching. Logging and raising alone does not stop saved stale pipeline add-ons loading.
  Define how to prevent unintended stale-code execution, and when an explicitly approved
  last-known-good release is allowed.
- **Complete releases only:** the localiser must finish syncing and verification before
  exposing a release. Coordinate concurrent launches and never expose partial downloads.
- **Bootstrap trust and maintenance:** protect the stable bootstrap separately from the
  mutable release cache, and define how bootstrap updates are deployed.
- **Dependencies:** PySide6 and other external/native dependencies need their own deployment
  and compatibility strategy; these tests cover pipeline scripts, not dependency installation.
- **Launch integration:** reconcile AYON's environment and other startup code rather than
  blindly overwriting its settings. Ensure newly launched processes inherit the environment.
- **Support matrix:** repeat the tests on every supported Blender version and platform.
  These results establish Windows/Blender 5.2 behaviour, not universal compatibility.
