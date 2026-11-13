"""Exercise the installer's first-run code without installing the application."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from localiser.config import load_local_config

INSTALLER = Path(__file__).resolve().parents[1] / "packaging" / "windows" / "TheLinePipeline.iss"


def inno_compiler():
    compiler = shutil.which("ISCC.exe")
    if compiler:
        return Path(compiler)
    for variable, folder in (
        ("LOCALAPPDATA", "Programs"),
        ("ProgramFiles(x86)", ""),
        ("ProgramFiles", ""),
    ):
        base = os.environ.get(variable)
        if base:
            candidate = Path(base) / folder / "Inno Setup 6" / "ISCC.exe"
            if candidate.is_file():
                return candidate
    return None


@unittest.skipUnless(sys.platform == "win32" and inno_compiler(), "requires Windows and Inno Setup 6")
class WindowsInstallerTests(unittest.TestCase):
    def test_first_run_defaults_preserve_existing_configs_and_report_creation_errors(self):
        with tempfile.TemporaryDirectory(prefix="theline-installer-test-") as directory:
            work = Path(directory)
            root = work / "fresh-d\u00e9fault" / "TheLine" / "pipeline"
            existing_root = work / "existing"
            existing_root.mkdir()
            existing_file = existing_root / "config.json"
            existing = json.dumps({
                "schema_version": 1,
                "remote_repository": "custom-remote",
                "bundle_repository": "br3",
                "_comment": "preserve exactly",
            }).encode("utf-8")
            existing_file.write_bytes(existing)
            blocked = work / "blocked"
            blocked.write_text("not a directory", encoding="utf-8")
            marker = work / "passed"

            def quoted(path):
                return "'" + str(path).replace("'", "''") + "'"

            code = INSTALLER.read_text(encoding="utf-8").split("[Code]", 1)[1]
            harness = work / "test.iss"
            harness.write_text(
                "[Setup]\n"
                "AppName=THE LINE installer defaults test\n"
                "AppVersion=1\n"
                "CreateAppDir=no\n"
                "Uninstallable=no\n"
                "PrivilegesRequired=lowest\n"
                "OutputBaseFilename=test\n"
                f"OutputDir={work}\n"
                "[Code]\n" + code + "\n"
                "function InitializeSetup(): Boolean;\n"
                "var\n"
                "  Raised: Boolean;\n"
                "begin\n"
                f"  InitializePipelineConfig({quoted(root)});\n"
                f"  InitializePipelineConfig({quoted(root)});\n"
                f"  InitializePipelineConfig({quoted(existing_root)});\n"
                "  Raised := False;\n"
                "  try\n"
                f"    InitializePipelineConfig({quoted(blocked)});\n"
                "  except\n"
                "    Raised := True;\n"
                "  end;\n"
                "  if not Raised then RaiseException('Expected directory creation to fail');\n"
                f"  if not SaveStringToFile({quoted(marker)}, 'passed', False) then\n"
                "    RaiseException('Could not write test marker');\n"
                "  Result := False;\n"
                "end;\n",
                encoding="utf-8-sig",
            )
            compiled = subprocess.run(
                [str(inno_compiler()), "/Q", str(harness)], capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            log = work / "setup.log"
            ran = subprocess.run(
                [str(work / "test.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertTrue(marker.is_file(), log.read_text(encoding="utf-8-sig") if log.exists() else ran.stderr)
            config = load_local_config(root / "config.json", {})
            self.assertEqual(config.remote_repository, Path(r"P:\pipeline\repository"))
            self.assertEqual(config.bundle_repository, root / "bundles")
            self.assertTrue(config.bundle_repository.is_dir())
            self.assertEqual(existing_file.read_bytes(), existing)
            self.assertFalse((existing_root / "bundles").exists())
