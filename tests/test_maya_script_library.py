"""The Maya bundle's script library: scan folders into menu entries and run scripts. No Maya needed."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

LIBRARY = (
    Path(__file__).resolve().parent.parent
    / "structure" / "bundle_sources" / "maya" / "1.0.0" / "LineTools" / "scriptLibrary.py"
)
SHARED = Path(__file__).resolve().parent.parent / "structure" / "shared_sources"


def _load():
    sys.path.insert(0, str(SHARED))  # tls_common ships inside the bundle at publish time
    try:
        spec = importlib.util.spec_from_file_location("script_library_under_test", LIBRARY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SHARED))
    return module


@unittest.skipUnless(LIBRARY.is_file(), "maya bundle source not present")
class ScriptLibraryTests(unittest.TestCase):
    def setUp(self):
        self.lib = _load()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def touch(self, relative, text=""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_underscore_folders_list_at_top_level_before_submenus(self):
        self.touch("_scene/SetOverscanRes.py")
        self.touch("_global/playblastPlus.py")
        self.touch("anim/bakeToLocators.py")
        library = self.lib.scan(self.root)
        self.assertEqual(
            [(s.section, s.title) for s in library.top_level],
            [("_global", "Playblast Plus"), ("_scene", "Set Overscan Res")],
        )
        self.assertEqual([section.title for section in library.sections], ["Anim"])
        self.assertEqual(library.sections[0].scripts[0].title, "Bake To Locators")

    def test_sections_are_sorted_and_empty_or_hidden_folders_skipped(self):
        self.touch("rig/a.py")
        self.touch("Anim/b.py")
        self.touch("light/__init__.py")
        self.touch("model/notes.txt")
        self.touch("__pycache__/x.py")
        self.touch(".hidden/y.py")
        library = self.lib.scan(self.root)
        self.assertEqual([section.name for section in library.sections], ["Anim", "rig"])

    def test_only_py_and_mel_scripts_and_never_init(self):
        self.touch("tools/a.py")
        self.touch("tools/b.mel")
        self.touch("tools/__init__.py")
        self.touch("tools/c.zip")
        self.touch("tools/package/inner.py")
        library = self.lib.scan(self.root)
        self.assertEqual([s.file_name for s in library.sections[0].scripts], ["a.py", "b.mel"])

    def test_new_script_appears_on_next_scan(self):
        self.touch("tools/a.py")
        self.assertEqual(len(self.lib.scan(self.root).sections[0].scripts), 1)
        self.touch("tools/b.py")
        self.touch("newfolder/c.py")
        library = self.lib.scan(self.root)
        self.assertEqual([section.name for section in library.sections], ["newfolder", "tools"])
        self.assertEqual([len(section.scripts) for section in library.sections], [1, 2])

    def test_nice_names(self):
        self.assertEqual(self.lib.make_nice_name("playblastPlus"), "Playblast Plus")
        self.assertEqual(self.lib.make_nice_name("SetOverscanRes"), "Set Overscan Res")
        self.assertEqual(self.lib.make_nice_name("ig_EzRename"), "Ig Ez Rename")

    def test_run_script_runs_as_main(self):
        marker = self.root / "ran.txt"
        self.touch(
            "tools/a.py",
            'if __name__ == "__main__":\n    open(r"{}", "w").write("ok")\n'.format(marker),
        )
        self.lib.run_script("tools", "a.py", self.root)
        self.assertEqual(marker.read_text(), "ok")

    def test_run_script_logs_instead_of_raising(self):
        self.touch("tools/bad.py", "raise RuntimeError('boom')\n")
        with self.assertLogs("tls.maya.line_tools.library", level="ERROR"):
            result = self.lib.run_script("tools", "bad.py", self.root)
        self.assertEqual(result, self.lib.FAILED)

    def test_requirements_are_read_without_running_the_script(self):
        self.touch("a/list.py", 'REQUIRES = ["one", "two"]\nraise RuntimeError("must not run")\n')
        self.touch("a/dict.py", 'REQUIRES = {"dwpicker": "comes from AYON"}\n')
        self.touch("a/none.py", "x = 1\n")
        self.touch("a/dynamic.py", "REQUIRES = [name]\n")
        read = self.lib.read_requirements
        self.assertEqual(read(self.root / "a/list.py"), (("one", ""), ("two", "")))
        self.assertEqual(read(self.root / "a/dict.py"), (("dwpicker", "comes from AYON"),))
        self.assertEqual(read(self.root / "a/none.py"), ())
        self.assertEqual(read(self.root / "a/dynamic.py"), ())
        self.assertEqual(self.lib.scan(self.root).sections[0].scripts[0].requires, (("dwpicker", "comes from AYON"),))

    def test_declared_missing_module_is_reported_without_running_the_script(self):
        marker = self.root / "ran.txt"
        self.touch(
            "_global/picker.py",
            'REQUIRES = {{"tls_no_such_module": "comes from AYON"}}\n'
            'if __name__ == "__main__":\n    open(r"{}", "w").write("ran")\n'.format(marker),
        )
        messages = []
        with self.assertLogs("tls.maya.line_tools.library", level="WARNING") as logs:
            result = self.lib.run_script("_global", "picker.py", self.root, notify=messages.append)
        self.assertEqual(result, self.lib.MISSING)
        self.assertFalse(marker.exists())
        self.assertEqual(
            messages, ["picker needs 'tls_no_such_module', which isn't available in this session (comes from AYON)"]
        )
        self.assertNotIn("Traceback", logs.output[0])

    def test_undeclared_missing_import_is_still_a_clean_report(self):
        self.touch("tools/a.py", 'if __name__ == "__main__":\n    import tls_no_such_module\n')
        messages = []
        with self.assertLogs("tls.maya.line_tools.library", level="WARNING"):
            result = self.lib.run_script("tools", "a.py", self.root, notify=messages.append)
        self.assertEqual(result, self.lib.MISSING)
        self.assertIn("tls_no_such_module", messages[0])

    def test_declared_module_that_is_available_runs(self):
        marker = self.root / "ran.txt"
        self.touch("tools/a.py", 'REQUIRES = ["json"]\nopen(r"{}", "w").write("ok")\n'.format(marker))
        self.assertEqual(self.lib.run_script("tools", "a.py", self.root), self.lib.RAN)
        self.assertEqual(marker.read_text(), "ok")


if __name__ == "__main__":
    unittest.main()
