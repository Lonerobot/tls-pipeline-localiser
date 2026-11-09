"""Minimal Tinify API client — stdlib only, no third-party dependencies.

The official tinify package requires requests + certifi + urllib3 + idna +
charset-normalizer.  This module reproduces the two operations we need
(upload + download) using only Python's built-in urllib, so it works in
Blender's bundled Python without any pip install step.

Usage::

    from .lib.tinify_client import compress_file

    ok, msg = compress_file(api_key, "/path/to/file.png", "/path/to/file.png")
    if not ok:
        print(f"Tinify failed: {msg}")

API reference: https://tinify.com/developers/reference/python
"""

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

_SHRINK_URL = "https://api.tinify.com/shrink"


def _auth_header(api_key: str) -> str:
    credentials = base64.b64encode(f"api:{api_key}".encode()).decode()
    return f"Basic {credentials}"


def compress_file(api_key: str, input_path: str, output_path: str) -> tuple:
    """Upload *input_path* to Tinify, write the compressed result to *output_path*.

    Args:
        api_key:     Your Tinify API key.
        input_path:  Absolute path to the source PNG/APNG.
        output_path: Destination path (may be the same as input_path).

    Returns:
        ``(success: bool, info: dict)`` where *info* always contains
        ``'message'`` and on success also contains:
        ``'size_before_mb'``, ``'size_after_mb'``, ``'saved_pct'``,
        ``'elapsed_s'``, ``'compressions_this_month'``.
    """
    auth = _auth_header(api_key)
    t_start = time.monotonic()

    # ── Step 1: read source + record input size ───────────────────────
    try:
        data = Path(input_path).read_bytes()
    except OSError as exc:
        return False, {"message": f"cannot read source file: {exc}"}

    size_before = len(data)

    upload_req = urllib.request.Request(
        _SHRINK_URL,
        data=data,
        headers={
            "Authorization": auth,
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )

    # ── Step 2: upload ────────────────────────────────────────────────
    try:
        with urllib.request.urlopen(upload_req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            location = resp.headers.get("Location") or body.get("output", {}).get("url", "")
            compressions_this_month = body.get("input", {}).get("count", "?")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("message", raw)
        except Exception:
            detail = raw
        # Surface useful hints for common errors
        if exc.code == 401:
            detail = f"invalid or missing API key ({detail})"
        elif exc.code == 429:
            detail = f"compression limit reached — upgrade or wait until next month ({detail})"
        return False, {"message": f"upload HTTP {exc.code}: {detail}"}
    except urllib.error.URLError as exc:
        return False, {"message": f"connection error: {exc.reason}"}
    except Exception as exc:
        return False, {"message": f"upload error: {exc}"}

    if not location:
        return False, {"message": "no output URL in API response"}

    # ── Step 3: download result ───────────────────────────────────────
    dl_req = urllib.request.Request(
        location,
        headers={"Authorization": auth},
    )
    try:
        with urllib.request.urlopen(dl_req, timeout=60) as resp:
            result_bytes = resp.read()
    except urllib.error.URLError as exc:
        return False, {"message": f"download error: {exc.reason}"}
    except Exception as exc:
        return False, {"message": f"download error: {exc}"}

    try:
        Path(output_path).write_bytes(result_bytes)
    except OSError as exc:
        return False, {"message": f"cannot write output file: {exc}"}

    size_after   = len(result_bytes)
    elapsed      = time.monotonic() - t_start
    saved_pct    = (1.0 - size_after / size_before) * 100.0 if size_before else 0.0

    return True, {
        "message":                "OK",
        "size_before_mb":         size_before / (1024 * 1024),
        "size_after_mb":          size_after  / (1024 * 1024),
        "saved_pct":              saved_pct,
        "elapsed_s":              elapsed,
        "compressions_this_month": compressions_this_month,
    }
