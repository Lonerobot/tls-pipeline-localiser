"""Launching a host: finding its program, building the child environment, and starting it detached."""
import json
import os
import subprocess
import sys
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

from localiser import ReleaseUnavailableError, sync_release
from localiser.errors import LocaliserError
from localiser.hosts import find_executable
from localiser.launch import launch_environment, launch_host
from localiser.python_runtime import find_python_home

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

    def prepare_harmony(self):
        self.publish("harmony", "1.0", {"__init__.py": ""})
        self.write_studio_config({"harmony": {"24": "1.0"}})
        sync_release("harmony", "24", self.config, {})
        home = self.tmp / "Python39"
        touch(home / "python.exe")
        touch(home / "python39.dll")
        return home

    def test_harmony_finds_external_python_without_it_being_on_path(self):
        home = self.prepare_harmony()
        local = self.tmp / "user"
        standard = local / "Programs" / "Python" / "Python39"
        standard.parent.mkdir(parents=True)
        home.rename(standard)
        base = {"TLS_PIPELINE": str(self.pipeline), "LOCALAPPDATA": str(local), "PATH": "existing"}
        before = dict(base)
        with patch("localiser.python_runtime._registered_python_homes", return_value=[]), patch(
            "localiser.python_runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "3.9:64\n", "")
        ) as probe:
            env = launch_environment("harmony", "24", self.config, base)
        self.assertEqual(probe.call_args.args[0][:3], [str(standard / "python.exe"), "-I", "-S"])
        self.assertEqual(env["PYTHON_LIB_PATH"], str(standard))
        self.assertEqual(env["PATH"], str(standard) + os.pathsep + "existing")
        self.assertEqual(env["TOONBOOM_GLOBAL_SCRIPT_LOCATION"], str(self.pipeline / "bootstrap" / "harmony"))
        self.assertEqual(base, before)

    def test_harmony_local_python_override_wins_over_the_inherited_environment(self):
        home = self.prepare_harmony()
        config = replace(self.config, python_homes={"harmony": home})
        base = {
            "TLS_PIPELINE": str(self.pipeline), "PYTHON_LIB_PATH": str(self.tmp / "wrong"),
            "PATH": "existing", "PYTHONPATH": "custom modules",
        }
        with patch(
            "localiser.python_runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "3.9:64\n", "")
        ):
            env = launch_environment("harmony", "24", config, base)
        self.assertEqual(env["PYTHON_LIB_PATH"], str(home))
        self.assertEqual(env["PYTHONPATH"], "custom modules")

    def test_missing_harmony_python_prevents_launch_with_an_actionable_error(self):
        self.prepare_harmony()
        with patch("localiser.python_runtime._candidate_homes", return_value=[]), patch("subprocess.Popen") as popen:
            with self.assertRaisesRegex(LocaliserError, r"64-bit Python 3\.9.*python_homes.harmony"):
                launch_host("harmony", "24", self.config, {"TLS_PIPELINE": str(self.pipeline)}, ["HarmonyPremium.exe"])
        popen.assert_not_called()

    def test_other_hosts_keep_their_python_environment_and_do_not_probe_for_a_runtime(self):
        for host, series in (("maya", SERIES), ("blender", "5.2"), ("nuke", "17.0")):
            with self.subTest(host=host):
                if host != "maya":
                    self.publish(host, "1.0", {"__init__.py": ""})
                self.write_studio_config({host: {series: "1.0"}})
                sync_release(host, series, self.config, {})
                base = {"TLS_PIPELINE": str(self.pipeline), "PATH": "existing", "PYTHON_LIB_PATH": "keep"}
                with patch("localiser.launch.find_python_home") as find:
                    env = launch_environment(host, series, self.config, base)
                find.assert_not_called()
                self.assertEqual((env["PATH"], env["PYTHON_LIB_PATH"]), ("existing", "keep"))

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


class ExternalPythonTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.home = self.tmp / "Python39"
        touch(self.home / "python.exe")
        touch(self.home / "python39.dll")

    def test_an_existing_python_lib_path_is_validated_and_used(self):
        with patch(
            "localiser.python_runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "3.9:64\n", "")
        ):
            self.assertEqual(find_python_home("3.9", None, {"PYTHON_LIB_PATH": str(self.home)}), self.home)

    def test_python_on_path_is_found_after_registered_and_standard_locations(self):
        with patch("localiser.python_runtime._registered_python_homes", return_value=[]), patch(
            "localiser.python_runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "3.9:64\n", "")
        ):
            self.assertEqual(find_python_home("3.9", None, {"PATH": str(self.home)}), self.home)

    def test_a_registered_runtime_is_found_without_path(self):
        with patch("localiser.python_runtime._registered_python_homes", return_value=[self.home]), patch(
            "localiser.python_runtime.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "3.9:64\n", "")
        ):
            self.assertEqual(find_python_home("3.9", None, {}), self.home)

    def test_a_wrong_version_or_architecture_in_an_explicit_folder_never_falls_back(self):
        for reported in ("3.14:64\n", "3.9:32\n"):
            with self.subTest(reported=reported), patch(
                "localiser.python_runtime.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, reported, ""),
            ), patch("localiser.python_runtime._candidate_homes") as candidates:
                with self.assertRaisesRegex(LocaliserError, "required 3.9:64"):
                    find_python_home("3.9", self.home, {})
                candidates.assert_not_called()

    def test_an_explicit_runtime_missing_its_dll_is_rejected(self):
        (self.home / "python39.dll").unlink()
        with self.assertRaisesRegex(LocaliserError, "must contain python.exe and python39.dll"):
            find_python_home("3.9", self.home, {})

    def test_a_failed_or_unresponsive_runtime_is_reported(self):
        for result in (
            subprocess.CompletedProcess([], 1, "", "runtime failed"),
            subprocess.TimeoutExpired("python.exe", 10),
        ):
            with self.subTest(result=result), patch("localiser.python_runtime.subprocess.run") as probe:
                if isinstance(result, subprocess.TimeoutExpired):
                    probe.side_effect = result
                else:
                    probe.return_value = result
                with self.assertRaisesRegex(LocaliserError, "Invalid external Python 3.9"):
                    find_python_home("3.9", self.home, {})


if __name__ == "__main__":
    unittest.main()
