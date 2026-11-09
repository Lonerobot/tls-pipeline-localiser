"""
THE LINE script library.

Scans the folders next to this file for Maya scripts, so the menu always matches what is on disk.
Adding a script (or a folder) needs no menu definition: it appears the next time Maya starts.

Layout, one level deep -

    LineTools/
        _global/playblastPlus.py     scripts in an underscore folder are listed directly in the top level
        _scene/SetOverscanRes.py
        anim/bakeToLocators.py       any other folder becomes a submenu named after the folder
        rig/launchNgskintools.py

Scripts are run as __main__ by run_script, so a script keeps its code under

    if __name__ == "__main__":
        ...

If a tool needs specific setup (a module or package living in these folders), write a small script that
launches it and the folder scan picks that up. For example, playblastPlus.py

    if __name__ == "__main__":
        from playblast_plus import launch
        launch.run()

If a script needs a module that isn't part of this bundle (a tool that AYON provides, say), declare it at
the top of the script. The runner then says so clearly instead of failing, and the menu item's tooltip
lists it. Use a list of module names, or a dict of module name to a note about where it comes from:

    REQUIRES = {"dwpicker": "comes from the AYON tool descriptor"}
"""

import ast
import importlib.util
import runpy
from dataclasses import dataclass, field
from pathlib import Path

from tls_common import MayaLogger


class log(MayaLogger):
    NAME = "line_tools.library"


SCRIPT_SUFFIXES = (".py", ".mel")
GLOBAL_PREFIX = "_"  # folders starting with this list their scripts at the top level of the menu
RAN, MISSING, FAILED = "ran", "missing", "failed"  # what run_script returns


@dataclass(frozen=True)
class Script:
    section: str  # the folder name
    file_name: str  # the file name with its suffix
    title: str
    requires: tuple = ()  # (module name, note) pairs the script declares in REQUIRES


@dataclass
class Section:
    name: str
    title: str
    scripts: list = field(default_factory=list)


@dataclass
class Library:
    top_level: list  # Script, from the underscore folders
    sections: list  # Section, one per other folder that has scripts


def make_nice_name(name):
    """'playblastPlus' -> 'Playblast Plus', 'set_overscan_res' -> 'Set Overscan Res'."""
    nice_name = ""
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            if i < len(name) - 1 and name[i + 1].islower():
                nice_name += " " + char
            else:
                nice_name += char
        elif char == "_":
            nice_name += " "
        else:
            nice_name += char
    return " ".join(nice_name.title().split())


def default_root():
    return Path(__file__).resolve().parent


def _scripts_in(folder):
    return sorted(
        (
            item
            for item in folder.iterdir()
            if item.is_file() and item.suffix in SCRIPT_SUFFIXES and item.name != "__init__.py"
        ),
        key=lambda item: item.name.casefold(),
    )


def read_requirements(path):
    """Return the (module name, note) pairs in a script's top-level REQUIRES, without running the script."""
    if Path(path).suffix != ".py":
        return ()
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, ValueError):
        return ()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REQUIRES" for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return ()
            if isinstance(value, dict):
                return tuple((str(name), str(note)) for name, note in value.items())
            if isinstance(value, (list, tuple)):
                return tuple((str(name), "") for name in value)
    return ()


def is_available(module_name):
    """True if `module_name` can be imported in this session, checked without importing it."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False  # find_spec imports a dotted name's parent packages, which may be missing


def describe_missing(name, note=""):
    return "needs '{}', which isn't available in this session{}".format(name, " ({})".format(note) if note else "")


def scan(root=None):
    """Read the script folders under `root` (default: this folder) into a Library."""
    root = Path(root) if root else default_root()
    folders = sorted(
        (item for item in root.iterdir() if item.is_dir() and not item.name.startswith((".", "__"))),
        key=lambda item: (not item.name.startswith(GLOBAL_PREFIX), item.name.casefold()),
    )
    top_level, sections = [], []
    for folder in folders:
        scripts = [
            Script(folder.name, item.name, make_nice_name(item.stem), read_requirements(item))
            for item in _scripts_in(folder)
        ]
        if folder.name.startswith(GLOBAL_PREFIX):
            top_level.extend(scripts)
        elif scripts:
            sections.append(Section(folder.name, folder.name.title(), scripts))
    return Library(top_level, sections)


def run_script(section, module, root=None, notify=None):
    """Run <root>/<section>/<module> as __main__ and return RAN, MISSING or FAILED.

    Nothing is raised into Maya's UI. A missing module is a warning without a traceback, and `notify`,
    if given, is called with the same text so the caller can show it to the user.
    """
    path = (Path(root) if root else default_root()) / section / module
    where = "[LINE SCRIPT][{}][Module] {}".format(section, module)

    for name, note in read_requirements(path):
        if not is_available(name):
            return _missing(where, module, describe_missing(name, note), notify)

    try:
        if path.suffix == ".mel":
            from maya import mel

            mel.eval('source "{}"'.format(path.as_posix()))
        else:
            runpy.run_path(str(path), run_name="__main__")
    except ModuleNotFoundError as exc:  # a module the script didn't declare
        if exc.name:
            log.debug("%s import failed", where, exc_info=True)
            return _missing(where, module, describe_missing(exc.name), notify)
        log.exception("%s failed", where)
        return FAILED
    except Exception:
        log.exception("%s failed", where)
        return FAILED
    log.info(where)
    return RAN


def _missing(where, module, reason, notify):
    log.warning("%s %s", where, reason)
    if notify:
        notify("{} {}".format(Path(module).stem, reason))
    return MISSING
