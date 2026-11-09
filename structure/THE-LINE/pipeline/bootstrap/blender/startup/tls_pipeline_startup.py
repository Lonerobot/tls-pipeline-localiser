"""Blender bootstrap stub. Set BLENDER_SYSTEM_SCRIPTS to the folder containing startup/ (bootstrap/blender).

Blender calls register() during startup, before saved add-ons load, so localising must happen here
synchronously, not from a timer. Blender also swallows exceptions raised from register(), so failures
are printed here.

After localising, the stub exposes what the bundle ships (all optional):
- splash/splash.png  -> BLENDER_CUSTOM_SPLASH
- the bundle root    -> a script directory entry (startup/, modules/, presets/, addons/)
- extensions/<id>/   -> a local extension repository. Folders must be named after the id in their
                        blender_manifest.toml. All are enabled.
- addons/<name>      -> legacy add-ons (bl_info). All are enabled. Keep extensions out of addons/:
                        Blender would list them a second time as legacy add-ons.
"""
import importlib.util
import os
import sys
import traceback

import addon_utils
import bpy

SCRIPT_DIRECTORY_NAME = "THELINE_PIPELINE"
EXTENSION_REPO_MODULE = "tls_pipeline"  # extensions load as bl_ext.tls_pipeline.<extension id>
EXTENSION_REPO_NAME = "THE LINE Pipeline"
SPLASH_VARIABLE = "BLENDER_CUSTOM_SPLASH"
SPLASH_FILE = os.path.join("splash", "splash.png")


def _pipeline_root():
    """TLS_PIPELINE if set, otherwise the per-user install location (same rule as localiser.config)."""
    root = os.environ.get("TLS_PIPELINE", "").strip()
    if root:
        return root
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "")
        root = os.path.join(base, "TheLine", "Pipeline") if base else ""
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "TheLine", "Pipeline")
    else:
        data = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        root = os.path.join(data, "theline", "pipeline")
    if not os.path.isfile(os.path.join(root, "config.json")):
        raise RuntimeError("TLS_PIPELINE is not set and there is no pipeline installed at {!r}".format(root))
    os.environ.setdefault("TLS_PIPELINE", root)
    return root


