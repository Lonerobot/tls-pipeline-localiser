from pathlib import Path
import os

def show(): 
    """
    This file is to be placed in your global scripts/ maya env directory so that it can be called from the internal pype script menu definition.

    The script will make the following directory in the project if it doesn't already exist:
        - Y:\PROJECTS\{PROJECT NAME}\tools\studiolibrary

    Now using Pathlib from Python 3+ instead of os.path for better compatibility.
    """
    ayon_server_root = os.getenv("AYON_PROJECT_ROOT_WORK")
    ayon_project = os.getenv("AYON_PROJECT_NAME")

    if ayon_server_root and ayon_project:
        base_path = Path(ayon_server_root) / ayon_project / "tools" / "studiolibrary"

        if not base_path.exists():
            base_path.mkdir(parents=True)

        template_path = base_path if base_path.exists() else None

    if template_path:
        import studiolibrary
        studiolibrary.main(name=f"Project Library - {ayon_project}", path=str(template_path))

if __name__ == "__main__":
    show()
