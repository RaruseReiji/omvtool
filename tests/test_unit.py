import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from omvtool.cli import main, input_files
from omvtool.converter import layout, read_frame, unpack
from omvtool.header import inspect


def header_fixture(path, mode=1, height=4, visible=None, frames=2, pixel_format=3):
    width = 8
    visible = visible or (height + (height + 2) // 3 if mode == 1 else height)
    header = bytearray(168)
    for off, value in (
        (0, 168),
        (4, 257),
        (0x28, mode),
        (0x2C, width),
        (0x30, height),
        (0x4C, 1),
        (0x50, frames),
    ):
        struct.pack_into("<I", header, off, value)
    theora = bytearray(42)
    theora[:7] = b"\x80theora"
    for off, size, value in (
        (14, 3, width),
        (17, 3, visible),
        (22, 4, 30000),
        (26, 4, 1001),
        (40, 2, pixel_format << 3),
    ):
        theora[off : off + size] = value.to_bytes(size, "big")
    # Only identification bytes are needed by the structural parser in these tests.
    path.write_bytes(header + bytes(28 + frames * 32) + b"OggS\x00\x02" + theora)
    return path


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_alpha_reconstruction_all_remainders(self):
        rng = np.random.default_rng(42)
        for height in (1, 2, 3, 4, 270, 400, 512, 1080):
            with self.subTest(height=height):
                m = layout(header_fixture(self.root / "a.omv", height=height))
                rgb = rng.integers(0, 256, (height, 8, 3), dtype=np.uint8)
                alpha = rng.integers(0, 256, (height, 8), dtype=np.uint8)
                tail = np.zeros((3 * ((height + 2) // 3), 8), dtype=np.uint8)
                tail[:height] = alpha
                planes = np.concatenate(
                    (rgb.transpose(2, 0, 1)[::-1], tail.reshape(3, -1, 8)), axis=1
                )
                rgba = unpack(planes, m)
                np.testing.assert_array_equal(rgba[:, :, :3], rgb)
                np.testing.assert_array_equal(rgba[:, :, 3], alpha)

    def test_mode2_alignment_is_not_alpha(self):
        m = layout(
            header_fixture(self.root / "a.omv", mode=2, height=1088, visible=1080)
        )
        self.assertEqual(m["output_height"], 1080)
        self.assertFalse(m["alpha"])
        self.assertEqual((m["fps_num"], m["fps_den"]), (30000, 1001))

    def test_reject_unknown_mode_and_sampling(self):
        for kwargs in ({"mode": 9}, {"pixel_format": 0}, {"visible": 99}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                layout(header_fixture(self.root / "a.omv", **kwargs))

    def test_truncated_and_invalid_header(self):
        p = self.root / "a.omv"
        p.write_bytes(b"OggS")
        with self.assertRaises(ValueError):
            inspect(p)
        header_fixture(p)
        p.write_bytes(p.read_bytes()[:-20])
        with self.assertRaises(ValueError):
            inspect(p)

    def test_forced_mode_preserves_validation_and_declared_value(self):
        p = header_fixture(self.root / "a.omv", mode=99)
        with contextlib.redirect_stderr(io.StringIO()):
            m = layout(p, 2)
            self.assertEqual(
                (m["declared_mode"], m["forced_mode"], m["mode"]), (99, 2, 2)
            )
            with self.assertRaises(ValueError):
                layout(p, 1)
            with self.assertRaises(ValueError):
                layout(header_fixture(p, pixel_format=0), 2)
            data = bytearray(p.read_bytes())
            struct.pack_into("<I", data, 4, 258)
            p.write_bytes(data)
            with self.assertRaises(ValueError):
                layout(p, 2)

    def test_unknown_mode_hint_and_opt_in_private_report(self):
        source = header_fixture(self.root / "private-game-name.omv", mode=99)
        output = self.root / "report.json"
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["inspect", str(source)]), 1)
        self.assertIn("diagnose", error.getvalue())
        self.assertIn("--consent", error.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["diagnose", str(source), "-o", str(output)]), 1)
        self.assertFalse(output.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(["diagnose", str(source), "-o", str(output), "--consent"]), 0
            )
        text = output.read_text(encoding="utf8")
        data = json.loads(text)
        self.assertEqual(data["status"], "unknown_mode")
        self.assertEqual(data["metadata"]["mode"], 99)
        for private in (str(self.root), source.name, "prefix_hex", "serial", "path"):
            self.assertNotIn(private, text)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                main(["diagnose", str(source), "-o", str(output), "--consent"]), 1
            )
        self.assertEqual(output.read_text(encoding="utf8"), text)

    def test_unknown_version_report_and_theora_fields(self):
        p = header_fixture(self.root / "a.omv")
        data = bytearray(p.read_bytes())
        start = data.find(b"\x80theora")
        data[start + 7 : start + 10] = bytes((3, 2, 1))
        for offset, size, value in (
            (10, 2, 1),
            (12, 2, 1),
            (20, 1, 2),
            (21, 1, 3),
            (30, 3, 4),
            (33, 3, 3),
            (36, 1, 2),
        ):
            data[start + offset : start + offset + size] = value.to_bytes(size, "big")
        p.write_bytes(data)
        m = inspect(p)
        self.assertEqual((m["coded_width"], m["coded_height"]), (16, 16))
        self.assertEqual(m["theora_version"], [3, 2, 1])
        self.assertEqual(
            (
                m["picture_x"],
                m["picture_y"],
                m["aspect_num"],
                m["aspect_den"],
                m["colorspace"],
            ),
            (2, 3, 4, 3, 2),
        )
        struct.pack_into("<I", data, 4, 258)
        p.write_bytes(data)
        output = self.root / "unknown.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(["diagnose", str(p), "-o", str(output), "--consent"]), 0
            )
        report = json.loads(output.read_text())
        self.assertEqual(report["candidate_header_fields"]["version"], 258)
        self.assertNotIn("metadata", report)

    def test_yuv_black_white_and_color(self):
        m = {"mode": 2, "output_height": 1, "output_width": 3}
        p = np.array(
            [[[0, 128, 255]], [[128, 128, 128]], [[128, 128, 128]]], dtype=np.uint8
        )
        rgba = unpack(p, m)
        np.testing.assert_array_equal(
            rgba[0, :, :3], np.array([[0] * 3, [128] * 3, [255] * 3])
        )
        p[0, 0] = [16, 128, 235]
        limited = unpack(p, m, "limited")
        self.assertEqual(limited[0, 0, 0], 0)
        self.assertEqual(limited[0, 2, 0], 255)
        p[2] = 200
        self.assertFalse(
            np.array_equal(unpack(p, m, matrix="601"), unpack(p, m, matrix="709"))
        )

    def test_raw_reader_rejects_partial_frame(self):
        self.assertEqual(read_frame(io.BytesIO(b"abcd"), 4), b"abcd")
        self.assertIsNone(read_frame(io.BytesIO(), 4))
        with self.assertRaises(RuntimeError):
            read_frame(io.BytesIO(b"abc"), 4)

    def test_recursive_case_insensitive_inputs(self):
        (self.root / "sub").mkdir()
        header_fixture(self.root / "sub" / "a.OMV")
        self.assertEqual(len(input_files(self.root)), 1)

    def test_invalid_arguments(self):
        for args in (
            ["convert", "x", "-o", "y.mp4", "--start", "nan"],
            ["convert", "x", "-o", "y.mp4", "--frames", "0"],
            ["convert", "x", "-o", "y.mp4", "--crf", "52"],
            *(
                ["convert", "x", "-o", "y.mp4", "--fps", value]
                for value in ("0", "-1", "nan", "inf", "1/0", "1001")
            ),
        ):
            with (
                self.subTest(args=args),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as caught,
            ):
                main(args)
            self.assertEqual(caught.exception.code, 2)

    def test_overwrite_is_convert_only(self):
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            main(["pipe", "x", "--overwrite"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
