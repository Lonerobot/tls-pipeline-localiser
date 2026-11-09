"""AYON-managed plates/reviews, organised into shot columns in Nuke.

Run in Nuke launched by AYON. No server writes; uses installed AYON loaders.
"""
import copy
import html
import json
import re
import traceback
from collections import defaultdict

import nuke

META = "tl_shot_board_meta"
SETTINGS = "tl_shot_board_settings"
REPORT = "tl_shot_board_report"
MENU = "The Line/AYON Shot Board"
_BUSY = False

DEFAULTS = {
    "scope": "/shots",
    "shot_type": "Shot",
    "versions": "Latest",
    "plate": True,
    "review": True,
    "start_at_workfile": True,
    "add_retime": True,
    "loaders": ["LoadClip", "LoadImage"],
    "plate_formats": ["exr", "dpx", "tif", "tiff", "png", "mov", "mp4", "jpg", "jpeg"],
    "review_formats": ["mov", "mp4", "jpg", "jpeg", "png", "exr"],
}


def natural(value):
    return tuple((1, int(p)) if p.isdigit() else (0, p.casefold())
                 for p in re.split(r"(\d+)", value or ""))


def chunks(items, size=200):
    items = list(items)
    for index in range(0, len(items), size):
        yield items[index:index + size]


def normal_path(path):
    return "/" + path.strip().replace("\\", "/").strip("/")


def in_scope(path, scope):
    path, scope = normal_path(path), normal_path(scope)
    return scope == "/" or path == scope or path.startswith(scope + "/")


def read_json(node, key, default=None):
    knob = node.knob(key)
    if knob is None:
        return default
    try:
        return json.loads(knob.value())
    except (ValueError, TypeError):
        raise RuntimeError("Invalid Shot Board metadata on " + node.fullName())


def write_json(node, key, value):
    knob = node.knob(key)
    if knob is None:
        knob = nuke.String_Knob(key, key)
        node.addKnob(knob)
        knob.setVisible(False)
    knob.setValue(json.dumps(value, sort_keys=True))


def tag(node, **data):
    write_json(node, META, data)


def label(text):
    # Prevent names containing brackets from becoming Tcl expressions.
    return html.escape(str(text)).replace("[", "&#91;").replace("]", "&#93;")


def dependencies():
    import ayon_api
    from ayon_core.pipeline import get_current_project_name
    from ayon_core.pipeline.load import (
        discover_loader_plugins, get_representation_contexts,
        is_compatible_loader, load_with_repre_context,
    )
    from ayon_nuke.api import ls
    project = get_current_project_name()
    if not project:
        raise RuntimeError("Launch Nuke from AYON in the target project first.")
    return {
        "api": ayon_api, "project": project, "ls": ls,
        "discover": discover_loader_plugins,
        "contexts": get_representation_contexts,
        "compatible": is_compatible_loader,
        "load": load_with_repre_context,
    }


def shot_for_folder(folder, folders, config):
    """Find nearest Shot ancestor, including products under shot subfolders."""
    seen = set()
    while folder and folder["id"] not in seen:
        seen.add(folder["id"])
        if not in_scope(folder["path"], config["scope"]):
            return None
        if folder.get("folderType", "").casefold() == config["shot_type"].casefold():
            return folder
        folder = folders.get(folder.get("parentId"))
    return None


