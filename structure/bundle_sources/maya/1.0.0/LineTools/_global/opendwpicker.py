from pathlib import Path
import os

REQUIRES = {"dwpicker": "comes from the AYON tool descriptor"}

def show(): 
    """
    The script will make the following directory in the project if it doesn't already exist:
        - Y:\PROJECTS\{PROJECT NAME}\tools\dwPicker

    """
    ayon_server_root = os.getenv("AYON_PROJECT_ROOT_WORK")
    ayon_project = os.getenv("AYON_PROJECT_NAME")

    if ayon_server_root and ayon_project:
        base_path = Path(ayon_server_root) / ayon_project / "tools" / "dwPicker"

        if not base_path.exists():
            base_path.mkdir(parents=True)

        picker_path = base_path if base_path.exists() else None

        os.environ["DWPICKER_PROJECT_DIRECTORY"] = str(picker_path)

        picker_files = sorted(picker_path.glob("*.json"))
        if not picker_files:
            raise FileNotFoundError(f"No picker JSON files found in {picker_path}")

        import dwpicker
        dwpicker.show(pickers=[str(path) for path in picker_files])

if __name__ == "__main__":
    show()
