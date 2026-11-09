import nuke
import os
import shutil
import glob

def is_script_saved():
    script_path = nuke.root().name()
    return script_path and script_path != "Root" and os.path.isfile(script_path)

def get_script_dir():
    if is_script_saved():
        return os.path.dirname(nuke.root().name()).replace("\\", "/")
    return ""

def copy_read_file(read_node, assets_dir):
    original_value = read_node["file"].value()
    evaluated_path = read_node["file"].evaluate()

    pattern = original_value
    for token in ["%04d", "%05d", "%06d", "%08d", "####"]:
        pattern = pattern.replace(token, "*")

    copied_any = False

    if "*" in pattern:
        for src in glob.glob(pattern):
            dst = os.path.join(assets_dir, os.path.basename(src)).replace("\\", "/")
            shutil.copy2(src, dst)
            copied_any = True

        new_path = os.path.join(assets_dir, os.path.basename(original_value)).replace("\\", "/")
        read_node["file"].setValue(new_path)

    elif os.path.exists(evaluated_path):
        dst = os.path.join(assets_dir, os.path.basename(evaluated_path)).replace("\\", "/")
        shutil.copy2(evaluated_path, dst)

        read_node["file"].setValue(dst)
        copied_any = True

    if not copied_any:
        nuke.tprint("Warning: could not copy file for: {}".format(original_value))

def collect_files():
    reads = nuke.allNodes("Read")

    if not reads:
        nuke.message("No Read nodes found.")
        return

    script_was_saved = is_script_saved()
    default_location = get_script_dir()

    p = nuke.Panel("Collect files")
    p.addBooleanCheckBox("Save As", False)
    p.addSingleLineInput("Collect Location", default_location)

    if not p.show():
        return

    save_as = p.value("Save As")
    collect_location = p.value("Collect Location").strip()

    if save_as or not script_was_saved:
        nuke.scriptSaveAs()

    if not collect_location:
        collect_location = get_script_dir()

    if not collect_location:
        nuke.message("No collection location set.")
        return

    assets_dir = os.path.join(collect_location, "assets").replace("\\", "/")
    os.makedirs(assets_dir, exist_ok=True)

    for read in reads:
        copy_read_file(read, assets_dir)

    nuke.scriptSave()

    nuke.message("Files collected to:\n{}".format(assets_dir))

collect_files()