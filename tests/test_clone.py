"""Cloning a bundle into the dev folder, and launching a host from a clone."""
import json
import sys
from dataclasses import replace
from unittest.mock import patch

from localiser import (
    PublishError,
    ReleaseUnavailableError,
    ZippedSourceError,
    available_releases,
    clone_bundle,
    find_zipped_bundle,
    get_override,
    installed_releases,
    list_clones,
    publish_to_repository,
    pull_release,
    set_override,
    startup_release,
    sync_release,
)
from localiser.launch import launch_environment
from localiser.layout import CLONE_MARKER, DataLayout
from localiser.repository import WebRepository
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

    def test_a_folder_of_nothing_is_refused_with_a_reason(self):
        empty = self.tmp / "empty"
        (empty / "sub").mkdir(parents=True)
        with self.assertRaisesRegex(PublishError, "no files"):
            clone_bundle(self.config, "maya", "x", source=empty)
        self.assertEqual(list_clones(self.config, "maya"), [])

    def test_a_zipped_bundle_is_detected_and_only_unzipped_when_asked(self):
        import zipfile

        published = self.repo / "hosts" / "maya" / "1.0"  # a release folder as it sits on the remote
        self.assertEqual(find_zipped_bundle(published), published / "pipeline.zip")
        self.assertEqual(find_zipped_bundle(published / "pipeline.zip"), published / "pipeline.zip")
        self.assertIsNone(find_zipped_bundle(self.source_folder()))
        with self.assertRaises(ZippedSourceError) as raised:
            clone_bundle(self.config, "maya", "z", source=published)
        self.assertEqual(raised.exception.archive, published / "pipeline.zip")
        self.assertEqual(list_clones(self.config, "maya"), [])
        clone = clone_bundle(self.config, "maya", "z", source=published, unzip=True)
        self.assertEqual((clone / "tool" / "a.py").read_text(), "X = 1\n")
        self.assertEqual(json.loads((clone / CLONE_MARKER).read_text())["origin"][:3], "zip")
        loose = self.tmp / "loose.zip"
        with zipfile.ZipFile(loose, "w") as archive:
            archive.writestr("__init__.py", "")
        self.assertEqual(find_zipped_bundle(loose), loose)

    def test_the_release_list_has_installed_published_and_studio_releases_with_the_default_marked(self):
        self.publish("maya", "1.1")  # published, not installed
        self.write_studio_config({"maya": {"2026": "1.1", "2025": "1.0"}})
        clone_bundle(self.config, "maya", "x", release="1.0")  # installs 1.0
        choices = {c.release_id: c for c in available_releases(self.config, "maya")}
        self.assertEqual(list(choices), ["1.1", "1.0"])  # newest first
        self.assertEqual((choices["1.1"].installed, choices["1.1"].studio_series), (False, ("2026",)))
        self.assertEqual((choices["1.0"].installed, choices["1.0"].studio_series), (True, ("2025",)))

    def test_the_release_list_still_works_offline_from_what_is_installed(self):
        clone_bundle(self.config, "maya", "x", release="1.0")
        (self.repo / "config.json").unlink()
        self.assertEqual([c.release_id for c in available_releases(self.config, "maya")], ["1.0"])

    # publishing

    def test_a_dev_bundle_is_published_as_it_is_without_the_clone_marker(self):
        import zipfile

        clone_bundle(self.config, "maya", "mine", release="1.0")
        (self.dev / "mine" / "tool" / "a.py").write_text("X = 2\n", encoding="utf-8")
        manifest, folder = publish_to_repository(self.config, "maya", "1.1", bundle="mine")
        self.assertEqual((manifest.package_id, manifest.release_id, manifest.python_root), ("maya", "1.1", "."))
        self.assertEqual(folder, self.repo / "hosts" / "maya" / "1.1")
        with zipfile.ZipFile(folder / "pipeline.zip") as archive:
            names = archive.namelist()
            self.assertNotIn(CLONE_MARKER, names)
            self.assertEqual(archive.read("tool/a.py").decode().strip(), "X = 2")
        self.assertEqual(self.config.remote_repository, self.repo)
        self.assertEqual(json.loads(self.read_config_studio())["hosts"]["maya"][SERIES]["bundle_version"], "1.0")  # not selected

    def read_config_studio(self):
        return (self.repo / "config.json").read_text(encoding="utf-8")

    def test_a_published_dev_bundle_installs_and_runs_like_any_release(self):
        clone_bundle(self.config, "blender", "b", source=self.source_folder({"startup/__init__.py": "VALUE = 'b'\n"}))
        publish_to_repository(self.config, "blender", "3.0", bundle="b")
        release = pull_release("blender", "3.0", self.config)
        self.assertEqual(release.python_root, release.release_root / "startup")
        self.assertEqual((release.python_root / "__init__.py").read_text(), "VALUE = 'b'\n")

    def test_a_source_folder_is_published_with_the_shared_packages_merged_in(self):
        shared = self.tmp / "shared"
        (shared / "tls_common").mkdir(parents=True)
        (shared / "tls_common" / "__init__.py").write_text("", encoding="utf-8")
        publish_to_repository(self.config, "maya", "2.0", source=self.source_folder(), shared=[shared])
        release = pull_release("maya", "2.0", self.config)
        self.assertTrue((release.release_root / "tls_common" / "__init__.py").is_file())
        self.assertEqual((release.release_root / "__init__.py").read_text(), "VALUE = 'source'\n")

    def test_a_dev_bundle_given_as_a_source_folder_is_published_as_a_bundle(self):
        clone = clone_bundle(self.config, "maya", "mine", release="1.0")
        publish_to_repository(self.config, "maya", "1.2", source=clone)
        self.assertTrue((pull_release("maya", "1.2", self.config).release_root / "tool" / "a.py").is_file())

    def test_publishing_refuses_what_it_cannot_do_and_changes_nothing(self):
        clone_bundle(self.config, "maya", "mine", release="1.0")
        before = sorted(p.name for p in (self.repo / "hosts" / "maya").iterdir())
        web = replace(self.config, remote_repository=WebRepository("https://example.com/p"))
        for kwargs, config in (
            ({"bundle": "mine"}, web),  # a web repository can't be published to
            ({"bundle": "nothing"}, self.config),  # no such dev bundle
            ({}, self.config),  # nothing chosen
            ({"bundle": "mine", "source": self.tmp}, self.config),  # both chosen
            ({"source": self.tmp / "nowhere"}, self.config),
            ({"source": self.tmp / "work"}, self.config),  # doesn't exist yet
        ):
            with self.subTest(kwargs=sorted(kwargs)), self.assertRaises(PublishError):
                publish_to_repository(config, "maya", "9.9", **kwargs)
        with self.assertRaises(PublishError):  # releases are immutable
            publish_to_repository(self.config, "maya", "1.0", bundle="mine")
        with self.assertRaises(Exception):
            publish_to_repository(self.config, "maya", "../x", bundle="mine")
        self.assertEqual(sorted(p.name for p in (self.repo / "hosts" / "maya").iterdir()), before)

    def test_a_zipped_source_is_not_published(self):
        published = self.repo / "hosts" / "maya" / "1.0"
        with self.assertRaises(ZippedSourceError):
            publish_to_repository(self.config, "maya", "1.5", source=published)

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
