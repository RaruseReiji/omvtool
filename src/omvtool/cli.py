"""Stable command-line interface. Binary data uses stdout; progress uses stderr."""

import argparse
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from . import __version__
from .converter import convert, layout, probe_media
from .runtime import executable, external_env
from .encoding import (
    HARDWARE,
    SOFTWARE,
    encoder_list,
    probe_encoder,
    probe_alpha,
    validate,
)
from .diagnostics import diagnose
from argparse import Namespace


def options(parser):
    parser.add_argument(
        "--no-progress", action="store_true", help="Disable periodic progress on stderr"
    )
    parser.add_argument(
        "--force-mode",
        type=int,
        choices=[0, 1, 2],
        help="Override declared mode; dimensions and sampling are still validated",
    )
    parser.add_argument("--start", type=float, default=0, metavar="SECONDS")
    parser.add_argument("--frames", type=int, metavar="COUNT")
    parser.add_argument("--yuv-range", choices=["full", "limited"], default="full")
    parser.add_argument("--matrix", choices=["601", "709"], default="601")
    parser.add_argument(
        "--hwaccel",
        default="none",
        choices=[
            "none",
            "auto",
            "cuda",
            "qsv",
            "d3d11va",
            "dxva2",
            "vaapi",
            "videotoolbox",
            "vulkan",
        ],
        help="FFmpeg input acceleration; Theora normally uses software decoding",
    )
    parser.add_argument("--hwaccel-device", help="FFmpeg input hardware device")


def parser():
    p = argparse.ArgumentParser(
        prog="omvtool",
        description="Stream SiglusEngine OMV to ordinary video, lossless MKV or RGBA.",
    )
    p.add_argument("--version", action="version", version=f"omvtool {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser(
        "convert", help="Convert one OMV or recursively convert a directory"
    )
    c.add_argument("input", type=Path)
    c.add_argument("-o", "--output", type=Path, required=True)
    c.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file; the input file is never overwritten",
    )
    c.add_argument("--format", choices=["mp4", "ffv1"], default="mp4")
    c.add_argument(
        "--codec",
        choices=["h264", "hevc", "av1"],
        default="h264",
        help="Video codec for MP4",
    )
    c.add_argument(
        "--encoder",
        default="software",
        help="software, auto, nvenc, qsv, amf, vaapi, videotoolbox, or an FFmpeg encoder name",
    )
    quality = c.add_mutually_exclusive_group()
    quality.add_argument(
        "--crf", type=int, help="Software CRF: default H.264 16, HEVC 20, AV1 28"
    )
    quality.add_argument(
        "--quality", type=int, help="Hardware quality value (backend-specific)"
    )
    quality.add_argument("--bitrate", help="Target video bitrate, e.g. 8M")
    c.add_argument("--preset", help="Encoder-specific preset; see the manual")
    c.add_argument(
        "--encode-device", help="NVENC GPU index, QSV device, or VAAPI render node"
    )
    c.add_argument(
        "--alpha",
        choices=["black", "discard", "preserve"],
        default="black",
        help="MP4 alpha handling; preserve requires HEVC/libx265 with working alpha support",
    )
    c.add_argument("--audio", choices=["auto", "copy", "none"], default="auto")
    c.add_argument(
        "--fps",
        type=frame_rate,
        metavar="RATE",
        help="Output frame rate, e.g. 24, 29.97 or 30000/1001; duplicates/drops frames without changing playback speed",
    )
    options(c)
    i = sub.add_parser(
        "inspect", help="Show layout, frame rate and embedded audio streams"
    )
    i.add_argument("input", type=Path)
    i.add_argument("--force-mode", type=int, choices=[0, 1, 2])
    i.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object, or a JSON array for a directory",
    )
    e = sub.add_parser(
        "extract", help="Copy the entire original Ogg payload without decoding"
    )
    e.add_argument("input", type=Path)
    e.add_argument("-o", "--output", type=Path, required=True)
    e.add_argument("--force-mode", type=int, choices=[0, 1, 2])
    e.add_argument("--no-progress", action="store_true")
    r = sub.add_parser(
        "pipe", help="Write headerless RGBA video to binary stdout (one file)"
    )
    r.add_argument("input", type=Path)
    options(r)
    d = sub.add_parser(
        "doctor", help="Check FFmpeg, codecs, filters and hardware encoders"
    )
    d.add_argument(
        "--test-encoders",
        action="store_true",
        help="Actually encode one frame with each listed encoder",
    )
    report = sub.add_parser(
        "diagnose",
        help="Create an opt-in local structural JSON report; never upload automatically",
    )
    report.add_argument("input", type=Path)
    report.add_argument("-o", "--output", type=Path, required=True)
    report.add_argument(
        "--consent",
        action="store_true",
        help="Consent to collecting file size and numeric header fields only; excludes paths, names and media bytes",
    )
    return p


