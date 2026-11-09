"""Per-user host entries: how each DCC finds the pipeline stub without any environment variable.

Each DCC already looks in a fixed per-user place at startup, so the installer drops a small entry there:

    Maya      <Documents>/maya/modules/TheLinePipeline.mod    a module file; Maya adds the stub folder to its path
    Nuke      ~/.nuke/init.py                                 a marked block that adds the stub folder to the plugin path
    Blender   <user scripts>/startup/tls_pipeline_startup.py  a forwarder that loads the stub

All three point at `<pipeline root>/bootstrap/<host>`, so updating the stubs needs no change here. Entries
are idempotent, never overwrite anything that isn't marked as ours, and are removed cleanly. Environment
variables stay available as overrides for a launcher such as AYON; they are not needed.
"""
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .config import LocalConfig
from .fsutil import atomic_write_text

MARK = "THE LINE pipeline"
BLOCK_BEGIN = f"# >>> {MARK} (managed by the installer; edits inside this block are overwritten) >>>"
BLOCK_END = f"# <<< {MARK} <<<"
MAYA_MODULE_NAME = "TheLinePipeline.mod"
BLENDER_STUB_NAME = "tls_pipeline_startup.py"

CREATED, UPDATED, UNCHANGED, REMOVED, ABSENT = "created", "updated", "unchanged", "removed", "absent"


@dataclass(frozen=True)
class Action:
    host: str
    path: Path
    change: str  # one of CREATED, UPDATED, UNCHANGED, REMOVED, ABSENT


def documents_folder() -> Path:
    """The user's Documents folder, which OneDrive may have moved away from the profile folder."""
    if sys.platform.startswith("win"):
        import ctypes

        buffer = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:  # CSIDL_PERSONAL
            return Path(buffer.value)
    return Path.home() / "Documents"


def maya_app_dir(environ: Mapping[str, str]) -> Path:
    override = environ.get("MAYA_APP_DIR", "").strip()
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "Autodesk" / "maya"
    if sys.platform.startswith("win"):
        return documents_folder() / "maya"
    return Path.home() / "maya"


def nuke_user_dir(environ: Mapping[str, str]) -> Path:
    return Path.home() / ".nuke"


def blender_scripts_dir(series: str, environ: Mapping[str, str]) -> Path:
    override = environ.get("BLENDER_USER_SCRIPTS", "").strip()
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = environ.get("APPDATA", "").strip()
        base = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return base / "Blender Foundation" / "Blender" / series / "scripts"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Blender" / series / "scripts"
    return Path.home() / ".config" / "blender" / series / "scripts"


def _write(path: Path, text: str) -> str:
    """Write `text`, reporting whether the file was created, changed or already identical."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        current = None
    if current == text:
        return UNCHANGED
    atomic_write_text(path, text)
    return CREATED if current is None else UPDATED


def _split_block(text: str) -> tuple[str, str] | None:
    """Return (text before the managed block, text after it), or None if the block is absent."""
    start = text.find(BLOCK_BEGIN)
    if start < 0:
        return None
    end = text.find(BLOCK_END, start)
    if end < 0:
        return None
    return text[:start], text[end + len(BLOCK_END):].lstrip("\r\n")


def _with_block(existing: str, block: str) -> str:
    parts = _split_block(existing)
    if parts is not None:
        before, after = parts
        return before + block + ("\n" + after if after else "")
    return existing + ("" if not existing or existing.endswith("\n") else "\n") + block


def _unmanaged(path: Path, marker: str) -> bool:
    """True if `path` exists but isn't ours, so it must be left alone."""
    try:
        return marker not in path.read_text(encoding="utf-8")
    except OSError:
        return False


# Maya ------------------------------------------------------------------------------------------

def maya_module_text(root: Path) -> str:
    stub = root / "bootstrap" / "maya"
    return f"+ TheLinePipeline 1.0 {stub}\nPYTHONPATH +:= .\n"


