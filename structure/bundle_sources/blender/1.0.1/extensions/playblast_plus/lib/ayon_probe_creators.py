"""
Probe available AYON TrayPublisher creators and write results as JSON.

Run via:
    ayon_console.exe run lib/ayon_probe_creators.py --project <name> --output <path.json>

This runs in the full AYON Python environment (outside Blender) where OTIO
and all publish plugins can be imported safely.  Blender reads the JSON result
back rather than calling CreateContext directly (which crashes due to the
OTIO / MSVCP140.dll conflict inside Blender's Python runtime).
"""

import argparse
import json
import os
import sys


_VALID_IDS = {"settings_review", "settings_render", "settings_image"}


def main():
    parser = argparse.ArgumentParser(
        description="Probe AYON TrayPublisher creators and write JSON."
    )
    # Project comes from the AYON launcher environment — do NOT pass it as a
    # CLI flag because ayon_console consumes --project before the script sees it.
    parser.add_argument("--output", required=True, help="Path to write JSON results.")
    # Strip bare '--' separators that ayon_console may inject into sys.argv.
    argv = [a for a in sys.argv[1:] if a != "--"]
    args = parser.parse_args(argv)

    project_name = os.environ.get("AYON_PROJECT_NAME", "")
    if not project_name:
        print("[ayon_probe] ERROR: AYON_PROJECT_NAME env var is not set.", file=sys.stderr)
        sys.exit(1)

    from ayon_core.pipeline import install_host
    from ayon_core.pipeline.create import CreateContext
    from ayon_traypublisher.api import TrayPublisherHost

    host = TrayPublisherHost()
    host.set_project_name(project_name)
    install_host(host)

    create_context = CreateContext(host, headless=True)

    results = []
    for cid, creator in create_context.creators.items():
        if cid not in _VALID_IDS:
            continue
        product_type = cid[len("settings_"):]
        results.append({
            "id":     cid,
            "label":  product_type.capitalize(),
            "family": product_type,
        })

    results.sort(key=lambda x: x["label"])

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(results, fh)

    print(f"[ayon_probe] Found {len(results)} creators: {[r['id'] for r in results]}")


if __name__ == "__main__":
    main()
