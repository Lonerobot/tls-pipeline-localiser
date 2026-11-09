"""The Nuke toolchain table: disabled toolchains are named in one line, not tabulated. No Nuke needed."""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parent.parent
    / "structure" / "bundle_sources" / "nuke" / "1.1.0" / "core" / "utils" / "PipelineReporter.py"
)


def load():
    spec = importlib.util.spec_from_file_location("nuke_pipeline_reporter_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(MODULE.is_file(), "nuke 1.1.0 bundle source not present")
class ReporterTests(unittest.TestCase):
    def report(self, rows, debug=False):
        reporter = load().create_reporter(debug)
        for row in rows:
            reporter.add_toolchain(*row[:5], **(row[5] if len(row) > 5 else {}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            reporter.print_toolchains_summary()
        return out.getvalue()

    ENABLED = ("TheLine", "0.0.2", True, 0.346, True)

    def test_disabled_toolchains_are_not_in_the_table_but_are_named_once(self):
        text = self.report([
            ("TL_BreakOutPSD", "0.0.1", False, 0.0), self.ENABLED,
            ("TemplateTools", "1.0.0", False, 0.0), ("Stamps", "1.2", False, 0.0),
        ])
        table = text.split("[  TL_BreakOutPSD")[0]
        self.assertIn("TheLine", table)
        for name in ("TL_BreakOutPSD", "TemplateTools", "Stamps"):
            self.assertNotIn(name, table)
        self.assertIn("[  TL_BreakOutPSD, TemplateTools, Stamps toolchains are present but currently disabled.  ]", text)

    def test_one_disabled_toolchain_reads_in_the_singular(self):
        text = self.report([self.ENABLED, ("Stamps", "1.2", False, 0.0)])
        self.assertIn("Stamps toolchain is present but currently disabled.", text)

    def test_nothing_is_said_when_nothing_is_disabled(self):
        text = self.report([self.ENABLED])
        self.assertNotIn("disabled", text)

    def test_a_missing_folder_stays_in_the_table_and_is_not_called_disabled(self):
        text = self.report([self.ENABLED, ("Gone", "1.0", False, 0.0, False, {"missing": True})])
        self.assertIn("MISSING", text)
        self.assertIn("Gone", text)
        self.assertNotIn("disabled", text)

    def test_when_everything_is_disabled_there_is_no_empty_table(self):
        text = self.report([("A", "1", False, 0.0), ("B", "1", False, 0.0)])
        self.assertIn("No toolchains loaded", text)
        self.assertNotIn("Toolchain ", text)  # the column header
        self.assertIn("A, B toolchains are present but currently disabled.", text)

    def test_with_no_toolchains_at_all_it_says_none_are_configured(self):
        self.assertIn("No toolchains configured", self.report([]))

    def test_debug_mode_still_lists_every_toolchain(self):
        text = self.report([self.ENABLED, ("Stamps", "1.2", False, 0.0)], debug=True)
        self.assertIn("Toolchain: Stamps", text)
        self.assertIn("Toolchain: TheLine", text)

    def test_the_footer_counts_only_loaded_toolchains(self):
        text = self.report([self.ENABLED, ("Stamps", "1.2", False, 0.0)])
        self.assertIn("1 toolchains loaded", text)