def collect(config, deps, progress):
    """Query published entities in batches, without changing the script."""
    api, project = deps["api"], deps["project"]
    progress.setMessage("Reading AYON folders...")
    folders = {f["id"]: f for f in api.get_folders(
        project, fields={"id", "name", "path", "parentId", "folderType"}
    )}
    shots = {}
    for folder in folders.values():
        shot = shot_for_folder(folder, folders, config)
        if shot:
            shots[folder["id"]] = shot
    if not shots:
        raise RuntimeError("No folders of type {!r} under {}. Check the scope "
                           "and Shot folder type.".format(
                               config["shot_type"], config["scope"]))
    products = {}
    for batch in chunks(shots):
        if progress.isCancelled():
            return [], ["Scan cancelled."], True
        for product in api.get_products(project, folder_ids=batch):
            kind = product.get("productBaseType") or product.get("productType")
            if kind in ("plate", "review") and config[kind]:
                products[product["id"]] = product
    versions = {}
    for batch in chunks(products):
        if progress.isCancelled():
            return [], ["Scan cancelled."], True
        if config["versions"] == "Latest":
            found = api.get_last_versions(project, batch).values()
        else:
            found = api.get_versions(project, product_ids=batch, hero=False)
        for version in found:
            if version and version.get("active", True) and version["version"] >= 0:
                versions[version["id"]] = version
    by_version = defaultdict(list)
    for batch in chunks(versions):
        if progress.isCancelled():
            return [], ["Scan cancelled."], True
        for repre in api.get_representations(project, version_ids=batch):
            by_version[repre["versionId"]].append(repre)

    loaders = {loader.__name__: loader for loader in deps["discover"]()
               if getattr(loader, "enabled", True)
               and loader.__name__ in config["loaders"]}
    if not loaders:
        raise RuntimeError("No enabled LoadClip/LoadImage loaders were found. "
                           "Check AYON Nuke loader settings.")
    contexts = {}
    for batch in chunks([r for items in by_version.values() for r in items]):
        if progress.isCancelled():
            return [], ["Scan cancelled."], True
        contexts.update(deps["contexts"](project, batch))

    result, skipped = [], []
    for version in versions.values():
        product = products[version["productId"]]
        kind = product.get("productBaseType") or product.get("productType")
        shot = shots[product["folderId"]]
        formats = config[kind + "_formats"]
        choices = []
        for repre in by_version[version["id"]]:
            context = contexts.get(repre["id"])
            if not context or not all(context.get(k) for k in (
                    "project", "folder", "product", "version", "representation")):
                continue
            ext = (repre.get("context", {}).get("ext") or
                   repre["name"]).lower().lstrip(".")
            if ext not in formats:
                continue
            for rank, loader_name in enumerate(config["loaders"]):
                loader = loaders.get(loader_name)
                if loader and deps["compatible"](loader, context):
                    choices.append((formats.index(ext), rank, repre["name"],
                                    repre["id"], repre, loader, context))
        if not choices:
            skipped.append("{} | {} v{:03d}: no supported representation/"
                           "enabled compatible loader".format(
                               shot["path"], product["name"], version["version"]))
            continue
        choice = min(choices, key=lambda c: c[:4])
        result.append({
            "shot": shot, "product": product, "version": version, "kind": kind,
            "representation": choice[4], "loader": choice[5], "context": choice[6],
        })
    result.sort(key=lambda item: (
        natural(item["shot"]["path"]), natural(item["product"]["name"]),
        item["version"]["version"],
    ))
    return result, skipped, False


def inventory(deps):
    """Use live AYON IDs so Scene Inventory changes do not leave stale IDs."""
    return {str(c["representation"]) for c in deps["ls"]()
            if c.get("representation")
            and c.get("project_name", deps["project"]) == deps["project"]}


def extent(node):
    if node.Class() == "BackdropNode":
        return int(node["bdwidth"].value()), int(node["bdheight"].value())
    if node.Class() == "StickyNote":
        return max(360, node.screenWidth()), max(150, node.screenHeight())
    return max(100, node.screenWidth()), max(70, node.screenHeight())


def bounds(nodes):
    return (min(n.xpos() for n in nodes), min(n.ypos() for n in nodes),
            max(n.xpos() + extent(n)[0] for n in nodes),
            max(n.ypos() + extent(n)[1] for n in nodes))


def deselect():
    for node in nuke.selectedNodes():
        node["selected"].setValue(False)


def board_backdrop(project, shot, created):
    matches = []
    for node in nuke.allNodes():
        data = read_json(node, META, {})
        if (data.get("project") == project and data.get("shot_id") == shot["id"]
                and data.get("role") == "backdrop"):
            matches.append(node)
    if len(matches) > 1:
        raise RuntimeError("Duplicate board backdrops for " + shot["path"] +
                           ". Remove the duplicate backdrop before updating.")
    if matches:
        return matches[0]
    nodes = nuke.allNodes()
    x = bounds(nodes)[2] + 150 if nodes else 0
    y = min((n.ypos() for n in nodes), default=0)
    deselect()
    backdrop = nuke.nodes.BackdropNode(
        label=label(shot["path"]), note_font_size=32,
        tile_color=0x334B65FF, bdwidth=760, bdheight=400,
        xpos=x, ypos=y, z_order=-10,
    )
    created.append(backdrop)
    tag(backdrop, role="backdrop", project=project, shot_id=shot["id"])
    return backdrop


