"""Synthetic media only; enable with OMVTOOL_INTEGRATION=1."""

import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from omvtool.converter import input_args, layout, read_frame, unpack
from omvtool.runtime import executable, external_env
from omvtool.encoding import encoder_list, SOFTWARE, probe_alpha
from argparse import Namespace
from fractions import Fraction
import math
import hashlib


def command(*args, check=True):
    return subprocess.run(args, capture_output=True, check=check, env=external_env())


def cli(*args, check=True):
    binary = os.environ.get("OMVTOOL_TEST_BINARY")
    prefix = [binary] if binary else [sys.executable, "-m", "omvtool"]
    return command(*prefix, *map(str, args), check=check)


def fixture(root, mode, static=False):
    ogg = root / f"mode{mode}.ogv"
    height = 256 if mode == 1 else 192
    source = (
        f"color=c=red:size=256x{height}:rate=30000/1001"
        if static
        else f"testsrc2=size=256x{height}:rate=30000/1001"
    )
    command(
        executable("ffmpeg"),
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        source,
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000:duration=1",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-frames:v",
        "12",
        "-c:v",
        "libtheora",
        "-pix_fmt",
        "yuv444p",
        "-q:v",
        "5",
        "-c:a",
        "libvorbis",
        str(ogg),
    )
    data = ogg.read_bytes()
    offset = pages = 0
    while offset < len(data):
        assert data[offset : offset + 4] == b"OggS"
        segments = data[offset + 26]
        offset += 27 + segments + sum(data[offset + 27 : offset + 27 + segments])
        pages += 1
    header = bytearray(168)
    for off, value in (
        (0, 168),
        (4, 257),
        (0x28, mode),
        (0x2C, 256),
        (0x30, 192),
        (0x4C, pages),
        (0x50, 12),
    ):
        struct.pack_into("<I", header, off, value)
    omv = root / f"空 格mode{mode}.omv"
    omv.write_bytes(header + bytes(pages * 28 + 12 * 32) + data)
    return omv, data


