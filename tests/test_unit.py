import contextlib
import io
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
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(
                io.StringIO()
            ), self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
