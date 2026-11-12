"""The DCCs the pipeline supports, in one place. Adding a host starts with an entry here.

Each entry says how the host is named in the UI, which icon to show, how the stub is found when an
environment variable overrides the default, where its bundle's entry point and shared packages live,
and how to detect which versions are installed on a workstation.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ICONS_DIR = Path(__file__).resolve().parent / "icons"


@dataclass(frozen=True)
class HostInfo:
    name: str  # the id used everywhere: config, folders, variables
    display_name: str
    discovery_variable: str  # how a launcher overrides stub discovery; the default lookup needs no variable
    python_root: str = "."  # the bundle's entry-point folder, unless a bundle.json says otherwise
    shared_destination: str = "."  # where shared packages are merged into a bundle
    install_folder: str = ""  # under Program Files; where this host's versions are installed
    install_pattern: str = ""  # a regex whose first group is the series, matched against folder names
    executable: str = ""  # the program inside an install folder, with {series} filled in

    @property
    def icon(self) -> Path | None:
        path = ICONS_DIR / f"{self.name}.png"
        return path if path.is_file() else None


HOSTS: dict[str, HostInfo] = {
    "maya": HostInfo(
        "maya", "Maya", "PYTHONPATH", install_folder="Autodesk", install_pattern=r"^Maya(\d{4})$",
        executable="bin/maya.exe",
    ),
    "nuke": HostInfo(
        "nuke", "Nuke", "NUKE_PATH", install_folder="", install_pattern=r"^Nuke(\d+\.\d+)v\d+$",
        executable="Nuke{series}.exe",
    ),
    "blender": HostInfo(
        "blender",
        "Blender",
        "BLENDER_SYSTEM_SCRIPTS",
        python_root="startup",
        shared_destination="modules",
        install_folder="Blender Foundation",
        install_pattern=r"^Blender (\d+\.\d+)$",
        executable="blender.exe",
    ),
}


def program_files_roots(environ: Mapping[str, str] | None = None) -> list[Path]:
    environ = os.environ if environ is None else environ
    roots = []
    for name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        value = environ.get(name, "").strip()
        if value and Path(value) not in roots:
            roots.append(Path(value))
    return roots


def detect_installed_series(host: str, roots: list[Path] | None = None) -> list[str]:
    """The series of `host` installed in the standard Windows locations, oldest first.

    Several patch builds of one series (Nuke 15.1v2 and 15.1v10) are one series. Other platforms return
    an empty list until their locations are added here.
    """
    info = HOSTS.get(host)
    if info is None or not info.install_pattern:
        return []
    pattern = re.compile(info.install_pattern)
    found = set()
    for root in program_files_roots() if roots is None else roots:
        parent = root / info.install_folder if info.install_folder else root
        try:
            names = [entry.name for entry in parent.iterdir() if entry.is_dir()]
        except OSError:
            continue
        found.update(match.group(1) for name in names if (match := pattern.match(name)))
    return sorted(found, key=lambda series: [int(part) for part in series.split(".")])


def find_executable(host: str, series: str, roots: list[Path] | None = None) -> Path | None:
    """The program that starts `host` `series` from the standard Windows install locations, or None if it isn't
    installed there. Of several patch builds of one series (Nuke 15.1v2 and 15.1v10) the newest is used."""
    info = HOSTS.get(host)
    if info is None or not info.install_pattern or not info.executable:
        return None
    pattern = re.compile(info.install_pattern)
    found = []
    for root in program_files_roots() if roots is None else roots:
        parent = root / info.install_folder if info.install_folder else root
        try:
            folders = [entry for entry in parent.iterdir() if entry.is_dir()]
        except OSError:
            continue
        found += [
            (tuple(int(part) for part in re.findall(r"\d+", folder.name)), folder)
            for folder in folders
            if (match := pattern.match(folder.name)) and match.group(1) == series
        ]
    for _, folder in sorted(found, reverse=True):
        program = folder / info.executable.format(series=series)
        if program.is_file():
            return program
    return None

