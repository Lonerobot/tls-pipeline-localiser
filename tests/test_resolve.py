import unittest

from localiser import ConfigError, ReleaseUnavailableError
from localiser.layout import DataLayout
from localiser.resolve import SOURCE_LAST_KNOWN, SOURCE_OVERRIDE, SOURCE_STUDIO, override_variable, resolve_release

from .helpers import SERIES, WorkstationTestCase


class ResolveTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.layout = DataLayout(self.data)

    def resolve(self, host="maya", environ=None, series=SERIES):
        return resolve_release(host, series, self.config, self.layout, environ or {})

    def test_studio_config_selects_release_per_host(self):
        self.write_studio_config({"maya": "2.9.0", "nuke": "3.2.4"})
        maya = self.resolve("maya")
        self.assertEqual((maya.release_id, maya.source, maya.series), ("2.9.0", SOURCE_STUDIO, SERIES))
        self.assertEqual(self.resolve("nuke").release_id, "3.2.4")

    def test_release_is_selected_per_dcc_series(self):
        self.write_studio_config({"maya": {"2025": "0.9.0", "2026": "1.0.0"}})
        self.assertEqual(self.resolve("maya", series="2025").release_id, "0.9.0")
        self.assertEqual(self.resolve("maya", series="2026").release_id, "1.0.0")

    def test_unlisted_series_is_an_error_not_a_fallback(self):
        self.write_studio_config({"maya": {"2026": "1.0.0"}})
        with self.assertRaises(ConfigError):
            self.resolve("maya", series="2027")

    def test_override_replaces_studio_default_for_that_host_only(self):
        self.write_studio_config({"maya": "2.9.0", "nuke": "3.2.4"})
        env = {override_variable("maya"): "2.8.0"}
        self.assertEqual(self.resolve("maya", env).release_id, "2.8.0")
        self.assertEqual(self.resolve("maya", env).source, SOURCE_OVERRIDE)
        self.assertEqual(self.resolve("nuke", env).release_id, "3.2.4")

    def test_override_does_not_need_the_share(self):
        resolution = self.resolve("maya", {override_variable("maya"): "1.0"})
        self.assertEqual(resolution.release_id, "1.0")

    def test_invalid_override_is_an_error_not_ignored(self):
        self.write_studio_config({"maya": "2.9.0"})
        with self.assertRaises(ConfigError):
            self.resolve("maya", {override_variable("maya"): "../escape"})

    def test_blank_override_is_ignored(self):
        self.write_studio_config({"maya": "2.9.0"})
        self.assertEqual(self.resolve("maya", {override_variable("maya"): "  "}).source, SOURCE_STUDIO)

    def test_offline_uses_last_known_good_config(self):
        path = self.write_studio_config({"maya": "2.9.0"})
        self.resolve()
        path.unlink()
        resolution = self.resolve()
        self.assertEqual((resolution.release_id, resolution.source), ("2.9.0", SOURCE_LAST_KNOWN))

    def test_offline_without_last_known_good_fails_clearly(self):
        with self.assertRaises(ReleaseUnavailableError) as raised:
            self.resolve()
        self.assertIn("host=maya", str(raised.exception))

    def test_malformed_config_never_falls_back_to_last_known_good(self):
        path = self.write_studio_config({"maya": "2.9.0"})
        self.resolve()
        path.write_text("{not json")
        with self.assertRaises(ConfigError):
            self.resolve()

    def test_unsupported_schema_is_an_error(self):
        path = self.write_studio_config({"maya": "2.9.0"})
        path.write_text('{"schema_version": 99, "hosts": {}}')
        with self.assertRaises(ConfigError):
            self.resolve()

    def test_host_missing_from_config(self):
        self.write_studio_config({"nuke": "3.2.4"})
        with self.assertRaises(ConfigError):
            self.resolve("maya")

    def test_last_known_good_only_stores_valid_config(self):
        path = self.write_studio_config({"maya": "2.9.0"})
        self.resolve()
        path.write_text("{not json")
        with self.assertRaises(ConfigError):
            self.resolve()
        self.assertIn("2.9.0", self.layout.last_known_config.read_text())


if __name__ == "__main__":
    unittest.main()
