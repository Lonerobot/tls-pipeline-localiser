"""Find a compatible external Windows Python for hosts that do not bundle one."""
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from .errors import LocaliserError


def _registered_python_homes(version: str) -> list[Path]:
    if not sys.platform.startswith("win"):
        return []
    import winreg

    homes = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(
                hive, rf"Software\Python\PythonCore\{version}\InstallPath",
                access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                home, _ = winreg.QueryValueEx(key, "")
                if isinstance(home, str) and home.strip():
                    homes.append(Path(home))
        except FileNotFoundError:
            continue
    return homes


def _candidate_homes(version: str, environ: Mapping[str, str]):
    yield from _registered_python_homes(version)
    name = "Python" + version.replace(".", "")
    local = environ.get("LOCALAPPDATA", "").strip()
    if local:
        yield Path(local) / "Programs" / "Python" / name
    for variable in ("ProgramW6432", "ProgramFiles"):
        base = environ.get(variable, "").strip()
        if base:
            yield Path(base) / name
    drive = environ.get("SystemDrive", "").strip()
    if drive:
        yield Path(drive + "\\") / name
    for folder in environ.get("PATH", "").split(os.pathsep):
        if folder.strip().strip('"'):
            yield Path(folder.strip().strip('"'))


def _runtime_problem(home: Path, version: str) -> str | None:
    dll = home / f"python{version.replace('.', '')}.dll"
    executable = home / "python.exe"
    if not executable.is_file() or not dll.is_file():
        return f"{home} must contain python.exe and {dll.name}"
    try:
        result = subprocess.run(
            [
                str(executable), "-I", "-S", "-c",
                "import struct,sys; print('%s.%s:%s' % (*sys.version_info[:2], struct.calcsize('P') * 8))",
            ],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"could not validate {executable}: {exc}"
    if result.returncode:
        return f"{executable} exited {result.returncode}: {result.stderr.strip()}"
    if result.stdout.strip() != f"{version}:64":
        return f"{executable} reported {result.stdout.strip()!r}; required {version}:64"
    return None


def find_python_home(
    version: str, override: Path | None, environ: Mapping[str, str]
) -> Path:
    """Prefer an explicit folder, otherwise discover and validate an installed 64-bit Python."""
    supplied = environ.get("PYTHON_LIB_PATH", "").strip()
    explicit = override if override is not None else Path(supplied) if supplied else None
    if explicit is not None:
        problem = _runtime_problem(explicit, version)
        if problem:
            raise LocaliserError(f"Invalid external Python {version}: {problem}. Fix python_homes or PYTHON_LIB_PATH.")
        return explicit
    seen = set()
    problems = []
    for home in _candidate_homes(version, environ):
        identity = os.path.normcase(os.path.abspath(home))
        if identity in seen:
            continue
        seen.add(identity)
        problem = _runtime_problem(home, version)
        if problem is None:
            return home
        if (home / "python.exe").is_file():
            problems.append(problem)
    detail = " " + "; ".join(problems) if problems else ""
    raise LocaliserError(
        f"A 64-bit Python {version} installation is required. Install it or set python_homes.harmony "
        f"in the local config.json to its installation folder.{detail}"
    )
