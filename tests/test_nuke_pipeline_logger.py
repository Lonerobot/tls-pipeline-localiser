"""The Nuke pipeline's PipelineLogger on top of tls_common. No Nuke needed."""
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
MODULE = STRUCTURE / "bundle_sources" / "nuke" / "1.0.0" / "core" / "utils" / "PipelineLogger.py"


def reset_tls():
    root = logging.getLogger("tls")
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    root.__dict__.pop("_tls_configured", None)
    root.setLevel(logging.NOTSET)


@unittest.skipUnless(MODULE.is_file() and (SHARED / "tls_common").is_dir(), "nuke bundle source not present")
class PipelineLoggerTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SHARED))
        self.addCleanup(sys.path.remove, str(SHARED))
        for name in [n for n in sys.modules if n == "tls_common" or n.startswith("tls_common.")]:
            del sys.modules[name]
        reset_tls()
        self.addCleanup(reset_tls)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(reset_tls)  # release the log file before the folder goes
        patcher = mock.patch.dict(os.environ, {"TLS_LOG_DIR": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def load(self):
        spec = importlib.util.spec_from_file_location("pipeline_logger_under_test", MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_root_logger_is_left_alone(self):
        root = logging.getLogger()
        before = list(root.handlers), root.level
        module = self.load()
        module.get_logger("init").info("hello")
        self.assertEqual((list(root.handlers), root.level), before)

    def test_loggers_live_under_tls_nuke(self):
        module = self.load()
        self.assertEqual(module.get_logger("Config").name, "tls.nuke.Config")
        self.assertEqual(module.get_logger("shortcuts.utility_functions").name, "tls.nuke.shortcuts.utility_functions")
        self.assertIs(module.get_logger("Config"), module.get_logger("Config"))

    def test_messages_reach_the_daily_log_file_in_tls_log_dir(self):
        module = self.load()
        module.get_logger("init").debug("debug goes to the file")
        for handler in logging.getLogger("tls").handlers:
            handler.flush()
        files = list(Path(self.tmp.name).glob("pipeline_*.log"))
        self.assertEqual(len(files), 1)
        self.assertIn("debug goes to the file", files[0].read_text(encoding="utf-8"))

    def test_console_is_info_by_default_and_file_is_debug(self):
        module = self.load()
        stats = module.get_log_stats()
        self.assertEqual((stats["console_level"], stats["file_level"]), ("INFO", "DEBUG"))
        self.assertEqual(logging.getLogger("tls").level, logging.DEBUG)

    def test_set_log_level_changes_both_handlers(self):
        module = self.load()
        module.set_log_level(logging.WARNING)
        stats = module.get_log_stats()
        self.assertEqual((stats["console_level"], stats["file_level"]), ("WARNING", "WARNING"))
        self.assertEqual(logging.getLogger("tls").level, logging.WARNING)

    def test_tls_log_level_environment_sets_the_console(self):
        with mock.patch.dict(os.environ, {"TLS_LOG_LEVEL": "DEBUG"}):
            module = self.load()
        self.assertEqual(module.get_log_stats()["console_level"], "DEBUG")

    def test_one_console_and_one_file_handler_after_a_reload(self):
        self.load()
        self.load()
        handlers = logging.getLogger("tls").handlers
        files = [h for h in handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(len(handlers), 2)
        self.assertEqual(len(files), 1)

    def test_performance_and_call_helpers_still_work(self):
        module = self.load()
        module.log_performance("op", 0.5, {"items": 2})
        module.log_function_call("f", (1,), {"x": 2})
        calls = []

        @module.log_calls("Decorated")
        def work(value):
            calls.append(value)
            return value * 2

        self.assertEqual(work(3), 6)
        self.assertEqual(calls, [3])


if __name__ == "__main__":
    unittest.main()