def place_bundle(item, nodes, primary, deps, created):
    project, shot = deps["project"], item["shot"]
    backdrop = board_backdrop(project, shot, created)
    members = []
    for node in nuke.allNodes():
        data = read_json(node, META, {})
        if (data.get("project") == project and data.get("shot_id") == shot["id"]
                and data.get("role") in ("member", "note")):
            members.append(node)
    x = backdrop.xpos() + 60
    y = max((n.ypos() + extent(n)[1] for n in members),
            default=backdrop.ypos() + 100) + 80
    # Lay out just this new loader bundle; do not reposition existing nodes.
    nodes = sorted(nodes, key=lambda n: (n is not primary, n.ypos(), n.xpos()))
    top = y
    for node in nodes:
        node.setXYpos(x, y)
        y += extent(node)[1] + 70
        tag(node, role="member", project=project, shot_id=shot["id"])
    version = item["version"]
    text = "{}\n{}\nv{:03d} | {}\n{}\n{}".format(
        item["product"]["name"], item["kind"], version["version"],
        item["representation"]["name"], version.get("status") or "",
        version.get("author") or "")
    deselect()
    note = nuke.nodes.StickyNote(
        label=label(text), note_font_size=18, xpos=x + 220, ypos=top,
        tile_color=(0xA9803EFF if item["kind"] == "review" else 0x467E68FF),
    )
    created.append(note)
    tag(note, role="note", project=project, shot_id=shot["id"])
    members += nodes + [note]
    _, _, right, bottom = bounds(members)
    backdrop["bdwidth"].setValue(max(int(backdrop["bdwidth"].value()),
                                      right - backdrop.xpos() + 60))
    backdrop["bdheight"].setValue(max(int(backdrop["bdheight"].value()),
                                       bottom - backdrop.ypos() + 60))


def load_item(item, config, deps):
    """Keep loader-created connections, metadata, colour and retime settings."""
    before = {n.fullName() for n in nuke.allNodes()}
    # Snapshot backdrop geometry to restore it if this asset fails.
    backdrops = [(n, n["bdwidth"].value(), n["bdheight"].value())
                 for n in nuke.allNodes() if n.Class() == "BackdropNode"]
    created = []
    try:
        deselect()
        # LoadClip caches script_start at module import in addon 0.4.15.
        # Use this script's actual start frame, then restore the class value.
        loader = item["loader"]
        old_start = getattr(loader, "script_start", None)
        try:
            if old_start is not None:
                loader.script_start = int(nuke.root()["first_frame"].value())
            returned = deps["load"](
                loader, copy.deepcopy(item["context"]),
                name=item["product"]["name"],
                namespace=item["shot"]["name"],
                options={
                    "set_frame_range": True,
                    "start_at_workfile": config["start_at_workfile"],
                    "add_retime": config["add_retime"],
                    "node_type": "Read",
                },
            )
        finally:
            if old_start is not None:
                loader.script_start = old_start
        created = [n for n in nuke.allNodes() if n.fullName() not in before]
        if not created:
            raise RuntimeError("Loader created no nodes.")
        containers = [c for c in deps["ls"]()
                      if str(c.get("representation")) ==
                      str(item["representation"]["id"])
                      and c.get("node") in created]
        if not containers:
            raise RuntimeError("Loader did not create a tracked AYON container.")
        primary = containers[0]["node"]
        place_bundle(item, list(created), primary, deps, created)
        return returned
    except Exception:
        # Only remove nodes created by this specific load attempt.
        for node in list(nuke.allNodes()):
            if node.fullName() not in before:
                nuke.delete(node)
        for node, width, height in backdrops:
            node["bdwidth"].setValue(width)
            node["bdheight"].setValue(height)
        raise


