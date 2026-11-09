import json
import unittest
from pathlib import Path

from localiser import ConfigError, parse_local_config, parse_manifest, parse_studio_config
from localiser.config import validate_id, validate_python_root, validate_series
from localiser.repository import WebRepository

SHA = "a" * 64


def manifest(**overrides):
    data = {
        "schema_version": 1,
        "package_id": "maya-tools",
        "release_id": "2.9.0",
        "artifact": "pipeline.zip",
        "sha256": SHA,
    }
    data.update(overrides)
    return json.dumps(data)


def studio(hosts, **extra):
    return json.dumps({"schema_version": 1, "hosts": hosts, **extra})


class StudioConfigTests(unittest.TestCase):
    def test_valid_nested_by_host_and_series(self):
        config = parse_studio_config(
            studio(
                {
                    "maya": {"2026": {"bundle_version": "1.0.0"}, "2025": {"bundle_version": "0.9.0"}},
                    "nuke": {"17.0": {"bundle_version": "1.0.0+dev"}},
                }
            )
        )
        self.assertEqual(config.bundle_version("maya", "2026"), "1.0.0")
        self.assertEqual(config.bundle_version("maya", "2025"), "0.9.0")
        self.assertEqual(config.bundle_version("nuke", "17.0"), "1.0.0+dev")

    def test_comment_keys_are_ignored(self):
        config = parse_studio_config(
            studio({"maya": {"2026": {"bundle_version": "1.0.0"}}}, _comment_hosts="notes")
        )
        self.assertEqual(config.bundle_version("maya", "2026"), "1.0.0")

    def test_missing_host_or_series_is_an_error_naming_what_exists(self):
        config = parse_studio_config(studio({"maya": {"2026": {"bundle_version": "1.0.0"}}}))
        with self.assertRaises(ConfigError) as raised:
            config.bundle_version("maya", "2027")
        self.assertIn("available: 2026", str(raised.exception))
        with self.assertRaises(ConfigError):
            config.bundle_version("nuke", "17.0")

    def test_rejects_bad_input(self):
        good = {"bundle_version": "1.0.0"}
        bad = [
            "not json",
            "[]",
            '{"hosts": {}}',
            '{"schema_version": 2, "hosts": {}}',
            '{"schema_version": true, "hosts": {}}',
            '{"schema_version": 1, "hosts": []}',
            studio({"Maya": {"2026": good}}),
            studio({"maya": []}),
            studio({"maya": {"../x": good}}),
            studio({"maya": {"2026": "1.0.0"}}),
            studio({"maya": {"2026": {}}}),
            studio({"maya": {"2026": {"bundle_version": "../evil"}}}),
            studio({"maya": {"2026": {"bundle_version": 5}}}),
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ConfigError):
                parse_studio_config(text)


class ManifestTests(unittest.TestCase):
    def test_valid_defaults_python_root(self):
        parsed = parse_manifest(manifest())
        self.assertEqual(parsed.python_root, ".")
        self.assertEqual(parsed.sha256, SHA)

    def test_round_trip(self):
        parsed = parse_manifest(manifest(python_root="core"))
        self.assertEqual(parse_manifest(parsed.to_json()), parsed)

    def test_rejects_bad_fields(self):
        bad = [
            manifest(sha256="xyz"),
            manifest(sha256="a" * 63),
            manifest(artifact="sub/pipeline.zip"),
            manifest(artifact="..\\pipeline.zip"),
            manifest(artifact=".."),
            manifest(release_id="../x"),
            manifest(package_id="a/b"),
            manifest(python_root="/abs"),
            manifest(python_root="../up"),
            manifest(python_root="C:\\x"),
            manifest(schema_version=9),
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ConfigError):
                parse_manifest(text)


class ValidationTests(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(validate_id("1.14.0", "x"), "1.14.0")
        for value in ["", ".", "..", "a/b", "a\\b", "-lead", "x" * 200, None, 3]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_id(value, "id")

    def test_python_root_normalised(self):
        self.assertEqual(validate_python_root("core/./sub"), "core/sub")
        self.assertEqual(validate_python_root("."), ".")


    def test_series(self):
        for value in ["2026", "5.2", "17.0"]:
            self.assertEqual(validate_series(value), value)
        for value in ["", "17.0v3 ", "a/b", "..", None, 5]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_series(value)


class LocalConfigTests(unittest.TestCase):
    base = Path(__file__).resolve().anchor + "pipeline-root"

    def parse(self, **fields):
        return parse_local_config(json.dumps({"schema_version": 1, **fields}), Path(self.base))

    def test_relative_paths_resolve_against_the_config_folder(self):
        config = self.parse(remote_repository="./fake_remote_repository")
        self.assertEqual(config.remote_repository, Path(self.base) / "fake_remote_repository")
        self.assertEqual(config.bundle_repository, Path(self.base) / "bundles")

    def test_absolute_paths_are_kept(self):
        remote = Path(__file__).resolve().anchor + "share"
        config = self.parse(remote_repository=remote, bundle_repository=remote + "-local")
        self.assertEqual(config.remote_repository, Path(remote))
        self.assertEqual(config.bundle_repository, Path(remote + "-local"))

    def test_file_urls_are_disc_paths(self):
        remote = Path(self.base) / "share"
        self.assertEqual(self.parse(remote_repository=remote.as_uri()).remote_repository, remote)

    def test_https_addresses_are_web_repositories(self):
        self.assertEqual(
            self.parse(remote_repository="https://example.com/pipeline/").remote_repository,
            WebRepository("https://example.com/pipeline"),
        )
        self.assertEqual(
            self.parse(remote_repository="http://127.0.0.1:8080").remote_repository, WebRepository("http://127.0.0.1:8080")
        )

    def test_unsafe_or_unsupported_addresses_are_rejected(self):
        for value in [
            "http://example.com", "ftp://host/x", "https://user:pw@example.com/p", "https://example.com/p?x=1",
            "https://example.com/p#frag", "https:///nohost",
        ]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.parse(remote_repository=value)

    def test_the_local_store_must_be_a_folder(self):
        with self.assertRaises(ConfigError):
            self.parse(remote_repository="./x", bundle_repository="https://example.com/local")

    def test_drive_letters_are_not_mistaken_for_urls(self):
        self.assertEqual(self.parse(remote_repository="D:/share").remote_repository.name, "share")

    def test_rejects_bad_input(self):
        for text in ["not json", '{"remote_repository": "x"}', '{"schema_version": 1}', '{"schema_version": 1, "remote_repository": ""}']:
            with self.subTest(text=text), self.assertRaises(ConfigError):
                parse_local_config(text, Path(self.base))


if __name__ == "__main__":
    unittest.main()
