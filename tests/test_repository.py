"""A web repository: the same layout as a share, served over http(s). A loopback test server stands in for it."""
import contextlib
import functools
import http.server
import json
import threading
import urllib.error
from pathlib import Path

from localiser import ConfigError, ReleaseUnavailableError, VerificationError, parse_local_config, sync_release
from localiser.__main__ import main
from localiser.layout import DataLayout
from localiser.repository import MAX_TEXT_BYTES, FolderRepository, WebRepository, as_repository, parse_web_url
from localiser.resolve import SOURCE_LAST_KNOWN, resolve_release

from .helpers import SERIES, WorkstationTestCase


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class WebRepositoryTests(WorkstationTestCase):
    """self.repo is the folder being published to and also what the test server serves."""

    def setUp(self):
        super().setUp()
        self.redirects = {}
        self.serve()

    def serve(self, port=0):
        outer = self

        class Handler(_Quiet):
            def do_GET(self):
                target = outer.redirects.get(self.path)
                if target:
                    self.send_response(302)
                    self.send_header("Location", target)
                    self.end_headers()
                    return
                super().do_GET()

        handler = functools.partial(Handler, directory=str(self.repo))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True).start()
        self.addCleanup(self.stop)
        return self.url

    def stop(self):
        with contextlib.suppress(Exception):
            self.server.shutdown()
            self.server.server_close()

    def web_config(self):
        return parse_local_config(
            json.dumps({"schema_version": 1, "remote_repository": self.url, "bundle_repository": str(self.data)}),
            self.tmp,
        )

    # reading

    def test_reads_text_and_files_by_relative_path(self):
        (self.repo / "config.json").write_text('{"x": 1}', encoding="utf-8")
        (self.repo / "bin.dat").write_bytes(b"\x00\x01" * 1000)
        repository = WebRepository(self.url)
        self.assertEqual(repository.read_text("config.json"), '{"x": 1}')
        target = self.tmp / "out.dat"
        repository.fetch("bin.dat", target)
        self.assertEqual(target.read_bytes(), b"\x00\x01" * 1000)

    def test_a_missing_file_is_an_oserror_like_a_missing_share_file(self):
        with self.assertRaises(OSError):
            WebRepository(self.url).read_text("nothing.json")

    def test_oversized_text_is_refused(self):
        (self.repo / "big.json").write_bytes(b"x" * (MAX_TEXT_BYTES + 10))
        with self.assertRaises(OSError):
            WebRepository(self.url).read_text("big.json")

    def test_relative_paths_cannot_escape_the_base(self):
        for relative in ["../x", "a/../b", "", "a//b", "a\\b"]:
            with self.subTest(relative=relative), self.assertRaises(OSError):
                WebRepository(self.url).url(relative)

    def test_redirects_to_unsafe_addresses_are_refused(self):
        (self.repo / "config.json").write_text("{}", encoding="utf-8")
        self.redirects["/config.json"] = "http://example.com/config.json"  # plain http, and not loopback
        with self.assertRaisesRegex(urllib.error.URLError, "refusing"):
            WebRepository(self.url).read_text("config.json")

    def test_redirects_to_safe_addresses_are_followed(self):
        (self.repo / "real.json").write_text('{"ok": true}', encoding="utf-8")
        self.redirects["/config.json"] = f"{self.url}/real.json"
        self.assertEqual(WebRepository(self.url).read_text("config.json"), '{"ok": true}')

    # address rules

    def test_only_https_or_loopback_http_addresses_are_accepted(self):
        self.assertEqual(parse_web_url("https://example.com/p/", "x"), "https://example.com/p")
        self.assertEqual(parse_web_url("http://localhost:9/p", "x"), "http://localhost:9/p")
        for value in ["http://example.com/p", "ftp://example.com", "https://u:p@example.com", "https://example.com?x=1"]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                parse_web_url(value, "x")

    def test_as_repository_accepts_folders_and_repositories(self):
        self.assertEqual(as_repository(self.repo), FolderRepository(self.repo))
        web = WebRepository(self.url)
        self.assertIs(as_repository(web), web)

    # the whole flow over http

    def test_sync_installs_and_selects_from_a_web_repository(self):
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0", {"__init__.py": "VALUE = 'web'\n"})
        release = sync_release("maya", SERIES, self.web_config(), {})
        self.assertEqual(release.release_id, "1.0")
        self.assertEqual((release.python_root / "__init__.py").read_text(), "VALUE = 'web'\n")

    def test_a_tampered_zip_over_http_fails_the_checksum(self):
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0")
        zip_path = self.repo / "hosts" / "maya" / "1.0" / "pipeline.zip"
        zip_path.write_bytes(zip_path.read_bytes() + b"tampered")
        with self.assertRaises(VerificationError):
            sync_release("maya", SERIES, self.web_config(), {})
        self.assertFalse(DataLayout(self.data).release_dir("maya", "1.0").exists())

    def test_unreleased_version_is_a_clear_unavailable_error(self):
        self.write_studio_config({"maya": "9.9"})
        with self.assertRaises(ReleaseUnavailableError):
            sync_release("maya", SERIES, self.web_config(), {})

    def test_server_down_falls_back_to_the_last_known_config(self):
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0")
        config = self.web_config()
        sync_release("maya", SERIES, config, {})
        self.stop()
        resolution = resolve_release("maya", SERIES, config, DataLayout(self.data), {})
        self.assertEqual((resolution.release_id, resolution.source), ("1.0", SOURCE_LAST_KNOWN))

    def test_server_down_with_nothing_cached_fails_clearly(self):
        self.stop()
        with self.assertRaisesRegex(ReleaseUnavailableError, "unreachable"):
            resolve_release("maya", SERIES, self.web_config(), DataLayout(self.data), {})

    def test_publish_refuses_a_web_remote_without_a_folder(self):
        pipeline = self.tmp / "pipeline"
        pipeline.mkdir()
        (pipeline / "config.json").write_text(
            json.dumps({"schema_version": 1, "remote_repository": self.url, "bundle_repository": str(self.data)}),
            encoding="utf-8",
        )
        source = self.tmp / "src"
        source.mkdir()
        (source / "a.py").write_text("x = 1\n", encoding="utf-8")
        import contextlib as cl, io
        with cl.redirect_stderr(io.StringIO()) as errors:
            status = main(["--pipeline", str(pipeline), "publish", str(source), "maya", "1.0"])
        self.assertEqual(status, 2)
        self.assertIn("web address", errors.getvalue())


if __name__ == "__main__":
    import unittest

    unittest.main()
