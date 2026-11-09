"""The host stubs find the pipeline root with the same rule as the core: TLS_PIPELINE, else the per-user install."""
import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from localiser.config import default_pipeline_root

BOOTSTRAP = Path(__file__).resolve().parents[1] / "structure" / "THE-LINE" / "pipeline" / "bootstrap"
STUBS = {
    "maya": BOOTSTRAP / "maya" / "userSetup.py",
    "nuke": BOOTSTRAP / "nuke" / "init.py",
    "blender": BOOTSTRAP / "blender" / "startup" / "tls_pipeline_startup.py",
}


def load_pipeline_root(stub: Path):
    """Pull `_pipeline_root` out of a stub without importing it (the stubs import DCC modules)."""
    tree = ast.parse(stub.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_pipeline_root")
    namespace = {"os": os, "sys": sys}
    exec(compile(ast.Module([function], []), str(stub), "exec"), namespace)
    return namespace["_pipeline_root"]


@unittest.skipUnless(all(stub.is_file() for stub in STUBS.values()), "host stubs not present")
class StubRootTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def install(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        (root / "config.json").write_text("{}", encoding="utf-8")

    def test_every_stub_prefers_the_variable(self):
        for name, stub in STUBS.items():
            with self.subTest(stub=name), patch.dict(os.environ, {"TLS_PIPELINE": str(self.tmp / "x")}, clear=True):
                self.assertEqual(load_pipeline_root(stub)(), str(self.tmp / "x"))

    def test_every_stub_falls_back_to_the_installed_default_and_exports_it(self):
        env = {"LOCALAPPDATA": str(self.tmp / "Local"), "XDG_DATA_HOME": str(self.tmp / "data")}
        with patch("sys.platform", "win32"):
            expected = default_pipeline_root(env, "win32")
        self.install(expected)
        for name, stub in STUBS.items():
            with self.subTest(stub=name), patch("sys.platform", "win32"), patch.dict(os.environ, env, clear=True):
                self.assertEqual(Path(load_pipeline_root(stub)()), expected)
                self.assertEqual(os.environ["TLS_PIPELINE"], str(expected))

    def test_every_stub_agrees_with_the_core_on_each_platform(self):
        home = self.tmp / "home"
        for platform, env in (
            ("darwin", {"HOME": str(home)}),
            ("linux", {"HOME": str(home)}),
            ("linux", {"HOME": str(home), "XDG_DATA_HOME": str(self.tmp / "xdg")}),
        ):
            expected = default_pipeline_root(env, platform)
            self.install(expected)
            for name, stub in STUBS.items():
                with self.subTest(platform=platform, stub=name), patch("sys.platform", platform), \
                        patch.dict(os.environ, env, clear=True), \
                        patch("os.path.expanduser", lambda path: str(home) if path == "~" else path):
                    self.assertEqual(Path(load_pipeline_root(stub)()), expected)

    def test_a_missing_installation_is_a_clear_error_not_a_guess(self):
        for name, stub in STUBS.items():
            with self.subTest(stub=name), patch("sys.platform", "win32"), \
                    patch.dict(os.environ, {"LOCALAPPDATA": str(self.tmp / "empty")}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "no pipeline installed"):
                    load_pipeline_root(stub)()


if __name__ == "__main__":
    unittest.main()