def frame_rate(value):
    try:
        rate = Fraction(value)
        if not 0 < rate <= 1000:
            raise ValueError()
        return rate
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(
            "--fps requires a positive rate <= 1000, e.g. 60 or 30000/1001"
        )


def doctor(test_encoders=False):
    failed = False
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = executable(name)
            result = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                env=external_env(),
                check=True,
            )
            print(f"{name}: {path}\n  {result.stdout.splitlines()[0]}")
            if name == "ffmpeg":
                for flag, required in (
                    ("-decoders", ["theora"]),
                    ("-encoders", ["libx264", "ffv1", "aac"]),
                    (
                        "-filters",
                        [
                            "fps",
                            "tpad",
                            "trim",
                            "setpts",
                            "scale",
                            "pad",
                            "format",
                            "setparams",
                            "setsar",
                        ],
                    ),
                ):
                    listing = subprocess.run(
                        [path, "-hide_banner", flag],
                        capture_output=True,
                        text=True,
                        env=external_env(),
                        check=True,
                    ).stdout
                    available = {
                        line.split()[1]
                        for line in listing.splitlines()
                        if len(line.split()) >= 2
                    }
                    missing = set(required) - available
                    print(
                        f"  {flag[1:]}: "
                        + (f"MISSING {', '.join(sorted(missing))}" if missing else "OK")
                    )
                    failed |= bool(missing)
                available = encoder_list(path)
                for codec in SOFTWARE:
                    for enc in (*SOFTWARE[codec], *HARDWARE[codec].values()):
                        if enc not in available:
                            continue
                        status = "compiled"
                        if test_encoders:
                            a = Namespace(
                                codec=codec,
                                selected_encoder=enc,
                                crf=None,
                                quality=None,
                                bitrate=None,
                                preset=None,
                                encode_device=None,
                            )
                            ok, reason = probe_encoder(a)
                            status = (
                                "PASS"
                                if ok
                                else "UNAVAILABLE: "
                                + (
                                    reason.splitlines()[-1]
                                    if reason
                                    else "probe failed"
                                )
                            )
                        print(f"  {codec}: {enc}: {status}")
                if test_encoders and "libx265" in available:
                    alpha_options = Namespace(
                        codec="hevc",
                        selected_encoder="libx265",
                        alpha="preserve",
                        crf=None,
                        quality=None,
                        bitrate=None,
                        preset=None,
                        encode_device=None,
                    )
                    ok, reason = probe_alpha(alpha_options)
                    print(
                        f"  HEVC alpha (libx265): {'PASS' if ok else 'UNAVAILABLE'}: {reason}"
                    )
                hw = subprocess.run(
                    [path, "-hide_banner", "-hwaccels"],
                    capture_output=True,
                    text=True,
                    check=True,
                    env=external_env(),
                )
                print("  " + hw.stdout.strip().replace("\n", ", "))
                print(
                    "  Theora input normally uses software decoding; hardware encoder availability depends on the device/driver."
                )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"{name}: ERROR: {exc}", file=sys.stderr)
            failed = True
    return int(failed)


