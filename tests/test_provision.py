"""Per-user host entries: idempotent, never overwriting what isn't ours, removed cleanly."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from localiser import host_enabled, parse_local_config, provision, unprovision
from localiser.__main__ import main
from localiser.provision import (
    ABSENT,
    BLOCK_BEGIN,
    BLOCK_END,
    CREATED,
    REMOVED,
    UNCHANGED,
    UPDATED,
    blender_scripts_dir,
    maya_app_dir,
    provision_blender,
    provision_maya,
    provision_nuke,
    remove_blender,
    remove_maya,
    remove_nuke,
)

from .helpers import WorkstationTestCase


class ProvisionTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.tmp / "Pipeline Root"  # a space on purpose
        self.env = {
            "MAYA_APP_DIR": str(self.tmp / "maya"),
            "BLENDER_USER_SCRIPTS": str(self.tmp / "blender"),
            "APPDATA": str(self.tmp / "appdata"),
        }
        patcher = patch("pathlib.Path.home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    # Maya

    def test_maya_module_points_the_stub_folder_at_maya(self):
        action = provision_maya(self.root, self.env)
        self.assertEqual((action.host, action.change), ("maya", CREATED))
        self.assertEqual(action.path, self.tmp / "maya" / "modules" / "TheLinePipeline.mod")
        text = action.path.read_text()
        self.assertIn(f"+ TheLinePipeline 1.0 {self.root / 'bootstrap' / 'maya'}", text)
        self.assertIn("PYTHONPATH +:= .", text)

    def test_maya_is_idempotent_and_follows_a_moved_root(self):
        provision_maya(self.root, self.env)
        self.assertEqual(provision_maya(self.root, self.env).change, UNCHANGED)
        self.assertEqual(provision_maya(self.tmp / "elsewhere", self.env).change, UPDATED)

    def test_maya_remove(self):
        provision_maya(self.root, self.env)
        self.assertEqual(remove_maya(self.env).change, REMOVED)
        self.assertEqual(remove_maya(self.env).change, ABSENT)

    def test_a_foreign_module_with_the_same_name_is_not_removed(self):
        path = Path(self.env["MAYA_APP_DIR"]) / "modules" / "TheLinePipeline.mod"
        path.parent.mkdir(parents=True)
        path.write_text("+ SomethingElse 1.0 C:/x\n")
        self.assertEqual(remove_maya(self.env).change, UNCHANGED)
        self.assertTrue(path.exists())

    # Nuke

    def test_nuke_gets_a_marked_block_in_a_new_init_py(self):
        action = provision_nuke(self.root, self.env)
        self.assertEqual((action.path, action.change), (self.home / ".nuke" / "init.py", CREATED))
        text = action.path.read_text()
        self.assertTrue(text.startswith(BLOCK_BEGIN) and text.rstrip().endswith(BLOCK_END))
        self.assertIn(f'nuke.pluginAddPath(r"{self.root / "bootstrap" / "nuke"}")', text)

    def test_nuke_keeps_the_users_own_init_py_and_adds_the_block_once(self):
        path = self.home / ".nuke" / "init.py"
        path.parent.mkdir()
        mine = "import nuke\nnuke.knobDefault('Blur.size', '5')\n"
        path.write_text(mine)
        provision_nuke(self.root, self.env)
        self.assertTrue(path.read_text().startswith(mine))
        self.assertEqual(provision_nuke(self.root, self.env).change, UNCHANGED)
        self.assertEqual(provision_nuke(self.tmp / "moved", self.env).change, UPDATED)
        text = path.read_text()
        self.assertEqual(text.count(BLOCK_BEGIN), 1)
        self.assertIn(str(self.tmp / "moved"), text)
        self.assertNotIn(str(self.root), text)

    def test_nuke_content_after_the_block_survives_an_update(self):
        path = self.home / ".nuke" / "init.py"
        provision_nuke(self.root, self.env)
        with path.open("a") as handle:
            handle.write("print('after')\n")
        provision_nuke(self.tmp / "moved", self.env)
        self.assertIn("print('after')", path.read_text())

    def test_nuke_remove_restores_the_users_file_or_deletes_ours(self):
        path = self.home / ".nuke" / "init.py"
        path.parent.mkdir()
        mine = "import nuke\nnuke.knobDefault('Blur.size', '5')\n"
        path.write_text(mine)
        provision_nuke(self.root, self.env)
        self.assertEqual(remove_nuke(self.env).change, REMOVED)
        self.assertEqual(path.read_text(), mine)
        self.assertEqual(remove_nuke(self.env).change, ABSENT)
        path.unlink()
        provision_nuke(self.root, self.env)
        remove_nuke(self.env)
        self.assertFalse(path.exists())

    # Blender

    def test_blender_forwarder_loads_the_stub_from_the_bootstrap_folder(self):
        stub = self.root / "bootstrap" / "blender" / "startup" / "tls_pipeline_startup.py"
        stub.parent.mkdir(parents=True)
        stub.write_text("def register():\n    return 'registered'\n\ndef unregister():\n    return 'gone'\n")
        action = provision_blender(self.root, "5.2", self.env)
        self.assertEqual((action.host, action.change), ("blender", CREATED))
        self.assertEqual(action.path, self.tmp / "blender" / "startup" / "tls_pipeline_startup.py")
        spec = importlib.util.spec_from_file_location("forwarder_under_test", action.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual((module.register(), module.unregister()), ("registered", "gone"))

    def test_blender_default_location_is_the_per_series_user_scripts_folder(self):
        env = {"APPDATA": str(self.tmp / "appdata")}
        with patch("sys.platform", "win32"):
            path = blender_scripts_dir("5.2", env)
        self.assertEqual(path, self.tmp / "appdata" / "Blender Foundation" / "Blender" / "5.2" / "scripts")

    def test_blender_idempotent_foreign_file_untouched_and_remove(self):
        self.assertEqual(provision_blender(self.root, "5.2", self.env).change, CREATED)
        self.assertEqual(provision_blender(self.root, "5.2", self.env).change, UNCHANGED)
        self.assertEqual(remove_blender("5.2", self.env).change, REMOVED)
        foreign = self.tmp / "blender" / "startup" / "tls_pipeline_startup.py"
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("# somebody else's script\n")
        self.assertEqual(provision_blender(self.root, "5.2", self.env).change, UNCHANGED)
        self.assertEqual(foreign.read_text(), "# somebody else's script\n")
        self.assertEqual(remove_blender("5.2", self.env).change, UNCHANGED)
        self.assertTrue(foreign.exists())

    # all enabled hosts

    def config_with(self, hosts):
        return parse_local_config(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data), "hosts": hosts,
        }), self.tmp)

    def test_only_enabled_hosts_get_entries_and_remove_mirrors_it(self):
        config = self.config_with({"maya": ["2026"], "nuke": ["17.0"]})
        actions = provision(self.root, config, self.env)
        self.assertEqual([(a.host, a.change) for a in actions], [("maya", CREATED), ("nuke", CREATED)])
        self.assertFalse((self.tmp / "blender").exists())
        self.assertEqual([a.change for a in unprovision(config, self.env)], [REMOVED, REMOVED])

    def test_nothing_enabled_installs_nothing(self):
        self.assertEqual(provision(self.root, self.config_with({}), self.env), [])

    def test_provision_command(self):
        pipeline = self.tmp / "pipeline"
        pipeline.mkdir()
        (pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data),
            "hosts": {"maya": ["2026"]},
        }), encoding="utf-8")
        out = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(out):
            self.assertEqual(main(["--pipeline", str(pipeline), "provision"]), 0)
            self.assertEqual(main(["--pipeline", str(pipeline), "provision"]), 0)
            self.assertEqual(main(["--pipeline", str(pipeline), "provision", "--remove"]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual([line.split()[1] for line in lines], ["created", "unchanged", "removed"])


class EnabledGateTests(WorkstationTestCase):
    def setUp(self):
        super().setUp()
        self.pipeline = self.tmp / "pipeline"
        self.pipeline.mkdir()

    def write(self, hosts):
        (self.pipeline / "config.json").write_text(json.dumps({
            "schema_version": 1, "remote_repository": str(self.repo), "bundle_repository": str(self.data), "hosts": hosts,
        }), encoding="utf-8")
        return {"TLS_PIPELINE": str(self.pipeline)}

    def test_an_empty_list_enables_everything(self):
        self.assertTrue(host_enabled("maya", "2026", self.write({})))

    def test_listed_hosts_load_only_for_their_series(self):
        env = self.write({"maya": ["2026"], "nuke": ["17.0"]})
        self.assertTrue(host_enabled("maya", "2026", env))
        self.assertFalse(host_enabled("maya", "2025", env))
        self.assertFalse(host_enabled("blender", "5.2", env))

    def test_an_explicit_pin_or_source_always_loads(self):
        env = self.write({"maya": ["2026"]})
        self.assertTrue(host_enabled("maya", "2025", {**env, "TLS_PIPELINE_MAYA_BUNDLE": "1.0"}))
        self.assertTrue(host_enabled("blender", "5.2", {**env, "TLS_PIPELINE_BLENDER_SOURCE": "C:/src"}))
