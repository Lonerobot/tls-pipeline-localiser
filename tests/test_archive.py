import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from localiser import UnsafeArchiveError
from localiser.archive import safe_extract


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.zip_path = self.tmp / "a.zip"
        self.dest = self.tmp / "out"

    def build(self, members):
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            for name, data in members:
                zf.writestr(name, data)

    def test_extracts_normal_tree(self):
        self.build([("a/b.txt", "hi"), ("top.txt", "x"), ("emptydir/", "")])
        safe_extract(self.zip_path, self.dest)
        self.assertEqual((self.dest / "a" / "b.txt").read_text(), "hi")
        self.assertTrue((self.dest / "emptydir").is_dir())

    def test_rejects_unsafe_members_and_writes_nothing(self):
        unsafe = ["../evil.txt", "a/../../evil.txt", "/abs.txt", "C:/x.txt", "C:evil.txt", "a\\..\\b.txt", "a:stream"]
        for name in unsafe:
            with self.subTest(name=name):
                self.build([("ok.txt", "fine"), (name, "bad")])
                with self.assertRaises(UnsafeArchiveError):
                    safe_extract(self.zip_path, self.dest)
                self.assertFalse((self.dest / "ok.txt").exists())
                self.assertFalse((self.tmp / "evil.txt").exists())

    def test_rejects_symlink_member(self):
        link = zipfile.ZipInfo("link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.build([(link, "target")])
        with self.assertRaises(UnsafeArchiveError):
            safe_extract(self.zip_path, self.dest)

    def test_rejects_duplicate_members(self):
        self.build([("dup.txt", "1"), ("DUP.txt", "2")])
        with self.assertRaises(UnsafeArchiveError):
            safe_extract(self.zip_path, self.dest)


if __name__ == "__main__":
    unittest.main()
