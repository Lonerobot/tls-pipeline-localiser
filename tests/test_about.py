"""The About text a host shows: built from the environment variables the pipeline entry sets."""
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "structure" / "THE-LINE" / "pipeline" / "about.py"


def load():
    spec = importlib.util.spec_from_file_location("about_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AboutTests(unittest.TestCase):
    def setUp(self):
        self.about = load()
        self.env = {
            "TLS_PIPELINE": r"C:\Pipeline",
            "TLS_PIPELINE_NUKE": r"C:\Pipeline\bundles\hosts\nuke\1.1.0",
            "TLS_PIPELINE_NUKE_RELEASE": "1.1.0",
            "TLS_PIPELINE_NUKE_MODE": "studio",
        }

    def test_identity_reads_the_release_mode_and_paths_for_that_host(self):
        info = self.about.identity("nuke", self.env)
        self.assertEqual(
            info,
            {"host": "nuke", "release": "1.1.0", "mode": "studio", "root": r"C:\Pipeline",
             "path": r"C:\Pipeline\bundles\hosts\nuke\1.1.0"},
        )

    def test_another_hosts_variables_are_not_picked_up(self):
        self.assertIsNone(self.about.identity("maya", self.env))

    def test_a_missing_or_blank_release_means_nothing_is_loaded(self):
        self.assertIsNone(self.about.identity("nuke", {}))
        self.assertIsNone(self.about.identity("nuke", {"TLS_PIPELINE_NUKE_RELEASE": "  "}))

    def test_the_text_names_the_release_and_where_it_came_from(self):
        text = self.about.text("nuke", self.env)
        self.assertIn("Release:  1.1.0", text)
        self.assertIn("studio default", text)
        self.assertIn(r"C:\Pipeline\bundles\hosts\nuke\1.1.0", text)

    def test_pinned_and_dev_sessions_say_so(self):
        for mode, words in (("pinned", "not the studio default"), ("dev", "unpublished source")):
            with self.subTest(mode=mode):
                self.assertIn(words, self.about.text("nuke", {**self.env, "TLS_PIPELINE_NUKE_MODE": mode}))

    def test_an_unknown_mode_is_shown_as_it_is_and_a_missing_one_means_studio(self):
        self.assertIn("odd", self.about.text("nuke", {**self.env, "TLS_PIPELINE_NUKE_MODE": "odd"}))
        del self.env["TLS_PIPELINE_NUKE_MODE"]
        self.assertIn("studio default", self.about.text("nuke", self.env))

    def test_with_no_bundle_the_text_says_so_instead_of_failing(self):
        text = self.about.text("blender", {})
        self.assertIn("No pipeline bundle is loaded", text)
        self.assertIn("Blender", text)
