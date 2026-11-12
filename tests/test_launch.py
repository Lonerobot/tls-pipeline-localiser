"""Launching a host: finding its program, building the child environment, and starting it detached."""
import json
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from localiser import ReleaseUnavailableError, sync_release
from localiser.errors import LocaliserError
from localiser.hosts import find_executable
from localiser.launch import launch_environment, launch_host

from .helpers import SERIES, WorkstationTestCase


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


class FindExecutableTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.roots = [self.tmp / "Program Files"]

    def test_each_host_has_its_program_in_its_own_layout(self):
        touch(self.roots[0] / "Autodesk" / "Maya2026" / "bin" / "maya.exe")
        touch(self.roots[0] / "Nuke17.0v3" / "Nuke17.0.exe")
        touch(self.roots[0] / "Blender Foundation" / "Blender 5.2" / "blender.exe")
        found = {host: find_executable(host, series, self.roots) for host, series in
                 (("maya", "2026"), ("nuke", "17.0"), ("blender", "5.2"))}
        self.assertEqual(found["maya"], self.roots[0] / "Autodesk" / "Maya2026" / "bin" / "maya.exe")
        self.assertEqual(found["nuke"], self.roots[0] / "Nuke17.0v3" / "Nuke17.0.exe")
        self.assertEqual(found["blender"], self.roots[0] / "Blender Foundation" / "Blender 5.2" / "blender.exe")

    def test_the_newest_patch_build_of_a_series_is_used(self):
        for build in ("v2", "v10", "v9"):
            touch(self.roots[0] / f"Nuke15.1{build}" / "Nuke15.1.exe")
        self.assertEqual(find_executable("nuke", "15.1", self.roots).parent.name, "Nuke15.1v10")

    def test_a_missing_version_or_program_is_none(self):
        touch(self.roots[0] / "Autodesk" / "Maya2025" / "bin" / "maya.exe")
        (self.roots[0] / "Autodesk" / "Maya2026").mkdir()  # folder but no program
        self.assertIsNone(find_executable("maya", "2026", self.roots))
        self.assertIsNone(find_executable("nope", "1", self.roots))
        self.assertIsNone(find_executable("blender", "5.2", [self.tmp / "nowhere"]))


class LaunchTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = self.tmp / "pipeline"
        self.pipeline.mkdir()
        (self.pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
        }), encoding="utf-8")
        self.write_studio_config({"maya": "1.0"})
        self.publish("maya", "1.0", {"__init__.py": "VALUE = 1\n"})
        self.config = self.make_config()

    def prepare(self):
        return sync_release("maya", SERIES, self.config, {})

    def test_the_environment_carries_the_root_the_bundle_and_the_bootstrap_folder(self):
        release = self.prepare()
        env = launch_environment("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)})
        self.assertEqual(env["TLS_PIPELINE"], str(self.pipeline))
        self.assertEqual(env["TLS_PIPELINE_MAYA"], str(release.release_root))
        self.assertEqual(env["PYTHONPATH"], str(self.pipeline / "bootstrap" / "maya"))

    def test_existing_search_paths_are_kept_after_the_bootstrap_folder(self):
        self.prepare()
        base = {"TLS_PIPELINE": str(self.pipeline), "PYTHONPATH": "C:/their/scripts"}
        env = launch_environment("maya", SERIES, self.config, base)
        self.assertEqual(env["PYTHONPATH"].split(";" if sys.platform.startswith("win") else ":")[1], "C:/their/scripts")
        self.assertEqual(base["PYTHONPATH"], "C:/their/scripts")  # the caller's mapping is not changed

    def test_nothing_persistent_is_written_and_the_process_environment_is_untouched(self):
        self.prepare()
        with patch.dict("os.environ", {"TLS_PIPELINE": str(self.pipeline)}, clear=True):
            launch_environment("maya", SERIES, self.config)
            import os

            self.assertEqual(set(os.environ), {"TLS_PIPELINE"})

    def test_an_unprepared_host_is_an_error_not_a_launch(self):
        with patch("subprocess.Popen") as popen, self.assertRaises(ReleaseUnavailableError):
            launch_host("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)}, [sys.executable])
        popen.assert_not_called()

    def test_a_host_that_is_not_installed_is_reported(self):
        self.prepare()
        with patch("localiser.launch.find_executable", return_value=None), self.assertRaisesRegex(LocaliserError, "not found"):
            launch_host("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)})

    def test_the_process_starts_without_waiting_and_sees_the_environment(self):
        release = self.prepare()
        output = self.tmp / "child.json"
        code = f"import json, os, pathlib; pathlib.Path({str(output)!r}).write_text(json.dumps(dict(os.environ)))"
        process = launch_host(
            "maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)}, [sys.executable, "-c", code]
        )
        self.assertEqual(process.wait(30), 0)
        end = time.monotonic() + 5
        while not output.exists() and time.monotonic() < end:
            time.sleep(0.05)
        env = json.loads(output.read_text())
        self.assertEqual(env["TLS_PIPELINE_MAYA"], str(release.release_root))
        self.assertEqual(env["PYTHONPATH"], str(self.pipeline / "bootstrap" / "maya"))

    def test_a_host_with_no_console_can_print_symbols_and_no_log_file_is_made(self):
        self.prepare()
        code = "print('toolchain \\u2550\\u2550 ok'); import sys; print('to stderr', file=sys.stderr)"
        process = launch_host(
            "maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)}, [sys.executable, "-c", code]
        )
        self.assertEqual(process.wait(30), 0)
        self.assertEqual(list((self.data / "logs").glob("launch-*")), [])

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows console flags")
    def test_the_host_gets_a_hidden_console_not_none_so_its_children_open_no_windows(self):
        self.prepare()
        with patch("subprocess.Popen") as popen:
            launch_host("maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline)}, ["maya.exe"])
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & subprocess.CREATE_NO_WINDOW)
        self.assertFalse(flags & subprocess.DETACHED_PROCESS)
    def test_the_encoding_a_caller_chose_is_kept(self):
        self.prepare()
        output = self.tmp / "enc.txt"
        code = f"import os, pathlib; pathlib.Path({str(output)!r}).write_text(os.environ['PYTHONIOENCODING'])"
        launch_host(
            "maya", SERIES, self.config, {"TLS_PIPELINE": str(self.pipeline), "PYTHONIOENCODING": "latin-1"},
            [sys.executable, "-c", code],
        ).wait(30)
        self.assertEqual(output.read_text(), "latin-1")


if __name__ == "__main__":
    unittest.main()
