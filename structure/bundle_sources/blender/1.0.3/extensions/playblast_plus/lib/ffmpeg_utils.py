"""FFmpeg discovery and background download/install utilities."""

import os
import shutil
import stat
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

_FFMPEG_EXE = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def default_download_url() -> str:
    """Return the default download URL for the current platform (from config.json)."""
    try:
        from .ayon_config import load_ffmpeg_urls
        urls = load_ffmpeg_urls()
    except Exception:
        urls = {}
    key = "linux" if sys.platform.startswith("linux") else sys.platform
    return urls.get(key, "")


def bin_dir() -> Path:
    """Return the add-on's local bin/ directory (created on demand)."""
    return Path(__file__).parent.parent / "bin"


def find_ffmpeg(custom_path: str = "") -> str | None:
    """Locate an ffmpeg executable.

    Discovery order:
    1. *custom_path* from addon preferences (if non-empty and the file exists).
    2. Additional search paths from config.json ``ffmpeg.search_paths``.
    3. System PATH via ``shutil.which``.
    4. Local ``<addon>/bin/ffmpeg[.exe]``.

    Returns the absolute path string, or ``None`` if not found.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return str(p)

    try:
        from .ayon_config import load_ffmpeg_search_paths
        for candidate in load_ffmpeg_search_paths():
            cp = Path(candidate)
            if cp.is_file():
                return str(cp)
    except Exception:
        pass

    which = shutil.which("ffmpeg")
    if which:
        return which

    local = bin_dir() / _FFMPEG_EXE
    if local.is_file():
        return str(local)

    return None


# ---------------------------------------------------------------------------
# Background download / install state
# ---------------------------------------------------------------------------

dl_state: dict = {
    "running":  False,
    "progress": 0.0,   # 0.0 – 1.0
    "error":    None,
    "done":     False,
}


def _reporthook(block_count: int, block_size: int, total_size: int) -> None:
    if total_size > 0:
        dl_state["progress"] = min(block_count * block_size / total_size, 1.0)


def _download_and_install(url: str) -> None:
    """Download FFmpeg and extract ffmpeg[.exe] to <addon>/bin/ ."""
    if not url:
        dl_state["error"] = "No download URL configured."
        dl_state["running"] = False
        return

    dest_dir = bin_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    is_zip = url.lower().endswith((".zip", "/zip"))
    archive_path = dest_dir / ("ffmpeg_dl.zip" if is_zip else "ffmpeg_dl.tar.xz")

    # --- Download ---
    try:
        urllib.request.urlretrieve(url, str(archive_path), reporthook=_reporthook)
    except Exception as exc:
        dl_state["error"] = f"Download failed: {exc}"
        dl_state["running"] = False
        archive_path.unlink(missing_ok=True)
        return

    exe_path = dest_dir / _FFMPEG_EXE

    # --- Extract ---
    try:
        if is_zip:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # The exe may sit inside a sub-directory within the archive
                target = next(
                    (m for m in zf.namelist()
                     if m.endswith(f"/{_FFMPEG_EXE}") or m == _FFMPEG_EXE),
                    None,
                )
                if target is None:
                    raise RuntimeError(f"{_FFMPEG_EXE} not found in archive")
                data = zf.read(target)
                exe_path.write_bytes(data)
        else:
            import tarfile
            with tarfile.open(archive_path, "r:xz") as tf:
                target = next(
                    (m for m in tf.getmembers()
                     if m.name.endswith(f"/{_FFMPEG_EXE}") or m.name == _FFMPEG_EXE),
                    None,
                )
                if target is None:
                    raise RuntimeError(f"{_FFMPEG_EXE} not found in archive")
                fobj = tf.extractfile(target)
                if fobj:
                    exe_path.write_bytes(fobj.read())
    except Exception as exc:
        dl_state["error"] = f"Extraction failed: {exc}"
        dl_state["running"] = False
        archive_path.unlink(missing_ok=True)
        return
    finally:
        archive_path.unlink(missing_ok=True)

    # --- Ensure executable on POSIX ---
    if sys.platform != "win32" and exe_path.is_file():
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # --- Validate ---
    import subprocess
    try:
        subprocess.run(
            [str(exe_path), "-version"],
            capture_output=True, timeout=10, check=True,
        )
    except Exception as exc:
        dl_state["error"] = f"Validation failed: {exc}"
        dl_state["running"] = False
        return

    dl_state["done"] = True
    dl_state["running"] = False


def start_install(url: str = "") -> None:
    """Reset state and kick off the background install thread."""
    resolved = url or default_download_url()
    dl_state.update({"running": True, "progress": 0.0, "error": None, "done": False})
    thread = threading.Thread(target=_download_and_install, args=(resolved,), daemon=True)
    thread.start()