def _load_pipeline():
    if "tls_pipeline" not in sys.modules:
        root = _pipeline_root()
        spec = importlib.util.spec_from_file_location(
            "tls_pipeline", os.path.join(root, "__init__.py"), submodule_search_locations=[root]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["tls_pipeline"] = module
        spec.loader.exec_module(module)
    return sys.modules["tls_pipeline"]


def _extension_name(extension_id):
    return "bl_ext.{}.{}".format(EXTENSION_REPO_MODULE, extension_id)


def _shipped_addons(release_root):
    """Return (extensions folder, extension ids, legacy add-on names) the bundle ships, in a stable order."""
    extensions_dir = os.path.join(release_root, "extensions")
    addons_dir = os.path.join(release_root, "addons")
    extensions, legacy = [], []
    if os.path.isdir(extensions_dir):
        for name in sorted(os.listdir(extensions_dir)):
            if os.path.isfile(os.path.join(extensions_dir, name, "blender_manifest.toml")):
                extensions.append(name)
    if os.path.isdir(addons_dir):
        for name in sorted(os.listdir(addons_dir)):
            path = os.path.join(addons_dir, name)
            if name.startswith((".", "__")):
                continue
            if os.path.isfile(os.path.join(path, "__init__.py")):
                legacy.append(name)
            elif name.endswith(".py") and os.path.isfile(path):
                legacy.append(name[:-3])
    return extensions_dir, extensions, legacy


def _expose_release(release_root, extensions_dir, extensions):
    """Point Blender at the bundle. Entries are found by name and updated, never duplicated.

    Preferences persist these entries and the enabled add-ons, so everything is rewritten on every
    launch, here in register() and before Blender loads the saved add-ons, rather than trusting what
    an earlier release left behind.
    """
    prefs = bpy.context.preferences

    for entry in prefs.filepaths.script_directories:
        if entry.name == SCRIPT_DIRECTORY_NAME:
            break
    else:
        entry = prefs.filepaths.script_directories.new()
        entry.name = SCRIPT_DIRECTORY_NAME
    entry.directory = release_root

    if extensions:
        for repo in prefs.extensions.repos:
            if repo.module == EXTENSION_REPO_MODULE:
                break
        else:
            repo = prefs.extensions.repos.new(
                name=EXTENSION_REPO_NAME, module=EXTENSION_REPO_MODULE, custom_directory=extensions_dir, remote_url=""
            )
        repo.use_custom_directory = True
        repo.custom_directory = extensions_dir
        repo.enabled = True

    # A release that dropped an extension must not leave it enabled in the saved preferences.
    wanted = {_extension_name(name) for name in extensions}
    prefix = _extension_name("")
    for addon in list(prefs.addons):
        if addon.module.startswith(prefix) and addon.module not in wanted:
            prefs.addons.remove(addon)

    bpy.utils.refresh_script_paths()


def _enable_addons(extensions, legacy):
    """Enable every add-on the bundle ships.

    default_set=True records them in the preferences, which add-ons need: they read their own
    settings through context.preferences.addons[...], and the preferences UI lists only those entries.
    """
    addon_utils.modules(refresh=True)
    names = [_extension_name(name) for name in extensions] + legacy
    for name in names:
        try:
            addon_utils.enable(name, default_set=True, handle_error=lambda exc: traceback.print_exc())
        except Exception:
            traceback.print_exc()
        print("TLS pipeline: add-on", "enabled" if addon_utils.check(name)[1] else "NOT loaded", name)


def _enable_addons_after_startup(extensions, legacy):
    """Extensions can't be enabled inside register(): Blender creates the bl_ext namespace and loads
    extension repositories only after startup scripts run. The first load_post (the startup file) is
    early enough that nothing else has been used yet, and is one-shot.
    """
    if not (extensions or legacy):
        return

    @bpy.app.handlers.persistent
    def on_load_post(*_args):
        if on_load_post in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(on_load_post)
        try:
            _enable_addons(extensions, legacy)
        except Exception:
            traceback.print_exc()

    bpy.app.handlers.load_post.append(on_load_post)


def _set_splash(release_root):
    splash = os.path.join(release_root, SPLASH_FILE)
    if os.path.isfile(splash):
        os.environ[SPLASH_VARIABLE] = splash


def _about_lines():
    try:
        message = importlib.import_module("tls_pipeline.about").text("blender")
    except Exception:
        message = "THE LINE pipeline\n\nNo pipeline bundle is loaded in this session."
    return message.splitlines()


class TLS_PIPELINE_OT_about(bpy.types.Operator):
    bl_idname = "tls_pipeline.about"
    bl_label = "About THE LINE Pipeline"
    bl_description = "Show which pipeline release this Blender session is running"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        for line in _about_lines():
            self.layout.label(text=line)


def _draw_about_item(self, context):
    self.layout.separator()
    self.layout.operator(TLS_PIPELINE_OT_about.bl_idname, icon="INFO")


def _register_about():
    """Help > About THE LINE Pipeline. Only when a bundle is loaded, so Help stays clean otherwise."""
    if not hasattr(bpy.types, "TLS_PIPELINE_OT_about"):
        bpy.utils.register_class(TLS_PIPELINE_OT_about)
        bpy.types.TOPBAR_MT_help.append(_draw_about_item)


def register():
    try:
        series = "{}.{}".format(*bpy.app.version[:2])  # "5.2"
        release = _load_pipeline().start("blender", series)
        if release is None:  # not enabled in the local config
            return
        release_root = str(release.release_root)
        _set_splash(release_root)
        extensions_dir, extensions, legacy = _shipped_addons(release_root)
        _expose_release(release_root, extensions_dir, extensions)
        _enable_addons_after_startup(extensions, legacy)
        _register_about()
    except Exception:
        traceback.print_exc()
        print("TLS pipeline: failed to localise for blender")


def unregister():
    try:
        bpy.types.TOPBAR_MT_help.remove(_draw_about_item)
        bpy.utils.unregister_class(TLS_PIPELINE_OT_about)
    except Exception:
        pass  # it was never added, e.g. the pipeline wasn't loaded
