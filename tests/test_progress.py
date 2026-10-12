import contextlib
import io
import unittest
from types import SimpleNamespace

from omvtool.progress import Progress


class ProgressTests(unittest.TestCase):
    def test_ffmpeg_records_are_parsed_and_errors_preserved(self):
        p = Progress()
        with contextlib.redirect_stderr(io.StringIO()) as log:
            p.phase("video", 100)
            p.read(
                SimpleNamespace(
                    stderr=io.BytesIO(
                        b"frame=25\nfps=10\nprogress=continue\n[codec] actual error\n"
                    )
                )
            )
            p.render()
        self.assertEqual(p.done, 25)
        self.assertIn("25/100", log.getvalue())
        self.assertIn("25.0%", log.getvalue())
        self.assertIn("[codec] actual error", log.getvalue())
        self.assertNotIn("progress=continue", log.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            p.phase("audio", 5, "seconds")
            p.read(
                SimpleNamespace(
                    stderr=io.BytesIO(b"out_time_us=2500000\nprogress=end\n")
                )
            )
        self.assertEqual(p.done, 2.5)

    def test_disabled_and_zero_total_do_not_write_or_divide_by_zero(self):
        with contextlib.redirect_stderr(io.StringIO()) as log:
            with Progress(False) as p:
                p.phase("video", 0)
                p.render()
        self.assertEqual(log.getvalue(), "")
        with contextlib.redirect_stderr(io.StringIO()):
            Progress().phase("empty", 0)
