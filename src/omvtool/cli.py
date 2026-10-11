"""Stable command-line interface. Binary data uses stdout; progress uses stderr."""

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from . import __version__
from .converter import convert, layout, probe_media
from .runtime import executable, external_env


def options(parser):
    parser.add_argument("--start", type=float, default=0, metavar="SECONDS")
    parser.add_argument("--frames", type=int, metavar="COUNT")
    parser.add_argument("--yuv-range", choices=["full", "limited"], default="full")
    parser.add_argument("--matrix", choices=["601", "709"], default="601")


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
    c.add_argument("--format", choices=["mp4", "ffv1"], default="mp4")
    c.add_argument("--crf", type=int, default=16)
    c.add_argument(
        "--preset",
        default="slow",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
    )
    c.add_argument(
        "--alpha",
        choices=["black", "discard"],
        default="black",
        help="MP4 background; lossless output always preserves alpha",
    )
    c.add_argument("--audio", choices=["auto", "copy", "none"], default="auto")
    options(c)
    i = sub.add_parser(
        "inspect", help="Show layout, frame rate and embedded audio streams"
    )
    i.add_argument("input", type=Path)
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
    r = sub.add_parser(
        "pipe", help="Write headerless RGBA video to binary stdout (one file)"
    )
    r.add_argument("input", type=Path)
    options(r)
    sub.add_parser("doctor", help="Check FFmpeg, ffprobe and required codecs/filters")
    return p


def doctor():
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
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"{name}: ERROR: {exc}", file=sys.stderr)
            failed = True
    return int(failed)


def inspect_input(source, as_json):
    files = input_files(source)
    rows, failed = [], False
    for src in files:
        try:
            m = layout(src)
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
        return doctor()
    if a.command == "inspect":
        return inspect_input(a.input, a.json)
    # Normalize all subcommands to the conversion core's small options structure.
    defaults = dict(
        format="mp4",
        crf=16,
        preset="slow",
        alpha="black",
        audio="auto",
        start=0,
        frames=None,
        yuv_range="full",
        matrix="601",
        output=None,
    )
    for key, value in defaults.items():
        if not hasattr(a, key):
            setattr(a, key, value)
    if (
        not math.isfinite(a.start)
        or a.start < 0
        or not 0 <= a.crf <= 51
        or (a.frames is not None and a.frames <= 0)
    ):
        p.error("Require finite --start >= 0, --crf 0..51 and --frames > 0")
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
    for src in files:
        dst = a.output
        if directory:
            suffix = {"mp4": ".mp4", "ffv1": ".mkv", "ogv": ".ogv"}[a.format]
            dst = a.output / src.relative_to(a.input).with_suffix(suffix)
            if dst.exists():
                print(f"SKIP existing: {dst}", file=sys.stderr)
                continue
        try:
            if directory and a.format != "ogv" and layout(src)["frames"] == 0:
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
