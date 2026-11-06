import json
import unittest

from localiser import (
    ConfigError,
    ReleaseUnavailableError,
    ensure_local_release,
    expose_environment,
    host_variable,
    localise,
)
from localiser.layout import DataLayout
from localiser.resolve import SOURCE_LAST_KNOWN, SOURCE_OVERRIDE, SOURCE_STUDIO, override_variable

from .helpers import SERIES, WorkstationTestCase


class LocaliseTests(WorkstationTestCase):
    def go(self, host="maya", environ=None, series=SERIES):
        return localise(host, series, self.config, {} if environ is None else environ)

    def test_end_to_end_studio_selection(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0", {"tool.py": "X = 1\n"})
        result = self.go()
        self.assertEqual((result.host, result.release_id, result.source), ("maya", "2.9.0", SOURCE_STUDIO))
        self.assertEqual((result.python_root / "tool.py").read_text(), "X = 1\n")
        self.assertEqual(result.release_root, self.data / "hosts" / "maya" / "2.9.0")

    def test_dcc_series_picks_a_different_bundle_for_the_same_host(self):
        self.write_studio_config({"maya": {"2025": "0.9.0", "2026": "1.0.0"}})
        self.publish("maya", "0.9.0")
        self.publish("maya", "1.0.0")
        self.assertEqual(self.go("maya", series="2025").release_id, "0.9.0")
        self.assertEqual(self.go("maya", series="2026").release_id, "1.0.0")

    def test_repeat_launch_returns_same_release(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0")
        self.assertEqual(self.go(), self.go())

    def test_ensure_local_release_finds_config_through_tls_pipeline(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0")
        root = self.tmp / "pipeline"
        root.mkdir()
        (root / "config.json").write_text(
            json.dumps(
                {"schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data)}
            )
        )
        self.assertEqual(ensure_local_release("maya", SERIES, {"TLS_PIPELINE": str(root)}).release_id, "2.9.0")

    def test_unset_or_empty_tls_pipeline_says_install_is_required(self):
        for environ in [{}, {"TLS_PIPELINE": "  "}]:
            with self.subTest(environ=environ), self.assertRaises(ConfigError) as raised:
                ensure_local_release("maya", SERIES, environ)
            self.assertIn("installation or repair", str(raised.exception))

    def test_missing_config_says_install_is_required(self):
        with self.assertRaises(ConfigError) as raised:
            ensure_local_release("maya", SERIES, {"TLS_PIPELINE": str(self.tmp / "nowhere")})
        self.assertIn("installation or repair", str(raised.exception))

    def test_expose_environment_sets_the_resolved_path_for_that_host_only(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0")
        environ = {}
        expose_environment(self.go(), environ)
        self.assertEqual(environ, {"TLS_PIPELINE_MAYA": str(self.data / "hosts" / "maya" / "2.9.0")})
        self.assertEqual(host_variable("nuke"), "TLS_PIPELINE_NUKE")

    def test_offline_launch_after_caching_still_works(self):
        config = self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0")
        first = self.go()
        config.unlink()
        for path in sorted((self.repo / "hosts").rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        second = self.go()
        self.assertEqual(second.release_root, first.release_root)
        self.assertEqual(second.source, SOURCE_LAST_KNOWN)

    def test_override_pulls_missing_release_without_changing_other_hosts(self):
        self.write_studio_config({"maya": "2.9.0", "nuke": "3.2.4"})
        self.publish("maya", "2.9.0")
        self.publish("maya", "2.8.0")
        self.publish("nuke", "3.2.4")
        self.go("nuke")
        nuke_state = DataLayout(self.data).host_state_file("nuke").read_text()
        result = self.go("maya", {override_variable("maya"): "2.8.0"})
        self.assertEqual((result.release_id, result.source), ("2.8.0", SOURCE_OVERRIDE))
        self.assertEqual(DataLayout(self.data).host_state_file("nuke").read_text(), nuke_state)

    def test_missing_override_fails_and_never_falls_back_to_studio_default(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.publish("maya", "2.9.0")
        with self.assertRaises(ReleaseUnavailableError) as raised:
            self.go("maya", {override_variable("maya"): "0.0.1"})
        self.assertIn("release=0.0.1", str(raised.exception))

    def test_per_host_state_files_are_separate(self):
        self.write_studio_config({"maya": "2.9.0", "nuke": "3.2.4"})
        self.publish("maya", "2.9.0")
        self.publish("nuke", "3.2.4")
        self.go("maya")
        self.go("nuke")
        layout = DataLayout(self.data)
        self.assertEqual(json.loads(layout.host_state_file("maya").read_text())["release_id"], "2.9.0")
        self.assertEqual(json.loads(layout.host_state_file("nuke").read_text())["release_id"], "3.2.4")

    def test_changing_one_host_leaves_other_hosts_release_untouched(self):
        self.write_studio_config({"maya": "2.9.0", "blender": "1.0.0"})
        self.publish("maya", "2.9.0")
        self.publish("blender", "1.0.0")
        blender = self.go("blender")
        self.write_studio_config({"maya": "3.0.0", "blender": "1.0.0"})
        self.publish("maya", "3.0.0")
        self.assertEqual(self.go("maya").release_id, "3.0.0")
        self.assertEqual(self.go("blender"), blender)


if __name__ == "__main__":
    unittest.main()