def provision_maya(root: Path, environ: Mapping[str, str]) -> Action:
    path = maya_app_dir(environ) / "modules" / MAYA_MODULE_NAME
    return Action("maya", path, _write(path, maya_module_text(root)))


def remove_maya(environ: Mapping[str, str]) -> Action:
    path = maya_app_dir(environ) / "modules" / MAYA_MODULE_NAME
    return _remove_file(path, "maya", "+ TheLinePipeline ")


# Nuke ------------------------------------------------------------------------------------------

def nuke_block(root: Path) -> str:
    stub = root / "bootstrap" / "nuke"
    return f'{BLOCK_BEGIN}\nimport nuke\nnuke.pluginAddPath(r"{stub}")\n{BLOCK_END}\n'


def provision_nuke(root: Path, environ: Mapping[str, str]) -> Action:
    path = nuke_user_dir(environ) / "init.py"
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        existing = ""
    return Action("nuke", path, _write(path, _with_block(existing, nuke_block(root))))


def remove_nuke(environ: Mapping[str, str]) -> Action:
    path = nuke_user_dir(environ) / "init.py"
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return Action("nuke", path, ABSENT)
    parts = _split_block(existing)
    if parts is None:
        return Action("nuke", path, ABSENT)
    remaining = (parts[0] + parts[1]).rstrip("\n")
    if remaining.strip():
        atomic_write_text(path, remaining + "\n")
    else:
        path.unlink()
    return Action("nuke", path, REMOVED)


# Blender ---------------------------------------------------------------------------------------

def blender_stub_text(root: Path) -> str:
    stub = root / "bootstrap" / "blender" / "startup" / BLENDER_STUB_NAME
    return (
        f"# {MARK}: managed by the installer, overwritten on update.\n"
        "import importlib.util\n"
        f'_spec = importlib.util.spec_from_file_location("tls_pipeline_stub", r"{stub}")\n'
        "_stub = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(_stub)\n"
        "register, unregister = _stub.register, _stub.unregister\n"
    )


def provision_blender(root: Path, series: str, environ: Mapping[str, str]) -> Action:
    path = blender_scripts_dir(series, environ) / "startup" / BLENDER_STUB_NAME
    if _unmanaged(path, MARK):
        return Action("blender", path, UNCHANGED)  # someone else's file with our name: leave it alone
    return Action("blender", path, _write(path, blender_stub_text(root)))


def remove_blender(series: str, environ: Mapping[str, str]) -> Action:
    path = blender_scripts_dir(series, environ) / "startup" / BLENDER_STUB_NAME
    return _remove_file(path, "blender", MARK)


def _remove_file(path: Path, host: str, marker: str) -> Action:
    if not path.is_file():
        return Action(host, path, ABSENT)
    if _unmanaged(path, marker):
        return Action(host, path, UNCHANGED)
    path.unlink()
    return Action(host, path, REMOVED)


# All enabled hosts -----------------------------------------------------------------------------

def provision(root: Path, config: LocalConfig, environ: Mapping[str, str] | None = None) -> list[Action]:
    """Install the entry for every host enabled in the local config (an entry per Blender series)."""
    environ = os.environ if environ is None else environ
    actions = []
    for host, series_list in sorted(config.hosts.items()):
        if host == "maya":
            actions.append(provision_maya(root, environ))
        elif host == "nuke":
            actions.append(provision_nuke(root, environ))
        elif host == "blender":
            actions += [provision_blender(root, series, environ) for series in series_list]
    return actions


def unprovision(config: LocalConfig, environ: Mapping[str, str] | None = None) -> list[Action]:
    """Remove the entries `provision` made for the enabled hosts, leaving everything else alone."""
    environ = os.environ if environ is None else environ
    actions = []
    for host, series_list in sorted(config.hosts.items()):
        if host == "maya":
            actions.append(remove_maya(environ))
        elif host == "nuke":
            actions.append(remove_nuke(environ))
        elif host == "blender":
            actions += [remove_blender(series, environ) for series in series_list]
    return actions
