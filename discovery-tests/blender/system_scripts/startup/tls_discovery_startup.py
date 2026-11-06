"""Discovery test startup script for Blender BLENDER_SYSTEM_SCRIPTS in-session script-directory
pickup (see .copilot/03_user_discovery.md G1 / B1 / B2). THROWAWAY TEST CODE — not part of the
localiser design.

Deploy: set BLENDER_SYSTEM_SCRIPTS to the absolute path of `system_scripts/` (this file's
grandparent folder — the one that *contains* this `startup/` subfolder), then launch Blender
5.0+. Point the TLS_DISCOVERY_FAKE_RELEASE env var at an absolute path to fake_release_v1/
(default) or fake_release_v2/ (for the B2 re-point test).
"""
import os
import sys
import tempfile
import time

import bpy

try:
    import addon_utils
except ImportError:  # pragma: no cover - always available inside Blender
    addon_utils = None

LOG_PATH = os.environ.get("TLS_DISCOVERY_LOG") or os.path.join(
    tempfile.gettempdir(), "tls_discovery.log"
)
SCRIPT_DIR_ENTRY_NAME = "TLS_DISCOVERY_TEST"
ADDON_MODULE_NAME = "tls_discovery_addon"


def _log(event, **fields):
    extra = " ".join("{}={}".format(k, v) for k, v in fields.items())
    line = "[{ts}] HOST=blender FILE={file} PID={pid} EVENT={event} {extra}".format(
        ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
        file=__file__,
        pid=os.getpid(),
        event=event,
        extra=extra,
    )
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def _fake_release_root():
    default = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fake_release_v1")
    )
    return os.environ.get("TLS_DISCOVERY_FAKE_RELEASE") or default


def _log_environment():
    # B1: record whatever BLENDER_SYSTEM_SCRIPTS actually resolved to, so this can be compared
    # against what the install script/AYON think they set, to catch a silent override/conflict.
    _log(
        "startup_begin",
        BLENDER_SYSTEM_SCRIPTS=os.environ.get("BLENDER_SYSTEM_SCRIPTS", "<unset>"),
    )
    try:
        paths = bpy.utils.script_paths()
        _log("script_paths_before", count=len(paths), paths=";".join(paths))
    except Exception as exc:  # defensive: API may differ between Blender versions
        _log("script_paths_before_FAILED", error=repr(exc))


def _existing_script_directory_entry():
    try:
        entries = bpy.context.preferences.filepaths.script_directories
    except AttributeError:
        return None, None
    for entry in entries:
        if entry.name == SCRIPT_DIR_ENTRY_NAME:
            return entries, entry
    return entries, None


def _set_entry_directory(entry, value):
    # Property name has moved between Blender versions; try the known candidates.
    for attr in ("directory", "directory_path", "path"):
        if hasattr(entry, attr):
            setattr(entry, attr, value)
            return
    _log("script_directory_attr_not_found")


def _register_or_refresh_script_directory(release_root):
    """Method (i): add, or refresh in place, a named script-directory entry. B2: if an entry
    with this name already exists, this updates its directory rather than adding a duplicate —
    confirms whether a stale persisted path gets fixed on launch."""
    entries, existing = _existing_script_directory_entry()
    if entries is None:
        _log("script_directory_api_unavailable")
        return False
    if existing is not None:
        old_dir = getattr(existing, "directory", getattr(existing, "directory_path", None))
        _set_entry_directory(existing, release_root)
        _log("script_directory_refreshed", old=old_dir, new=release_root)
    else:
        try:
            new_entry = entries.new()
        except Exception as exc:
            _log("script_directory_new_FAILED", error=repr(exc))
            return False
        new_entry.name = SCRIPT_DIR_ENTRY_NAME
        _set_entry_directory(new_entry, release_root)
        _log("script_directory_created", directory=release_root)
    return True


