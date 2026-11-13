"""Unified configuration for Playblast Plus.

Single source of truth: ``config.json`` at the addon root.
All subsystems (AYON publish, APNG presets, FFmpeg URLs, stored creators)
read from — and write to — this file.
"""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# ---------------------------------------------------------------------------
# Built-in defaults (used when config.json is absent or a key is missing)
# ---------------------------------------------------------------------------

_DEFAULT_PUBLISH: dict = {
    "MP4":      {"products": ["review", "render"], "variants": ["Main", "Turnaround"]},
    "SEQUENCE": {"products": ["review", "render"], "variants": ["Main", "Turnaround"]},
    "IMAGE":    {"products": ["review", "image"],  "variants": ["Main", "Wire", "Chalk"]},
}

_DEFAULT_APNG_PRESETS: list = [
    {"name": "profile_effects",    "label": "Profile Effects",    "width": 450,  "height": 880, "framerate": 12},
    {"name": "avatar_decorations", "label": "Avatar Decorations", "width": 288,  "height": 288, "framerate": 12},
    {"name": "hd_24fps",           "label": "HD 720p 24fps",      "width": 1280, "height": 720, "framerate": 24},
]

_DEFAULT_FFMPEG_URLS: dict = {
    "win32":  "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "linux":  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
    "darwin": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
}

_DEFAULT_FFMPEG_SEARCH_PATHS: list = [
    "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
    "C:\\ProgramData\\chocolatey\\bin\\ffmpeg.exe",
    "C:\\ProgramData\\scoop\\apps\\ffmpeg\\current\\bin\\ffmpeg.exe",
    "/usr/local/bin/ffmpeg",
    "/opt/homebrew/bin/ffmpeg",
    "/opt/homebrew/opt/ffmpeg/bin/ffmpeg",
]

_DEFAULT_PREFERRED_PLAYERS: dict = {
    "media_review": "",
    "image_review": "",
}

# ---------------------------------------------------------------------------
# Internal I/O helpers
# ---------------------------------------------------------------------------

def _read_raw() -> dict:
    """Read config.json from disk. Returns empty dict on any error."""
    if not _CONFIG_PATH.is_file():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"[PlayblastPlus] config.json read error: {exc}")
        return {}


def _write_raw(data: dict) -> None:
    """Write data to config.json via a temp file for crash safety."""
    tmp = _CONFIG_PATH.parent / f".config_tmp_{os.getpid()}.json"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp.replace(_CONFIG_PATH)
    except Exception as exc:
        print(f"[PlayblastPlus] config.json write error: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Return effective AYON publish config (products/variants per media type)."""
    raw = _read_raw()
    publish = raw.get("ayon", {}).get("publish", {})
    merged = {k: dict(v) for k, v in _DEFAULT_PUBLISH.items()}
    for media_type, settings in publish.items():
        if media_type in merged:
            merged[media_type].update(settings)
        else:
            merged[media_type] = settings
    return merged


def load_creators() -> list:
    """Return saved AYON creators from config.json. Empty list if not yet configured."""
    return _read_raw().get("ayon", {}).get("creators", [])


def save_creators(creators: list) -> None:
    """Persist creators list into config.json, preserving all other keys."""
    raw = _read_raw()
    raw.setdefault("ayon", {})["creators"] = creators
    _write_raw(raw)


def load_apng_presets() -> list:
    """Return APNG presets from config.json, falling back to built-in defaults."""
    raw = _read_raw()
    return raw.get("apng_presets", _DEFAULT_APNG_PRESETS)


def load_ffmpeg_urls() -> dict:
    """Return FFmpeg download URLs from config.json, falling back to built-in defaults."""
    raw = _read_raw()
    return raw.get("ffmpeg", {}).get("download_urls", _DEFAULT_FFMPEG_URLS)


def load_ffmpeg_search_paths() -> list:
    """Return additional FFmpeg search paths from config.json, falling back to built-in defaults."""
    raw = _read_raw()
    return raw.get("ffmpeg", {}).get("search_paths", _DEFAULT_FFMPEG_SEARCH_PATHS)


def load_preferred_players() -> dict:
    """Return preferred player paths from config.json, falling back to built-in defaults."""
    raw = _read_raw()
    players = raw.get("preferred_player", {})
    result = dict(_DEFAULT_PREFERRED_PLAYERS)
    result.update(players)
    return result
