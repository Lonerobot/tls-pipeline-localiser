import os
import sys
from pathlib import Path

import nuke

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.append(str(root))  # shared packages (tls_common) sit at the bundle root

from tls_common import NukeLogger  # noqa: E402

# Runtime logs belong beside the localised releases (<bundles>/hosts/nuke/<release>), not inside one.
logs = root.parent.parent.parent / "logs"
if logs.is_dir():
    os.environ.setdefault("TLS_LOG_DIR", str(logs))

# Nuke runs core/init.py once this entry returns, and core/menu.py when the UI loads.
nuke.pluginAddPath(str(root / "core"))
NukeLogger.info("Nuke pipeline core added: %s", root / "core")