def run(config):
    deps = dependencies()
    if config["project"] != deps["project"]:
        raise RuntimeError("This board belongs to {}. Launch Nuke in that AYON "
                           "project to update it.".format(config["project"]))
    progress = nuke.ProgressTask("AYON Shot Board: scanning")
    items, skipped, cancelled = collect(config, deps, progress)
    del progress
    if cancelled:
        return
    with nuke.root():
        existing = inventory(deps)
        pending = [i for i in items if str(i["representation"]["id"]) not in existing]
        # Keep the selected scope, including when there is nothing new to load.
        write_json(nuke.root(), SETTINGS, config)
        selected = [n.fullName() for n in nuke.selectedNodes()]
        root_values = {k: nuke.root()[k].value()
                       for k in ("first_frame", "last_frame", "fps")}
        done, failures, stopped = [], [], False
        progress = nuke.ProgressTask("AYON Shot Board: importing")
        undo = nuke.Undo()
        undo.begin("AYON Shot Board")
        try:
            for index, item in enumerate(pending):
                if progress.isCancelled():
                    stopped = True
                    break
                desc = "{} | {} v{:03d}".format(
                    item["shot"]["path"], item["product"]["name"],
                    item["version"]["version"])
                progress.setMessage(desc)
                progress.setProgress(int(100 * index / max(1, len(pending))))
                try:
                    load_item(item, config, deps)
                    existing.add(str(item["representation"]["id"]))
                    done.append(desc)
                except Exception as exc:
                    failures.append(desc + ": " + str(exc))
                    nuke.tprint(traceback.format_exc())
                finally:
                    for key, value in root_values.items():
                        nuke.root()[key].setValue(value)
        finally:
            undo.end()
            del progress
            for key, value in root_values.items():
                nuke.root()[key].setValue(value)
            deselect()
            for name in selected:
                node = nuke.toNode(name)
                if node is not None:
                    node["selected"].setValue(True)
        report = (
            "AYON Shot Board | {} | {} | {} versions\n"
            "Loaded: {}\nAlready present: {}\nUnsupported: {}\nFailed: {}\n"
            "Cancelled during import: {}\n\n"
            "LOADED\n{}\n\nUNSUPPORTED\n{}\n\nFAILED\n{}"
        ).format(config["project"], config["scope"], config["versions"],
                 len(done), len(items) - len(pending), len(skipped),
                 len(failures), stopped, "\n".join(done) or "-",
                 "\n".join(skipped) or "-", "\n".join(failures) or "-")
        write_json(nuke.root(), REPORT, report)
        nuke.tprint(report)
        nuke.message(report[:2400] + (
            "\n\nFull report is in the Script Editor." if len(report) > 2400 else ""))


def configure():
    deps = dependencies()
    config = copy.deepcopy(DEFAULTS)
    stored = read_json(nuke.root(), SETTINGS)
    if stored:
        config.update(stored)
    if stored and stored["project"] != deps["project"]:
        raise RuntimeError("Open a separate script for a different project.")
    panel = nuke.Panel("AYON Shot Board — " + deps["project"])
    panel.setWidth(620)
    panel.addSingleLineInput("Folder scope", config["scope"])
    panel.addSingleLineInput("Shot folder type", config["shot_type"])
    choices = "Latest All" if config["versions"] == "Latest" else "All Latest"
    panel.addEnumerationPulldown("Versions", choices)
    panel.addBooleanCheckBox("Include plates", config["plate"])
    panel.addBooleanCheckBox("Include reviews", config["review"])
    panel.addBooleanCheckBox("Align clips to script start", config["start_at_workfile"])
    panel.addBooleanCheckBox("Load published retimes", config["add_retime"])
    if not panel.show():
        return
    config.update(
        project=deps["project"],
        scope=normal_path(panel.value("Folder scope")),
        shot_type=panel.value("Shot folder type").strip(),
        versions=panel.value("Versions"),
        plate=bool(panel.value("Include plates")),
        review=bool(panel.value("Include reviews")),
        start_at_workfile=bool(panel.value("Align clips to script start")),
        add_retime=bool(panel.value("Load published retimes")),
    )
    if not config["shot_type"] or not (config["plate"] or config["review"]):
        raise RuntimeError("Choose a shot folder type and at least one product type.")
    run(config)


def update():
    config = read_json(nuke.root(), SETTINGS)
    if config is None:
        configure()
    else:
        run(config)


def show_report():
    report = read_json(nuke.root(), REPORT, "No import report saved in this script.")
    nuke.tprint(report)
    nuke.message(report[:2400])


def dispatch(command):
    global _BUSY
    if _BUSY:
        return
    _BUSY = True
    try:
        command()
    except Exception as exc:
        nuke.tprint(traceback.format_exc())
        nuke.message("AYON Shot Board\n\n" + str(exc))
    finally:
        _BUSY = False


def install():
    if not nuke.GUI:
        return
    menu = nuke.menu("Nuke")
    for title, fn in (("Build or Configure", configure),
                      ("Update — Add Missing", update),
                      ("Show Last Report", show_report)):
        path = MENU + "/" + title
        if menu.findItem(path):
            menu.removeItem(path)
        menu.addCommand(path, lambda command=fn: dispatch(command))
