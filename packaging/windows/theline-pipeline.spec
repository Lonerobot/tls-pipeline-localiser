import sys
from importlib.metadata import distribution
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
PIPELINE = ROOT / "structure" / "THE-LINE" / "pipeline"
BOOTSTRAP = PIPELINE / "bootstrap"
CORE = ROOT / "src" / "localiser"


def license_file(package, filename):
    dist = distribution(package)
    matches = [
        item
        for item in dist.files or ()
        if str(item).replace("\\", "/").lower().endswith(f".dist-info/licenses/{filename.lower()}")
    ]
    if not matches:
        raise FileNotFoundError(f"{package} license file was not found: {filename}")
    return str(dist.locate_file(matches[0]))


bootstrap_datas = [
    (
        str(path),
        (Path("pipeline") / "bootstrap" / path.relative_to(BOOTSTRAP).parent).as_posix(),
    )
    for path in BOOTSTRAP.rglob("*")
    if path.is_file()
    and "__pycache__" not in path.relative_to(BOOTSTRAP).parts
    and path.suffix not in (".pyc", ".pyo")
]
core_datas = [
    (str(path), (Path("localiser") / path.relative_to(CORE).parent).as_posix())
    for path in CORE.rglob("*.py")
    if "__pycache__" not in path.relative_to(CORE).parts
]
datas = [
    (str(PIPELINE / "__init__.py"), "pipeline"),
    (str(PIPELINE / "about.py"), "pipeline"),
    (str(ROOT / "src" / "localiser" / "icons"), "localiser/icons"),
    (license_file("PySide6", "LicenseRef-Qt-Commercial.txt"), "ThirdPartyLicenses/Qt"),
    (license_file("PyInstaller", "COPYING.txt"), "ThirdPartyLicenses/PyInstaller"),
    (str(Path(sys.base_prefix) / "LICENSE.txt"), "ThirdPartyLicenses/Python"),
] + bootstrap_datas + core_datas + copy_metadata("tls-pipeline-localiser")

if not (Path(sys.base_prefix) / "LICENSE.txt").is_file():
    raise FileNotFoundError(f"Python license file was not found: {Path(sys.base_prefix) / 'LICENSE.txt'}")

a = Analysis(
    [str(ROOT / "packaging" / "windows" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TheLinePipeline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TheLinePipeline",
)
