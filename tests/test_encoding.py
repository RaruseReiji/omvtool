import argparse
import contextlib
import io
import os
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from omvtool.encoding import (
    select_encoder,
    video_args,
    pixel_filter,
    device_args,
    validate,
    _probe_alpha,
)
from omvtool.runtime import executable


def profile(**kwargs):
    values = dict(
        format="mp4",
        codec="h264",
        encoder="software",
        crf=None,
        quality=None,
        bitrate=None,
        preset=None,
        encode_device=None,
        selected_encoder="libx264",
    )
    values.update(kwargs)
    return argparse.Namespace(**values)


class EncoderTests(unittest.TestCase):
    def test_alpha_options_reject_unsupported_backends(self):
        for codec, encoder, fmt in (
            ("h264", "software", "mp4"),
            ("av1", "software", "mp4"),
            ("hevc", "auto", "mp4"),
            ("hevc", "nvenc", "mp4"),
            ("hevc", "software", "ffv1"),
        ):
            with (
                self.subTest(codec=codec, encoder=encoder, fmt=fmt),
                self.assertRaises(ValueError),
            ):
                validate(
                    profile(codec=codec, encoder=encoder, format=fmt, alpha="preserve")
                )
        a = profile(codec="hevc", selected_encoder="libx265", alpha="preserve")
        validate(a)
        self.assertEqual(pixel_filter(a), "format=yuva420p")
        self.assertIn("+yuva420p", video_args(a))

    def test_alpha_roundtrip_rejects_opaque_fallback(self):
        for pixels, success in (
            (bytes(range(256)) * 192, True),
            (bytes([255]) * (256 * 192), False),
            (b"", False),
        ):
            _probe_alpha.cache_clear()
            with patch(
                "omvtool.encoding.subprocess.run",
                side_effect=[
                    SimpleNamespace(returncode=0, stderr=b""),
                    SimpleNamespace(returncode=0, stdout=pixels),
                ],
            ):
                self.assertEqual(_probe_alpha("ffmpeg", ())[0], success)
        _probe_alpha.cache_clear()
        with patch(
            "omvtool.encoding.subprocess.run",
            return_value=SimpleNamespace(
                returncode=1,
                stderr=b"Loaded libx265 does not support alpha layer encoding.",
            ),
        ):
            ok, reason = _probe_alpha("ffmpeg", ())
            self.assertFalse(ok)
            self.assertIn("alpha", reason)
        _probe_alpha.cache_clear()

    def test_auto_requires_successful_device_probe(self):
        a = profile(codec="av1", encoder="auto")
        with (
            patch("omvtool.encoding.executable", return_value="ffmpeg"),
            patch(
                "omvtool.encoding.encoder_list", return_value={"av1_nvenc", "libsvtav1"}
            ),
            patch("omvtool.encoding.probe_encoder", return_value=(False, "no GPU")),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(select_encoder(a, 256, 192), "libsvtav1")
        with (
            patch("omvtool.encoding.executable", return_value="ffmpeg"),
            patch(
                "omvtool.encoding.encoder_list", return_value={"av1_nvenc", "libsvtav1"}
            ),
            patch("omvtool.encoding.probe_encoder", return_value=(True, "")),
        ):
            self.assertEqual(select_encoder(a, 256, 192), "av1_nvenc")

    def test_explicit_encoder_never_falls_back(self):
        a = profile(codec="hevc", encoder="nvenc")
        with (
            patch("omvtool.encoding.executable", return_value="ffmpeg"),
            patch("omvtool.encoding.encoder_list", return_value={"libx265"}),
            self.assertRaises(ValueError),
        ):
            select_encoder(a, 256, 192)

    def test_quality_options_are_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            video_args(profile(selected_encoder="h264_nvenc", crf=18))
        with self.assertRaises(ValueError):
            video_args(profile(quality=18))
        with self.assertRaises(ValueError):
            validate(profile(codec="h264", crf=63))
        validate(profile(codec="av1", crf=63))
        with self.assertRaises(ValueError):
            validate(profile(encoder="auto", preset="slow"))

    def test_hw_frames_and_devices(self):
        a = profile(selected_encoder="hevc_vaapi", encode_device="/dev/dri/renderD129")
        self.assertEqual(pixel_filter(a), "format=nv12,hwupload")
        self.assertEqual(device_args(a), ["-vaapi_device", "/dev/dri/renderD129"])
        a = profile(selected_encoder="h264_qsv")
        self.assertEqual(pixel_filter(a), "format=nv12")
        self.assertIn("nv12", video_args(a))


class RuntimeTests(unittest.TestCase):
    def test_frozen_side_by_side_tools_precede_cwd_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, cwd = Path(tmp) / "app", Path(tmp) / "cwd"
            app.mkdir()
            cwd.mkdir()
            filename = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            for directory in (app, cwd):
                (directory / filename).write_bytes(b"fixture")
                (directory / filename).chmod(0o755)
            with (
                patch.dict(os.environ, {"PATH": "", "OMVTOOL_FFMPEG": ""}),
                patch("omvtool.runtime.sys.frozen", True, create=True),
                patch("omvtool.runtime.sys.executable", str(app / "omvtool.exe")),
                patch("omvtool.runtime.Path.cwd", return_value=cwd),
            ):
                self.assertEqual(Path(executable("ffmpeg")), app / filename)
                (app / filename).unlink()
                self.assertEqual(Path(executable("ffmpeg")), cwd / filename)

    def test_invalid_explicit_path_does_not_select_another_tool(self):
        with (
            patch.dict(os.environ, {"OMVTOOL_FFMPEG": "/nonexistent/ffmpeg-explicit"}),
            self.assertRaises(FileNotFoundError),
        ):
            executable("ffmpeg")
