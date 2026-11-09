import nuke

# Import and run the simple toolchain loader
try:
    from toolchains import load_toolchains
    load_toolchains()
    print("[OK] Toolchains loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load toolchains: {e}")

# Load shortcuts after UI is ready
try:
    from utils.ShortcutManager import load_shortcuts_from_config
    load_shortcuts_from_config()
    print("[OK] All keyboard shortcuts loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load shortcuts: {e}")

# Apply default grid settings (only if enabled)
try:
    from utils.Grid import apply_default_grid_settings, is_grid_enabled
    if is_grid_enabled():
        apply_default_grid_settings()
        print("[OK] Default grid settings applied successfully")
    else:
        print("[INFO] Grid settings disabled in configuration - skipping grid setup")
except Exception as e:
    print(f"[ERROR] Failed to apply grid settings: {e}")


