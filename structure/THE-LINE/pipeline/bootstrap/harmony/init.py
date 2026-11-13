#!/usr/bin/env python3
"""
Launch Toon Boom Harmony with custom script location.

This script sets the TOONBOOM_GLOBAL_SCRIPT_LOCATION environment variable
and launches Harmony Premium with the specified script directory.
"""

import os
import subprocess
import sys
from pathlib import Path

# # Configuration
# HARMONY_EXE = r"C:\Program Files (x86)\Toon Boom Animation\Toon Boom Harmony 24 Premium\win64\bin\HarmonyPremium.exe"
# SCRIPT_LOCATION = r"Y:\PIPELINE\config\harmony\scripts"

def _pipeline_root():
    """TLS_PIPELINE if set, otherwise the per-user install location (same rule as localiser.config)."""
    root = os.environ.get("TLS_PIPELINE", "").strip()
    if root:
        return root
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "")
        root = os.path.join(base, "TheLine", "pipeline") if base else ""
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "TheLine", "Pipeline")
    else:
        data = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        root = os.path.join(data, "theline", "pipeline")
    if not os.path.isfile(os.path.join(root, "config.json")):
        raise RuntimeError("TLS_PIPELINE is not set and there is no pipeline installed at {!r}".format(root))
    os.environ.setdefault("TLS_PIPELINE", root)
    return root



def launch_harmony():
    """Launch Harmony with custom script location environment variable."""
    
    # Verify Harmony executable exists
    if not Path(HARMONY_EXE).exists():
        print(f"Error: Harmony executable not found at: {HARMONY_EXE}")
        return False
    
    # Verify script directory exists
    if not Path(SCRIPT_LOCATION).exists():
        print(f"Error: Script directory not found at: {SCRIPT_LOCATION}")
        return False
    
    # Set up environment
    env = os.environ.copy()
    env["TOONBOOM_GLOBAL_SCRIPT_LOCATION"] = SCRIPT_LOCATION
    
    print(f"Setting TOONBOOM_GLOBAL_SCRIPT_LOCATION to: {SCRIPT_LOCATION}")
    print(f"Launching Harmony from: {HARMONY_EXE}")
    
    try:
        # Launch Harmony with the modified environment
        subprocess.Popen([HARMONY_EXE], env=env)
        print("Harmony launched successfully!")
        return True
        
    except Exception as e:
        print(f"Error launching Harmony: {e}")
        return False

if __name__ == "__main__":
    success = launch_harmony()
    sys.exit(0 if success else 1)