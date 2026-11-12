"""Cloning a bundle into the dev folder, and launching a host from a clone."""
import json
import sys
from unittest.mock import patch

from localiser import (
    PublishError,
    ReleaseUnavailableError,
    clone_bundle,
    get_override,
    installed_releases,
    list_clones,
    set_override,
    startup_release,
    sync_release,
)
from localiser.launch import launch_environment
from localiser.layout import CLONE_MARKER, DataLayout
from localiser.sync import source_variable

from .helpers import SERIES, WorkstationTestCase


class CloneTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = self.tmp / "pipeline"
        self.pipeline.mkdir()
        (self.pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
        }), encoding="utf-8")
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0", {"__init__.py": "VALUE = 'published'\n", "tool/a.py": "X = 1\n"})
        self.dev = DataLayout(self.data).dev / "maya"

    def source_folder(self, files=None):
        folder = self.tmp / "work" / "2.0"
        for relative, text in (files or {"__init__.py": "VALUE = 'source'\n"}).items():
            (folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (folder / relative).write_text(text, encoding="utf-8")
        return folder

    def test_cloning_a_release_copies_it_whole_and_marks_it_without_the_install_marker(self):
        clone = clone_bundle(self.config, "maya", "my-fix", release="1.0")
        self.assertEqual(clone, self.dev / "my-fix")
        self.assertEqual((clone / "tool" / "a.py").read_text(), "X = 1\n")
        self.assertFalse((clone / ".complete").exists())
        self.assertEqual(json.loads((clone / CLONE_MARKER).read_text())["python_root"], ".")
        self.assertEqual(list_clones(self.config, "maya"), ["my-fix"])
        self.assertEqual(installed_releases(self.config, "maya"), ["1.0"])

    def test_cloning_a_source_merges_the_shared_packages_like_a_publish(self):
        shared = self.tmp / "shared"
        (shared / "tls_common").mkdir(parents=True)
        (shared / "tls_common" / "__init__.py").write_text("", encoding="utf-8")
        clone = clone_bundle(self.config, "maya", "2.0-wip", source=self.source_folder(), shared=[shared])
        self.assertTrue((clone / "tls_common" / "__init__.py").is_file())
        self.assertEqual((clone / "__init__.py").read_text(), "VALUE = 'source'\n")

    def test_a_blender_clone_keeps_its_entry_point(self):
        source = self.source_folder({"startup/__init__.py": ""})
        clone = clone_bundle(self.config, "blender", "x", source=source)
        self.assertEqual(json.loads((clone / CLONE_MARKER).read_text())["python_root"], "startup")
        release = startup_release("blender", "5.2", self.config, {source_variable("blender"): str(clone)})
        self.assertEqual(release.python_root, clone.resolve() / "startup")

    def test_an_existing_tag_a_bad_tag_or_an_unclear_source_is_refused_and_leaves_nothing(self):
        clone_bundle(self.config, "maya", "taken", release="1.0")
        (self.dev / "taken" / "tool" / "a.py").write_text("X = 99\n", encoding="utf-8")
        for kwargs, tag in (({"release": "1.0"}, "taken"), ({"release": "1.0"}, "../x"), ({}, "t"),
                            ({"release": "1.0", "source": self.source_folder()}, "t"), ({"release": "9.9"}, "t")):
            with self.subTest(tag=tag, kwargs=sorted(kwargs)), self.assertRaises(Exception):
                clone_bundle(self.config, "maya", tag, **kwargs)
        self.assertEqual((self.dev / "taken" / "tool" / "a.py").read_text(), "X = 99\n")  # never overwritten
        self.assertEqual(list_clones(self.config, "maya"), ["taken"])
        self.assertEqual(list((self.data / "staging").glob("clone__*")), [])

    def test_a_clone_is_not_a_release_and_changes_no_selection(self):
        sync_release("maya", SERIES, self.config, {})
        clone_bundle(self.config, "maya", "mine", release="1.0")
        self.assertEqual(installed_releases(self.config, "maya"), ["1.0"])

    # overrides

    def test_an_override_is_remembered_and_cleared(self):
        clone_bundle(self.config, "maya", "mine", release="1.0")
        set_override(self.config, "maya", SERIES, "mine")
        self.assertEqual(get_override(self.config, "maya", SERIES), "mine")
        self.assertIsNone(get_override(self.config, "maya", "2025"))
        set_override(self.config, "maya", SERIES, None)
        self.assertIsNone(get_override(self.config, "maya", SERIES))

    def test_an_override_must_name_an_existing_clone(self):
        with self.assertRaises(ReleaseUnavailableError):
            set_override(self.config, "maya", SERIES, "nothing")

    def test_a_launch_runs_the_overridden_clone_in_place(self):
        clone = clone_bundle(self.config, "maya", "mine", release="1.0")
        set_override(self.config, "maya", SERIES, "mine")
        env = launch_environment("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)})
        self.assertEqual(env[source_variable("maya")], str(clone))
        self.assertNotIn("TLS_PIPELINE_MAYA", env)  # the stub in the host exposes it

    def test_an_explicit_source_beats_the_override(self):
        clone_bundle(self.config, "maya", "mine", release="1.0")
        set_override(self.config, "maya", SERIES, "mine")
        source = self.source_folder()
        env = launch_environment(
            "maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline), source_variable("maya"): str(source)}
        )
        self.assertEqual(env[source_variable("maya")], str(source))

    def test_a_deleted_clone_stops_the_launch_instead_of_falling_back(self):
        import shutil

        clone = clone_bundle(self.config, "maya", "mine", release="1.0")
        set_override(self.config, "maya", SERIES, "mine")
        shutil.rmtree(clone)
        with patch("subprocess.Popen") as popen, self.assertRaisesRegex(ReleaseUnavailableError, "no longer exists"):
            from localiser.launch import launch_host

            launch_host("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)}, [sys.executable])
        popen.assert_not_called()

    def test_with_no_override_the_launch_is_unchanged(self):
        sync_release("maya", SERIES, self.config, {})
        env = launch_environment("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)})
        self.assertNotIn(source_variable("maya"), env)
        self.assertIn("TLS_PIPELINE_MAYA", env)
