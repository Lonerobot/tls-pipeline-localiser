"""Blender startup reconciles only pipeline-owned asset libraries."""
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_stub_root import STUBS


class AssetLibraries(list):
    def new(self, *, name, directory):
        library = SimpleNamespace(name=name, path=directory, import_method="APPEND", use_relative_path=True)
        self.append(library)
        return library


class BlenderAssetLibraryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.libraries = AssetLibraries()
        self.bpy = SimpleNamespace(
            types=SimpleNamespace(Operator=object),
            context=SimpleNamespace(preferences=SimpleNamespace(
                filepaths=SimpleNamespace(asset_libraries=self.libraries),
            )),
            app=SimpleNamespace(version=(5, 2, 0)),
        )
        with patch.dict(sys.modules, {"bpy": self.bpy, "addon_utils": Mock()}):
            self.stub = runpy.run_path(str(STUBS["blender"]))

    def library_folder(self, name):
        folder = self.root / "assets" / name
        folder.mkdir(parents=True)
        return str(folder)

    def reconcile(self):
        self.stub["_expose_asset_libraries"](str(self.root))

    def test_register_adds_only_prefixed_immediate_folders_and_is_repeatable(self):
        geometry = self.library_folder("TLP_Geometry")
        materials = self.library_folder("TLP_Materials")
        self.library_folder("Other")
        self.library_folder(os.path.join("Other", "TLP_Nested"))
        (self.root / "assets" / "TLP_NotADirectory.blend").touch()
        release = SimpleNamespace(release_root=self.root)
        start = Mock(return_value=release)
        register = self.stub["register"]
        with patch.dict(register.__globals__, {
            "_load_pipeline": lambda: SimpleNamespace(start=start),
            "_set_splash": Mock(),
            "_shipped_addons": Mock(return_value=("", [], [])),
            "_expose_release": Mock(),
            "_enable_addons_after_startup": Mock(),
            "_register_about": Mock(),
        }):
            register()
            register()

        self.assertEqual(
            [(entry.name, entry.path) for entry in self.libraries],
            [("TLP_Geometry", geometry), ("TLP_Materials", materials)],
        )
        for library in self.libraries:
            self.assertEqual(library.import_method, "LINK")
            self.assertFalse(library.use_relative_path)
            self.assertTrue(os.path.isabs(library.path))
        start.assert_called_with("blender", "5.2")

    def test_updates_paths_preserving_settings_and_removes_stale_and_duplicate_entries(self):
        materials = self.library_folder("TLP_Materials")
        personal = self.libraries.new(name="Personal", directory="user-assets")
        existing = self.libraries.new(name="TLP_Materials", directory="old-bundle-assets")
        existing.enabled = False
        self.libraries.new(name="TLP_Removed", directory="old-bundle-assets")
        self.libraries.new(name="TLP_Materials", directory="duplicate")

        self.reconcile()
        self.reconcile()

        self.assertEqual(len(self.libraries), 2)
        self.assertIs(self.libraries[0], personal)
        self.assertEqual(personal.path, "user-assets")
        self.assertEqual(personal.import_method, "APPEND")
        self.assertTrue(personal.use_relative_path)
        self.assertIs(self.libraries[1], existing)
        self.assertEqual(existing.path, materials)
        self.assertEqual(existing.import_method, "LINK")
        self.assertFalse(existing.use_relative_path)
        self.assertFalse(existing.enabled)

    def test_missing_or_empty_assets_clears_only_pipeline_entries(self):
        for has_assets in (False, True):
            with self.subTest(has_assets=has_assets):
                if has_assets:
                    (self.root / "assets").mkdir()
                self.libraries.clear()
                personal = self.libraries.new(name="Personal", directory="user-assets")
                self.libraries.new(name="TLP_Old", directory="old-bundle-assets")

                self.reconcile()

                self.assertEqual(self.libraries, [personal])
                self.assertEqual(personal.path, "user-assets")

    def test_scan_failure_is_not_treated_as_an_empty_bundle(self):
        existing = self.libraries.new(name="TLP_Materials", directory="old-bundle-assets")
        self.library_folder("TLP_Materials")
        with patch.object(os, "listdir", side_effect=PermissionError("assets inaccessible")):
            with self.assertRaises(PermissionError):
                self.reconcile()
        self.assertEqual(self.libraries, [existing])
        self.assertEqual(existing.path, "old-bundle-assets")


if __name__ == "__main__":
    unittest.main()
