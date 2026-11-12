import nuke
from image.PasteFromClipboard import paste_clipboard_image

 #Create a command with no visible menu entry
shortcut = "ctrl+shift+v"
nuke.menu("Nuke").addCommand("","paste_clipboard_image()",f"{shortcut}")

from utils.PipelineLogger import get_logger
logger = get_logger("Toolchain")
logger.info(f"[TheLine] Shortcut registered : paste_clipboard_image [{shortcut}]")