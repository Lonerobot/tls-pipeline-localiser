import nuke
import os
from templateLibrary_load import import_mp4s_to_contact_sheet
from templateLibrary_save import export_toolset_and_mp4

# Hardcoded root where all template categories live
TEMPLATE_ROOT = r"Y:/TOOLS/CompTools/nuke/nukeTemplates"

def get_template_folders():
    """Scans TEMPLATE_ROOT and returns a list of (folder_name, full_path)"""
    folders = []
    for name in os.listdir(TEMPLATE_ROOT):
        full_path = os.path.join(TEMPLATE_ROOT, name)
        if os.path.isdir(full_path):
            folders.append((name, full_path))
    return folders

def create_custom_menu():
    MENU_NAME = "Template Library"
    SUBICON_PATH = "icons/my_sub_icon.png"

    menu_bar = nuke.menu("Nuke")
    custom_menu = menu_bar.addMenu(MENU_NAME)
    custom_menu.addCommand("Save", export_toolset_and_mp4, icon=SUBICON_PATH)

    load_submenu = custom_menu.addMenu("Load", icon=SUBICON_PATH)

    for label, path in get_template_folders():
        load_submenu.addCommand(label, lambda p=path, l=label: import_mp4s_to_contact_sheet(p, l), icon=SUBICON_PATH)

create_custom_menu()
