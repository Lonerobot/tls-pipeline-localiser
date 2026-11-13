import sys
from pathlib import Path

# Shared packages (tls_common) sit in <bundle>/modules. The stub adds that folder to Blender's script
# directories only after this entry has run, so make it importable here.
modules = str(Path(__file__).resolve().parent.parent / "modules")
if modules not in sys.path:
    sys.path.append(modules)

from tls_common import BlenderLogger  # noqa: E402

BlenderLogger.info("Blender host initialized")