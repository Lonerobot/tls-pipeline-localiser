"""Render docs/diagrams/*.mmd to SVG with mermaid-cli.

    python docs/build_diagrams.py

Needs Node.js (npx) and a Chromium-based browser. Chrome or Edge are found automatically; set
PUPPETEER_EXECUTABLE_PATH to use another. mermaid-cli is fetched by npx on first run, without
downloading its own browser. Edit the .mmd files, never the generated .svg files.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DIAGRAMS = Path(__file__).resolve().parent / "diagrams"
CONFIG = DIAGRAMS / "mermaid.config.json"
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_browser():
    configured = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if configured:
        return configured
    for candidate in BROWSERS:
        if Path(candidate).is_file():
            return candidate
    sys.exit("No Chrome or Edge found. Set PUPPETEER_EXECUTABLE_PATH to a Chromium-based browser.")


def main():
    npx = shutil.which("npx")
    if not npx:
        sys.exit("npx not found. Install Node.js.")
    sources = sorted(DIAGRAMS.glob("*.mmd"))
    if not sources:
        sys.exit(f"no .mmd files in {DIAGRAMS}")

    env = dict(os.environ, PUPPETEER_SKIP_DOWNLOAD="1")
    with tempfile.TemporaryDirectory() as tmp:
        puppeteer = Path(tmp) / "puppeteer.json"
        puppeteer.write_text(json.dumps({"executablePath": find_browser(), "args": ["--no-sandbox"]}))
        for source in sources:
            target = source.with_suffix(".svg")
            command = [
                npx, "--yes", "@mermaid-js/mermaid-cli",
                "-i", str(source), "-o", str(target),
                "-c", str(CONFIG), "-p", str(puppeteer), "-b", "white",
            ]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            if result.returncode:
                sys.exit(f"{source.name} failed:\n{result.stdout}\n{result.stderr}")
            print(f"{source.name} -> {target.name}")


if __name__ == "__main__":
    main()
