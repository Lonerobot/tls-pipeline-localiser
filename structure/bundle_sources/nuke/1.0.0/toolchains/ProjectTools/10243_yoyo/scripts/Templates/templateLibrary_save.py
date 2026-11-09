import nuke
import os
import shutil
import glob

TEMPLATE_ROOT = r"Y:/TOOLS/CompTools/nuke/nukeTemplates"

def get_destinations():
    return [(name, os.path.join(TEMPLATE_ROOT, name)) for name in os.listdir(TEMPLATE_ROOT) if os.path.isdir(os.path.join(TEMPLATE_ROOT, name))]

def configure_write_node(write_node, mp4_path):
    write_node["file"].setValue(mp4_path.replace("\\", "/"))
    write_node["file_type"].setValue("mov")
    write_node["mov64_format"].setValue("mp4 (MP4 (MPEG-4 Part 14))")
    write_node["mov64_codec"].setValue("h264")
    write_node["mov_h264_codec_profile"].setValue("High 4:2:0 8-bit")
    write_node["mov64_pixel_format"].setValue(0)
    write_node["mov64_quality"].setValue("Custom")
    write_node["mov64_fast_start"].setValue(True)
    write_node["mov64_write_timecode"].setValue(True)
    write_node["mov64_gop_size"].setValue(12)
    write_node["mov64_b_frames"].setValue(0)
    write_node["mov64_bitrate"].setValue(28000)
    write_node["mov64_bitrate_tolerance"].setValue(0)
    write_node["mov64_quality_min"].setValue(1)
    write_node["mov64_quality_max"].setValue(3)
    write_node["checkHashOnRead"].setValue(False)
    write_node["create_directories"].setValue(True)
    cm = nuke.root()["colorManagement"].value()
    write_node["colorspace"].setValue("Output - sRGB" if cm == "OCIO" else "default")
    write_node["view"].setValue("sRGB")

def export_toolset_and_mp4():
    EXISTING_DESTINATIONS = get_destinations()
    existing_names = [name for name, path in EXISTING_DESTINATIONS]

    selected_nodes = nuke.selectedNodes()
    if not selected_nodes:
        nuke.message("Please select at least a Write node and Read nodes.")
        return

    write_node = next((node for node in selected_nodes if node.Class() == "Write"), None)
    if not write_node:
        nuke.message("Please select a Write node to export.")
        return

    p = nuke.Panel("Export Toolset and MP4")
    p.addSingleLineInput("Filename", "")
    p.addEnumerationPulldown("Destination", " ".join(existing_names))
    p.addSingleLineInput("Start Frame", str(int(nuke.root()["first_frame"].value())))
    p.addSingleLineInput("End Frame", str(int(nuke.root()["last_frame"].value())))
    if not p.show(): return

    filename = p.value("Filename").strip().replace(" ", "_").capitalize()
    dest_path = dict(EXISTING_DESTINATIONS).get(p.value("Destination"))

    start_frame = int(p.value("Start Frame"))
    end_frame = int(p.value("End Frame"))

    mp4_path = os.path.join(dest_path, f"{filename}.mp4").replace("\\", "/")
    toolset_path = os.path.join(dest_path, f"{filename}.nk")
    asset_dir = os.path.join(dest_path, f"{filename}_assets").replace("\\", "/")

    old_input = write_node.input(0)
    reformat = nuke.nodes.Reformat(format="HD_1080", pbb=True)
    reformat.setInput(0, old_input)
    write_node.setInput(0, reformat)

    configure_write_node(write_node, mp4_path)

    try:
        nuke.execute(write_node.name(), start_frame, end_frame)
    except Exception as e:
        nuke.message(f"Render failed: {e}")

    write_node.setInput(0, old_input)
    nuke.delete(reformat)

    os.makedirs(asset_dir, exist_ok=True)

    # Just copy the assets - do not change file paths
    reads = [node for node in nuke.allNodes('Read')]
    for read in reads:
        orig_value = read['file'].value()
        pattern = orig_value.replace('%04d','*').replace('%08d','*').replace('####','*')
        if '*' in pattern:
            for f in glob.glob(pattern):
                shutil.copy2(f, os.path.join(asset_dir, os.path.basename(f)))
        elif os.path.exists(read['file'].evaluate()):
            shutil.copy2(read['file'].evaluate(), os.path.join(asset_dir, os.path.basename(read['file'].evaluate())))

    try:
        for n in nuke.allNodes():
            n['selected'].setValue(False)
        for n in selected_nodes:
            n['selected'].setValue(True)
        nuke.nodeCopy(toolset_path)
    except Exception as e:
        nuke.message(f"Error saving .nk: {e}")

    nuke.delete(write_node)
    nuke.message(f"Export completed: Rendered, assets copied, toolset saved. Read file paths unchanged.")