@unittest.skipUnless(
    os.environ.get("OMVTOOL_INTEGRATION") == "1",
    "Set OMVTOOL_INTEGRATION=1 and install FFmpeg with libtheora/libvorbis encoders",
)
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.sources = [
            fixture(cls.root, mode, static=(mode == 2))[0] for mode in range(3)
        ]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def probe(self, path):
        return json.loads(
            command(
                executable("ffprobe"),
                "-v",
                "error",
                "-count_frames",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ).stdout
        )

    def test_hevc_alpha_capability_and_safe_failure(self):
        a = Namespace(
            codec="hevc",
            selected_encoder="libx265",
            alpha="preserve",
            crf=18,
            preset="ultrafast",
            quality=None,
            bitrate=None,
            encode_device=None,
        )
        ok, reason = probe_alpha(a)
        out = self.root / "preserved-alpha.mp4"
        result = cli(
            "convert",
            self.sources[1],
            "-o",
            out,
            "--codec",
            "hevc",
            "--alpha",
            "preserve",
            "--crf",
            "18",
            "--preset",
            "ultrafast",
            "--frames",
            "2",
            check=False,
        )
        if not ok:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"HEVC alpha encode/decode check failed", result.stderr)
            self.assertFalse(out.exists())
            self.assertFalse(list(self.root.glob("preserved-alpha.partial-*")))
            print("HEVC alpha unavailable in test FFmpeg: " + reason)
            return
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        rgba = np.frombuffer(
            cli("pipe", self.sources[1], "--frames", "2").stdout, np.uint8
        ).reshape(2, 192, 256, 4)
        alpha = command(
            executable("ffmpeg"),
            "-v",
            "error",
            "-i",
            str(out),
            "-vf",
            "alphaextract",
            "-frames:v",
            "2",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ).stdout
        decoded = np.frombuffer(alpha, np.uint8).reshape(2, 192, 256)
        self.assertLess(np.abs(decoded.astype(float) - rgba[:, :, :, 3]).mean(), 16)
        self.assertEqual(
            len([s for s in self.probe(out)["streams"] if s["codec_type"] == "audio"]),
            2,
        )

    def test_output_frame_rate_and_audio_timing(self):
        for mode, source in enumerate(self.sources):
            rgba = cli("pipe", source).stdout
            frame_size = 256 * 192 * 4
            source_frames = {
                hashlib.sha256(rgba[i : i + frame_size]).digest()
                for i in range(0, len(rgba), frame_size)
            }
            for fmt in ("mp4", "ffv1"):
                for rate in ("24", "60", "24000/1001"):
                    with self.subTest(mode=mode, fmt=fmt, rate=rate):
                        out = (
                            self.root
                            / f"fps-{mode}-{fmt}-{rate.replace('/', '_')}.{'mp4' if fmt == 'mp4' else 'mkv'}"
                        )
                        result = cli(
                            "convert", source, "-o", out, "--format", fmt, "--fps", rate
                        )
                        streams = self.probe(out)["streams"]
                        v = next(s for s in streams if s["codec_type"] == "video")
                        fps = Fraction(rate)
                        expected = math.ceil(12 * fps / Fraction(30000, 1001))
                        self.assertEqual(Fraction(v["avg_frame_rate"]), fps)
                        self.assertEqual(int(v["nb_read_frames"]), expected)
                        self.assertEqual(
                            len([s for s in streams if s["codec_type"] == "audio"]), 2
                        )
                        self.assertIn(b"PROGRESS video", result.stderr)
                        self.assertIn(b"audio mux", result.stderr)
                        self.assertIn(b"ETA=", result.stderr)
                        self.assertEqual(result.stdout, b"")
                        if fmt == "ffv1" and mode != 2:
                            raw = command(
                                executable("ffmpeg"),
                                "-v",
                                "error",
                                "-i",
                                str(out),
                                "-pix_fmt",
                                "rgba",
                                "-f",
                                "rawvideo",
                                "pipe:1",
                            ).stdout
                            for i in range(0, len(raw), frame_size):
                                self.assertIn(
                                    hashlib.sha256(raw[i : i + frame_size]).digest(),
                                    source_frames,
                                )
                        if fmt == "mp4":
                            self.assertAlmostEqual(
                                float(v["duration"]), expected / float(fps), delta=0.002
                            )
                            for a in streams:
                                if a["codec_type"] == "audio":
                                    self.assertAlmostEqual(
                                        float(a["duration"]),
                                        expected / float(fps),
                                        delta=0.06,
                                    )
        # Start remains aligned to source frames; --frames counts output frames.
        out = self.root / "fps-trim.mp4"
        result = cli(
            "convert",
            self.sources[1],
            "-o",
            out,
            "--fps",
            "24",
            "--start",
            ".1",
            "--frames",
            "5",
            "--no-progress",
        )
        v = next(s for s in self.probe(out)["streams"] if s["codec_type"] == "video")
        self.assertEqual(int(v["nb_read_frames"]), 5)
        self.assertAlmostEqual(float(v["duration"]), 5 / 24, delta=0.002)
        self.assertNotIn(b"PROGRESS", result.stderr)

    def test_forced_unknown_mode_pipe_and_diagnostic(self):
        source = self.root / "unknown-mode.omv"
        data = bytearray(self.sources[1].read_bytes())
        struct.pack_into("<I", data, 0x28, 99)
        source.write_bytes(data)
        self.assertNotEqual(cli("inspect", source, check=False).returncode, 0)
        result = cli("pipe", source, "--force-mode", "1", "--frames", "2")
        self.assertEqual(
            result.stdout, cli("pipe", self.sources[1], "--frames", "2").stdout
        )
        self.assertIn(b"forcing mode", result.stderr)
        report = self.root / "diagnostic.json"
        self.assertNotEqual(
            cli("diagnose", source, "-o", report, check=False).returncode, 0
        )
        self.assertFalse(report.exists())
        cli("diagnose", source, "-o", report, "--consent")
        self.assertEqual(json.loads(report.read_text())["status"], "unknown_mode")
        source.unlink()

    def test_hevc_av1_and_input_acceleration(self):
        available = encoder_list(executable("ffmpeg"))
        for codec in ("hevc", "av1"):
            encoders = [e for e in SOFTWARE[codec] if e in available]
            self.assertTrue(
                encoders, f"Integration environment needs a software {codec} encoder"
            )
            for encoder in encoders:
                for mode, source in enumerate(self.sources):
                    with self.subTest(codec=codec, encoder=encoder, mode=mode):
                        out = self.root / f"{encoder}-{mode}.mp4"
                        cli(
                            "convert",
                            source,
                            "-o",
                            out,
                            "--codec",
                            codec,
                            "--encoder",
                            encoder,
                            "--preset",
                            "8" if codec == "av1" else "ultrafast",
                            "--frames",
                            "6",
                            "--hwaccel",
                            "auto",
                        )
                        data = self.probe(out)
                        video = next(
                            s for s in data["streams"] if s["codec_type"] == "video"
                        )
                        self.assertEqual(video["codec_name"], codec)
                        self.assertEqual(int(video["nb_read_frames"]), 6)
                        self.assertEqual((video["width"], video["height"]), (256, 192))
                        self.assertEqual(
                            [
                                s["codec_name"]
                                for s in data["streams"]
                                if s["codec_type"] == "audio"
                            ],
                            ["aac", "aac"],
                        )
                        command(
                            executable("ffmpeg"),
                            "-v",
                            "error",
                            "-i",
                            str(out),
                            "-f",
                            "null",
                            "-",
                        )

    @unittest.skipUnless(
        os.environ.get("OMVTOOL_HARDWARE_TEST") == "1",
        "Set OMVTOOL_HARDWARE_TEST=1 to verify local GPU encoders",
    )
    def test_hardware_encoders(self):
        # Explicitly configured list avoids silently treating missing GPUs as success.
        requested = os.environ.get(
            "OMVTOOL_HARDWARE_ENCODERS", "h264_nvenc,hevc_nvenc,av1_nvenc"
        ).split(",")
        for encoder in requested:
            codec = encoder.split("_", 1)[0]
            for mode, source in enumerate(self.sources):
                with self.subTest(encoder=encoder, mode=mode):
                    out = self.root / f"hardware-{encoder}-{mode}.mp4"
                    cli(
                        "convert",
                        source,
                        "-o",
                        out,
                        "--codec",
                        codec,
                        "--encoder",
                        encoder,
                        "--frames",
                        "6",
                    )
                    data = self.probe(out)
                    video = next(
                        s for s in data["streams"] if s["codec_type"] == "video"
                    )
                    self.assertEqual(video["codec_name"], codec)
                    self.assertEqual(int(video["nb_read_frames"]), 6)
                    self.assertEqual((video["width"], video["height"]), (256, 192))
                    self.assertEqual(
                        len([s for s in data["streams"] if s["codec_type"] == "audio"]),
                        2,
                    )
                    command(
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-i",
                        str(out),
                        "-f",
                        "null",
                        "-",
                    )
        out = self.root / "hardware-auto.mp4"
        auto_codec = requested[0].split("_", 1)[0]
        result = cli(
            "convert",
            self.sources[1],
            "-o",
            out,
            "--codec",
            auto_codec,
            "--encoder",
            "auto",
            "--frames",
            "3",
        )
        self.assertIn(f"ENCODER: {auto_codec}_".encode(), result.stderr)

    def test_all_modes_and_audio(self):
        for mode, source in enumerate(self.sources):
            for fmt in ("mp4", "ffv1"):
                with self.subTest(mode=mode, format=fmt):
                    out = (
                        self.root
                        / f'converted{mode}.{"mp4" if fmt == "mp4" else "mkv"}'
                    )
                    cli(
                        "convert",
                        source,
                        "-o",
                        out,
                        "--format",
                        fmt,
                        *(["--preset", "fast"] if fmt == "mp4" else []),
                    )
                    data = self.probe(out)
                    video = next(
                        s for s in data["streams"] if s["codec_type"] == "video"
                    )
                    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
                    self.assertEqual(int(video["nb_read_frames"]), 12)
                    self.assertEqual((video["width"], video["height"]), (256, 192))
                    self.assertLess(
                        abs(float(data["format"]["duration"]) - 12 * 1001 / 30000), 0.06
                    )
                    self.assertEqual(
                        [a["codec_name"] for a in audio],
                        ["aac" if fmt == "mp4" else "vorbis"] * 2,
                    )
                    for i in range(2):
                        pcm = np.frombuffer(
                            command(
                                executable("ffmpeg"),
                                "-v",
                                "error",
                                "-i",
                                str(out),
                                "-map",
                                f"0:a:{i}",
                                "-ar",
                                "48000",
                                "-ac",
                                "1",
                                "-f",
                                "f32le",
                                "-",
                            ).stdout,
                            np.float32,
                        )
                        self.assertGreater(float(np.sqrt(np.mean(pcm**2))), 0.03)
                        frequency = np.argmax(abs(np.fft.rfft(pcm))) * 48000 / len(pcm)
                        self.assertLess(abs(frequency - (440 if i == 0 else 880)), 8)
                    command(
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-i",
                        str(out),
                        "-f",
                        "null",
                        "-",
                    )

    def test_trim_disable_and_no_overwrite(self):
        out = self.root / "trim.mp4"
        cli(
            "convert",
            self.sources[2],
            "-o",
            out,
            "--start",
            "0.1",
            "--frames",
            "3",
            "--audio",
            "none",
        )
        streams = self.probe(out)["streams"]
        self.assertEqual(len(streams), 1)
        self.assertEqual(int(streams[0]["nb_read_frames"]), 3)
        original = out.read_bytes()
        result = cli("convert", self.sources[0], "-o", out, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(out.read_bytes(), original)
        self.assertFalse(list(self.root.glob("*.partial-*")))
        result = cli(
            "convert",
            self.sources[0],
            "-o",
            out,
            "--frames",
            "2",
            "--audio",
            "none",
            "--overwrite",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(int(self.probe(out)["streams"][0]["nb_read_frames"]), 2)

    def test_audio_trim_and_packet_copy(self):
        out = self.root / "trim-audio.mp4"
        cli("convert", self.sources[2], "-o", out, "--start", "0.1", "--frames", "5")
        data = self.probe(out)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        self.assertEqual(int(video["nb_read_frames"]), 5)
        audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
        self.assertEqual(len(audio), 2)
        self.assertLess(abs(float(data["format"]["duration"]) - 5 * 1001 / 30000), 0.06)
        mkv = self.root / "packet-copy.mkv"
        cli("convert", self.sources[0], "-o", mkv, "--format", "ffv1")
        for index in range(2):

            def hashes(path):
                payload = json.loads(
                    command(
                        executable("ffprobe"),
                        "-v",
                        "error",
                        "-select_streams",
                        f"a:{index}",
                        "-show_packets",
                        "-show_data_hash",
                        "sha256",
                        "-show_entries",
                        "packet=data_hash",
                        "-of",
                        "json",
                        str(path),
                    ).stdout
                )
                return [p["data_hash"] for p in payload["packets"]]

            original = hashes(self.root / "mode0.ogv")
            copied = hashes(mkv)
            self.assertTrue(copied)
            self.assertEqual(copied, original[: len(copied)])

    def test_extract_inspect_pipe_and_lossless(self):
        for mode, source in enumerate(self.sources):
            with self.subTest(mode=mode):
                info = json.loads(cli("inspect", source, "--json").stdout)
                self.assertEqual(len(info["audio_streams"]), 2)
                self.assertEqual((info["fps_num"], info["fps_den"]), (30000, 1001))
                out = self.root / f"extracted{mode}.ogv"
                cli("extract", source, "-o", out)
                self.assertEqual(
                    out.read_bytes(), source.read_bytes()[info["ogg_offset"] :]
                )
                rgba = cli("pipe", source, "--frames", "2").stdout
                self.assertEqual(len(rgba), 2 * 256 * 192 * 4)
                mkv = self.root / f"roundtrip{mode}.mkv"
                cli("convert", source, "-o", mkv, "--format", "ffv1", "--frames", "2")
                if mode != 2:
                    decoded = command(
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-i",
                        str(mkv),
                        "-map",
                        "0:v:0",
                        "-pix_fmt",
                        "rgba",
                        "-f",
                        "rawvideo",
                        "-",
                    ).stdout
                    self.assertEqual(decoded, rgba)
                else:
                    m = layout(source)
                    args = input_args(m, 0) + [
                        "-frames:v",
                        "2",
                        "-vf",
                        "fps=30000/1001:start_time=0,tpad=stop_mode=clone:stop=-1",
                        "-pix_fmt",
                        "yuv444p",
                        "-f",
                        "rawvideo",
                        "-",
                    ]
                    original = command(*args).stdout
                    decoded = command(
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-i",
                        str(mkv),
                        "-map",
                        "0:v:0",
                        "-pix_fmt",
                        "yuv444p",
                        "-f",
                        "rawvideo",
                        "-",
                    ).stdout
                    self.assertEqual(decoded, original)

    def test_directory_and_pipe_example(self):
        inputs = self.root / "inputs"
        (inputs / "sub").mkdir(parents=True)
        (inputs / "sub" / "a.OMV").write_bytes(self.sources[0].read_bytes())
        # A bad file must not prevent successful conversion of another item.
        (inputs / "broken.omv").write_bytes(b"bad")
        output = self.root / "batch"
        self.assertEqual(
            cli(
                "convert", inputs, "-o", output, "--frames", "2", check=False
            ).returncode,
            1,
        )
        target = output / "sub" / "a.mp4"
        self.assertTrue(target.exists())
        before = target.read_bytes()
        cli("convert", inputs, "-o", output, check=False)
        self.assertEqual(before, target.read_bytes())
        example = Path(__file__).resolve().parents[1] / "examples" / "pipe_to_ffmpeg.py"
        out = self.root / "pipe-example.mp4"
        command(sys.executable, str(example), str(self.sources[0]), str(out))
        self.assertEqual(len(self.probe(out)["streams"]), 3)


if __name__ == "__main__":
    unittest.main()