def inspect_input(source, as_json, force_mode=None):
    files = input_files(source)
    rows, failed = [], False
    for src in files:
        try:
            m = layout(src, force_mode)
            media = probe_media(m)
            m["audio_streams"] = [
                s for s in media["streams"] if s["codec_type"] == "audio"
            ]
            rows.append(m)
            if not as_json:
                print(
                    f"{src}\n  mode={m['mode']}, {m['output_width']}x{m['output_height']}, fps={m['fps_num']}/{m['fps_den']}, frames={m['frames']}, alpha={m['alpha']}, audio={len(m['audio_streams'])}"
                )
        except (OSError, ValueError, RuntimeError) as exc:
            if not source.is_dir():
                raise
            failed = True
            rows.append({"path": str(src), "error": str(exc)})
            print(f"FAILED: {src}: {exc}", file=sys.stderr)
    if as_json:
        print(
            json.dumps(
                rows if source.is_dir() else rows[0], ensure_ascii=True, indent=2
            )
        )
    return int(failed)


def input_files(source):
    if not source.exists():
        raise FileNotFoundError(f"Input does not exist: {source}")
    if not source.is_dir():
        return [source]
    files = sorted(
        p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".omv"
    )
    if not files:
        raise ValueError(f"No OMV files found: {source}")
    return files


def dispatch(a, p):
    if a.command == "doctor":
        return doctor(a.test_encoders)
    if a.command == "diagnose":
        return diagnose(a.input, a.output, a.consent)
    if a.command == "inspect":
        return inspect_input(a.input, a.json, a.force_mode)
    # Normalize all subcommands to the conversion core's small options structure.
    defaults = dict(
        format="mp4",
        crf=None,
        preset=None,
        codec="h264",
        encoder="software",
        quality=None,
        bitrate=None,
        encode_device=None,
        hwaccel="none",
        hwaccel_device=None,
        alpha="black",
        audio="auto",
        start=0,
        frames=None,
        yuv_range="full",
        matrix="601",
        force_mode=None,
        fps=None,
        no_progress=False,
        overwrite=False,
        output=None,
    )
    for key, value in defaults.items():
        if not hasattr(a, key):
            setattr(a, key, value)
    if (
        not math.isfinite(a.start)
        or a.start < 0
        or (a.frames is not None and a.frames <= 0)
    ):
        p.error("Require finite --start >= 0 and --frames > 0")
    if a.hwaccel_device and a.hwaccel == "none":
        p.error("--hwaccel-device requires --hwaccel")
    if a.command == "convert":
        try:
            validate(a)
        except ValueError as exc:
            p.error(str(exc))
    if a.command == "pipe":
        a.format = "rgba"
        if a.input.is_dir():
            p.error("pipe requires one input file")
        if sys.stdout.isatty():
            p.error("pipe writes binary data: connect stdout to a binary consumer")
    elif a.command == "extract":
        a.format = "ogv"
    files = input_files(a.input)
    directory = a.input.is_dir()
    if directory and a.output.exists() and not a.output.is_dir():
        p.error("Directory input requires an output directory")
    if a.command == "convert" and not directory:
        expected = ".mp4" if a.format == "mp4" else ".mkv"
        if a.output.suffix.lower() != expected:
            p.error(f"--format {a.format} requires an {expected} output filename")
    if (
        a.command == "extract"
        and not directory
        and a.output.suffix.lower() not in (".ogv", ".ogg")
    ):
        p.error("extract requires an .ogv or .ogg output filename")
    failed = 0
    for index, src in enumerate(files, 1):
        if directory:
            print(f"BATCH {index}/{len(files)}: {src}", file=sys.stderr)
        dst = a.output
        if directory:
            suffix = {"mp4": ".mp4", "ffv1": ".mkv", "ogv": ".ogv"}[a.format]
            dst = a.output / src.relative_to(a.input).with_suffix(suffix)
            if dst.exists() and not a.overwrite:
                print(f"SKIP existing: {dst}", file=sys.stderr)
                continue
        try:
            if (
                directory
                and a.format != "ogv"
                and layout(src, a.force_mode)["frames"] == 0
            ):
                print(f"SKIP empty placeholder: {src}", file=sys.stderr)
                continue
            convert(src, dst, a)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            if not directory:
                raise
            failed += 1
            print(f"FAILED: {src}: {exc}", file=sys.stderr)
    return int(bool(failed))


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        return dispatch(a, p)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
