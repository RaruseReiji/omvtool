import errno
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omvtool.converter import publish_output


class PublishTests(unittest.TestCase):
    def test_no_link_and_unsupported_filesystem(self):
        for link in (
            None,
            unittest.mock.Mock(side_effect=OSError(errno.EPERM, "unsupported")),
        ):
            with tempfile.TemporaryDirectory() as directory:
                src, dst = Path(directory) / "tmp", Path(directory) / "out"
                src.write_bytes(b"complete")
                with patch("omvtool.converter.os.link", link, create=True):
                    publish_output(src, dst)
                    self.assertEqual(dst.read_bytes(), b"complete")
                    self.assertFalse(src.exists())
                    src.write_bytes(b"new")
                    with self.assertRaises(FileExistsError):
                        publish_output(src, dst)
                    self.assertEqual(dst.read_bytes(), b"complete")
                    self.assertEqual(src.read_bytes(), b"new")

    def test_failed_copy_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            src, dst = Path(directory) / "tmp", Path(directory) / "out"
            src.write_bytes(b"complete")
            with (
                patch("omvtool.converter.os.link", None, create=True),
                patch(
                    "omvtool.converter.shutil.copyfileobj",
                    side_effect=OSError("disk full"),
                ),
            ):
                with self.assertRaises(OSError):
                    publish_output(src, dst)
            self.assertFalse(dst.exists())
            self.assertTrue(src.exists())
