"""Shared logging (tls_common) and the Playblast Plus logger's inheritance fix. No DCC needed."""
import importlib.util
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

STRUCTURE = Path(__file__).resolve().parent.parent / "structure"
SHARED = STRUCTURE / "shared_sources"
PLAYBLAST_LOGGER = (
    STRUCTURE / "bundle_sources" / "maya" / "1.0.0" / "playblast_plus" / "lib" / "logger.py"
)


def reset_root():
    root = logging.getLogger("tls")
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    root.__dict__.pop("_tls_configured", None)
    root.setLevel(logging.NOTSET)
    return root


@unittest.skipUnless((SHARED / "tls_common").is_dir(), "shared sources not present")
class SharedLoggingTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SHARED))
        self.addCleanup(sys.path.remove, str(SHARED))
        for name in [n for n in sys.modules if n == "tls_common" or n.startswith("tls_common.")]:
            del sys.modules[name]
        import tls_common

        self.tls = tls_common
        reset_root()
        self.addCleanup(reset_root)

    def test_name_is_host_and_tool(self):
        class Tool(self.tls.MayaLogger):
            NAME = "playblast"

        self.assertEqual(Tool.logger_obj().name, "tls.maya.playblast")
        self.assertEqual(self.tls.BlenderLogger.logger_obj().name, "tls.blender")
        self.assertEqual(self.tls.get_logger("x.y").name, "tls.x.y")

    def test_subclass_logger_is_not_hijacked_by_a_parent_that_logged_first(self):
        class Tool(self.tls.NukeLogger):
            NAME = "tool"

        self.tls.NukeLogger.info("the parent logs first")
        self.assertEqual(Tool.logger_obj().name, "tls.nuke.tool")
        self.assertEqual(self.tls.NukeLogger.logger_obj().name, "tls.nuke")

    def test_one_handler_on_tls_and_children_do_not_propagate_past_it(self):
        class A(self.tls.MayaLogger):
            NAME = "a"

        class B(self.tls.MayaLogger):
            NAME = "b"

        A.info("one")
        B.info("two")
        root = logging.getLogger("tls")
        self.assertEqual(len(root.handlers), 1)
        self.assertFalse(root.propagate)
        self.assertEqual(A.logger_obj().handlers, [])

    def test_configuring_twice_does_not_add_a_second_handler(self):
        self.tls.log._root(self.tls.BaseLogger.make_handler)
        self.tls.log._root(self.tls.BaseLogger.make_handler)
        self.assertEqual(len(logging.getLogger("tls").handlers), 1)

    def test_level_comes_from_the_environment(self):
        with mock.patch.dict(os.environ, {"TLS_LOG_LEVEL": "debug"}):
            self.tls.MayaLogger.logger_obj()
        self.assertEqual(logging.getLogger("tls").level, logging.DEBUG)

    def test_default_level_is_info_and_bad_values_are_ignored(self):
        with mock.patch.dict(os.environ, {"TLS_LOG_LEVEL": "loud"}):
            self.tls.MayaLogger.logger_obj()
        self.assertEqual(logging.getLogger("tls").level, logging.INFO)

    def test_write_to_file_does_not_duplicate_output(self):
        class Tool(self.tls.MayaLogger):
            NAME = "filetest"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "logs" / "tls.log"
            Tool.write_to_file(path, logging.INFO)
            Tool.write_to_file(path, logging.INFO)
            Tool.info("hello")
            for handler in logging.getLogger("tls").handlers:
                handler.flush()
            self.assertEqual(path.read_text(encoding="utf-8").count("hello"), 1)
            reset_root()  # release the file before the folder is removed


@unittest.skipUnless(PLAYBLAST_LOGGER.is_file(), "maya bundle source not present")
class PlayblastLoggerTests(unittest.TestCase):
    def test_subclass_keeps_its_own_logger_after_the_base_has_logged(self):
        spec = importlib.util.spec_from_file_location("playblast_logger_under_test", PLAYBLAST_LOGGER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class Sub(module.Logger):
            LOGGER_NAME = "PlayblastTestSub"

        module.Logger.logger_obj()
        self.assertEqual(Sub.logger_obj().name, "PlayblastTestSub")
        self.assertEqual(module.Logger.logger_obj().name, module.Logger.LOGGER_NAME)


if __name__ == "__main__":
    unittest.main()