def _try_sys_path_modules(release_root):
    """Method differentiator: does a plain sys.path insert for modules/ work regardless of
    whether the script-directory entry above is honoured?"""
    modules_dir = os.path.join(release_root, "modules")
    added = modules_dir not in sys.path
    if added:
        sys.path.insert(0, modules_dir)
    try:
        import tls_discovery_module  # noqa: F401 - imported for its side effect of existing

        _log(
            "modules_sys_path_import_ok",
            marker=tls_discovery_module.MARKER,
            source_file=tls_discovery_module.__file__,
            added_to_sys_path=added,
        )
    except Exception as exc:
        _log("modules_sys_path_import_FAILED", error=repr(exc), added_to_sys_path=added)


def _try_addon_refresh():
    try:
        bpy.ops.preferences.addon_refresh()
        _log("addon_refresh_ok")
    except Exception as exc:
        _log("addon_refresh_FAILED", error=repr(exc))


def _try_script_paths_refresh():
    try:
        # Add-on metadata refresh alone does not update Python's import paths.
        bpy.utils.refresh_script_paths()
        _log("script_paths_refresh_ok")
    except Exception as exc:
        _log("script_paths_refresh_FAILED", error=repr(exc))


def _check_addon(phase):
    if addon_utils is None:
        _log("addon_utils_unavailable", phase=phase)
        return None
    try:
        loaded_default, loaded_state = addon_utils.check(ADDON_MODULE_NAME)
        module = sys.modules.get(ADDON_MODULE_NAME)
        _log(
            "addon_check",
            phase=phase,
            loaded_default=loaded_default,
            loaded_state=loaded_state,
            source_file=getattr(module, "__file__", None),
        )
        return loaded_state
    except Exception as exc:
        _log("addon_check_FAILED", phase=phase, error=repr(exc))
        return None


def _try_enable_addon(phase):
    """Method (ii): ask Blender's own add-on machinery to enable the fake add-on by module
    name. This is the real G1 test — it only works in-session if Blender's add-on search paths
    already include the script directory registered above."""
    if addon_utils is None:
        return
    try:
        result = addon_utils.enable(ADDON_MODULE_NAME, default_set=True, persistent=False)
        _log("addon_enable_attempt", phase=phase, result=repr(result))
    except Exception as exc:
        _log("addon_enable_attempt_FAILED", phase=phase, error=repr(exc))


def _timer_phase_1():
    """Runs ~0.5s after startup, once Blender has finished its own initialisation, so operators
    and addon_utils calls are more likely to behave normally than at raw module-import time."""
    release_root = _fake_release_root()
    _log("timer_phase_1_begin", release_root=release_root)
    _try_addon_refresh()
    _check_addon(phase="timer_phase_1_before_enable")
    _try_enable_addon(phase="timer_phase_1")
    _check_addon(phase="timer_phase_1_after_enable")
    try:
        paths = bpy.utils.script_paths()
        _log("script_paths_after_phase_1", count=len(paths), paths=";".join(paths))
    except Exception as exc:
        _log("script_paths_after_phase_1_FAILED", error=repr(exc))
    return None  # do not repeat this timer


def _timer_phase_2():
    """Runs several seconds later, still the same session, deliberately *without* calling
    enable/refresh again: confirms whether the explicitly enabled add-on remains loaded.
    This does not test passive add-on discovery."""
    _check_addon(phase="timer_phase_2_recheck")
    return None  # do not repeat this timer


def register():
    _log_environment()
    release_root = _fake_release_root()
    _log("startup_release_setup", release_root=release_root)
    # Saved enabled add-ons load before timers run; repoint before that can import v1.
    _register_or_refresh_script_directory(release_root)
    _try_sys_path_modules(release_root)
    _try_script_paths_refresh()
    bpy.app.timers.register(_timer_phase_1, first_interval=0.5)
    bpy.app.timers.register(_timer_phase_2, first_interval=4.0)
    _log("startup_end")


def unregister():
    for callback in (_timer_phase_1, _timer_phase_2):
        if bpy.app.timers.is_registered(callback):
            bpy.app.timers.unregister(callback)


if __name__ == "__main__":
    register()
