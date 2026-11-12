"""Put the code a host loads into the pipeline root, so a launched host can find the pipeline.

A host's launcher points it at `<root>/bootstrap/<host>`; that stub loads `<root>/__init__.py` (the pipeline entry,
with `about.py`), which imports the core from `<root>/localiser`. The tray app runs this at every start, so the root
always holds the stubs and core that came with the app, and an update to them needs no separate step.

Only these four things in the root are managed. Config, bundles and state are never touched. Files are replaced
one at a time and only when their content differs, so a running host is never left half-updated.
"""
import os
import shutil
import uuid
from pathlib import Path

from .errors import LocaliserError
from .provision import CREATED, REMOVED, UPDATED, Action

CODE_HOST = "code"  # the `host` of an Action that describes a pipeline file rather than a DCC entry
ENTRY_FILES = ("__init__.py", "about.py")
STUB_FOLDER = "bootstrap"
CORE_FOLDER = "localiser"


def pipeline_source() -> Path | None:
    """The folder with the stubs and the pipeline entry: structure/THE-LINE/pipeline in a checkout of this project."""
    candidate = Path(__file__).resolve().parents[2] / "structure" / "THE-LINE" / "pipeline"
    return candidate if (candidate / STUB_FOLDER).is_dir() and (candidate / ENTRY_FILES[0]).is_file() else None


def _files(folder: Path):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.relative_to(folder).parts:
            yield path


def _copy(source: Path, target: Path) -> str | None:
    """Copy `source` over `target` if the content differs; report what happened, or None if already identical."""
    data = source.read_bytes()
    try:
        if target.read_bytes() == data:
            return None
        change = UPDATED
    except OSError:
        change = CREATED
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return change


def _sync_tree(source: Path, target: Path, actions: list[Action]) -> None:
    wanted = set()
    for path in _files(source):
        destination = target / path.relative_to(source)
        wanted.add(destination)
        if change := _copy(path, destination):
            actions.append(Action(CODE_HOST, destination, change))
    if target.is_dir():
        for path in _files(target):
            if path not in wanted:  # a file the source no longer has
                path.unlink()
                actions.append(Action(CODE_HOST, path, REMOVED))


def install_pipeline_code(root: Path, source: Path | None = None, core: Path | None = None) -> list[Action]:
    """Make the stubs, entry files and core in `root` match `source` and `core`; return what changed (empty when
    the root was already current). `source` defaults to this checkout's pipeline folder and `core` to this package."""
    root = Path(root)
    source = Path(source) if source else pipeline_source()
    if source is None or not (source / STUB_FOLDER).is_dir():
        raise LocaliserError("the pipeline files to install (bootstrap stubs and entry) were not found next to this program")
    core = Path(core) if core else Path(__file__).resolve().parent
    if root.resolve() == source.resolve():
        return []  # the source tree is itself a root: nothing to copy
    actions: list[Action] = []
    for name in ENTRY_FILES:
        if change := _copy(source / name, root / name):
            actions.append(Action(CODE_HOST, root / name, change))
    _sync_tree(source / STUB_FOLDER, root / STUB_FOLDER, actions)
    _sync_tree(core, root / CORE_FOLDER, actions)
    return actions
