"""Siglus OMV -> MP4 / lossless MKV / standard binary RGBA stream.

Only Python stdlib + numpy + FFmpeg are required. Source files are read-only.
"""

from fractions import Fraction
import math
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from .header import inspect
from .runtime import executable, external_env
from .encoding import select_encoder, video_args, pixel_filter, device_args


def layout(path):
    m = inspect(path)
    w, vh, h = m["theora_width"], m["theora_height"], m["height"]
    mode = m["mode"]
    if mode not in (0, 1, 2):
        raise ValueError(f"Unsupported OMV mode {mode}; refusing to guess")
    if m["pixel_format"] != 3:
        raise ValueError(
            "Expected Theora 4:4:4; refusing to reinterpret subsampled planes"
        )
    if mode == 1:
        if w != m["width"] or vh != h + (h + 2) // 3:
            raise ValueError("Unexpected packed-alpha dimensions")
    elif mode == 0:
        if (w, vh) != (m["width"], h):
            raise ValueError("Unexpected BGR dimensions")
    else:
        # Translated files sometimes store macroblock dimensions (1088),
        # while Theora pic_height is the actual display size (1080).
        h = vh
    if not m["fps_num"] or not m["fps_den"]:
        raise ValueError("Invalid frame rate")
    m.update(output_width=w, output_height=h, alpha=(mode == 1))
    return m


def unpack(planes, meta, yuv_range="full", matrix="601"):
    h, mode = meta["output_height"], meta["mode"]
    p = planes[:, :h, :]
    rgba = np.empty((h, meta["output_width"], 4), dtype=np.uint8)
    if mode in (0, 1):
        rgba[:, :, :3] = p[::-1].transpose(1, 2, 0)
    else:
        y, u, v = p.astype(np.float32)
        u -= 128
        v -= 128
        if yuv_range == "limited":
            y = (y - 16) * (255 / 219)
            u *= 255 / 224
            v *= 255 / 224
        if matrix == "709":
            rgb = (y + 1.5748 * v, y - 0.187324 * u - 0.468124 * v, y + 1.8556 * u)
        else:
            rgb = (y + 1.402 * v, y - 0.344136 * u - 0.714136 * v, y + 1.772 * u)
        rgba[:, :, :3] = np.stack(rgb, axis=2).round().clip(0, 255).astype(np.uint8)
    if mode == 1:
        # Each plane contains H color rows, followed by ceil(H/3) alpha rows.
        rgba[:, :, 3] = planes[:, h:, :].reshape(-1, meta["output_width"])[:h]
    else:
        rgba[:, :, 3] = 255
    return rgba


def read_frame(stream, size):
    b = bytearray(size)
    view = memoryview(b)
    n = 0
    while n < size:
        got = stream.readinto(view[n:])
        if not got:
            if n:
                raise RuntimeError(f"Truncated raw frame: {n}/{size} bytes")
            return None
        n += got
    return b


def input_args(m, start, options=None, encoding=False):
    url = f"subfile,,start,{m['ogg_offset']},,:{m['path']}"
    args = [executable("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin"]
    if options:
        if encoding:
            args += device_args(options)
        if options.hwaccel != "none":
            args += ["-hwaccel", options.hwaccel]
            if options.hwaccel_device:
                args += ["-hwaccel_device", options.hwaccel_device]
    # Decode from the first frame: a seek into Theora repeat packets may have
    # no new AVFrame to initialize the output. Trim after CFR reconstruction.
    return args + ["-i", url, "-map", "0:v:0", "-an"]


def probe_media(m):
    """Inspect every stream in the embedded container, without decoding video."""
    url = f"subfile,,start,{m['ogg_offset']},,:{m['path']}"
    p = subprocess.run(
        [
            executable("ffprobe"),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            url,
        ],
        capture_output=True,
        env=external_env(),
    )
    if p.returncode:
        if not m["frames"]:
            return {"streams": [], "empty_placeholder": True}
        raise RuntimeError("ffprobe failed: " + p.stderr.decode(errors="replace"))
    return json.loads(p.stdout)


def mux_audio(video, m, output_format, policy, start, duration, streams):
    """Keep audio timing relative to the requested video interval, never synthesize BGM."""
    audio = [s for s in streams if s["codec_type"] == "audio"]
    if not audio or policy == "none":
        return
    fd, name = tempfile.mkstemp(
        prefix=video.stem + ".audio-", suffix=video.suffix, dir=video.parent
    )
    os.close(fd)
    muxed = Path(name)
    url = f"subfile,,start,{m['ogg_offset']},,:{m['path']}"
    cmd = [
        executable("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(video),
    ]
    if start:
        cmd += ["-ss", str(start)]
    cmd += [
        "-i",
        url,
        "-map",
        "0:v:0",
        "-map",
        "1:a",
        "-map_metadata",
        "1",
        "-c:v",
        "copy",
        "-t",
        str(float(duration)),
    ]
    for i, s in enumerate(audio):
        copy = policy == "copy" or output_format == "ffv1" or s["codec_name"] == "aac"
        cmd += [f"-c:a:{i}", "copy" if copy else "aac"]
        if not copy:
            cmd += [f"-b:a:{i}", "256k"]
    if output_format == "mp4":
        cmd += ["-movflags", "+faststart"]
    try:
        run_checked(cmd + [str(muxed)])
        # Both files belong to this conversion; final destination is still untouched.
        os.replace(muxed, video)
    finally:
        if muxed.exists():
            muxed.unlink()


def run_checked(cmd):
    subprocess.run(cmd, check=True, env=external_env())


def convert(source, output, args):
    m = layout(source)
    if args.format == "mp4":
        args.selected_encoder = select_encoder(
            args, m["output_width"], m["output_height"]
        )
        # Validate the full profile before creating temporary files.
        video_args(args)
        device_args(args)
        print(f"ENCODER: {args.selected_encoder}", file=sys.stderr)
    media = probe_media(m) if args.format in ("mp4", "ffv1", "inspect") else None
    if media is not None:
        m["audio_streams"] = [
            {
                k: s[k]
                for k in (
                    "index",
                    "codec_name",
                    "sample_rate",
                    "channels",
                    "start_time",
                    "duration",
                )
                if k in s
            }
            for s in media["streams"]
            if s["codec_type"] == "audio"
        ]
    print(
        f"INPUT: {m['path']}; mode={m['mode']}; {m['output_width']}x{m['output_height']}; fps={m['fps_num']}/{m['fps_den']}",
        file=sys.stderr,
    )
    if not m["frames"] and args.format != "ogv":
        raise ValueError("Header-only OMV placeholder: zero video frames")
    fps = Fraction(m["fps_num"], m["fps_den"])
    start_frame = math.floor(Fraction(str(args.start)) * fps)
    actual_start = float(Fraction(start_frame, 1) / fps)
    remaining = m["frames"] - start_frame
    frame_limit = min(remaining, args.frames) if args.frames else remaining
    if frame_limit <= 0 and args.format != "ogv":
        raise ValueError("Start time is beyond the end of the video")
    # Theora duplicate packets may yield no decoded AVFrame. Reconstruct CFR
    # from timestamps, and preserve repeated trailing frames using the OMV table.
    timing = (
        f"fps=fps={m['fps_num']}/{m['fps_den']}:start_time=0,tpad=stop_mode=clone:stop=-1,"
        f"trim=start_frame={start_frame},setpts=PTS-STARTPTS"
    )
    if args.format == "rgba":
        if os.name == "nt":
            import msvcrt

            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        sink = sys.stdout.buffer
        tmp = None
    else:
        output = Path(output)
        if output.resolve() == Path(source).resolve():
            raise ValueError("Output must differ from source")
        if output.exists():
            raise FileExistsError(f"Output exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            prefix=output.stem + ".partial-", suffix=output.suffix, dir=output.parent
        )
        os.close(fd)
        tmp = Path(name)
    decoder = encoder = None
    count = 0
    try:
        if args.format == "ogv":
            with open(source, "rb") as src, open(tmp, "wb") as dst:
                src.seek(m["ogg_offset"])
                shutil.copyfileobj(src, dst, 1024 * 1024)
        elif args.format == "mp4" and m["mode"] == 2:
            # Native YUV path: no RGB round trip, no Python frame copying.
            cmd = input_args(m, args.start, args, encoding=True)
            cmd += ["-frames:v", str(frame_limit)]
            vf = (
                timing + "," + f"scale=in_range={args.yuv_range}:out_range=limited:"
                f"in_color_matrix=bt{args.matrix}:out_color_matrix=bt709,"
                "pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1," + pixel_filter(args)
            )
            cmd += ["-vf", vf] + mp4_args(args) + ["-y", str(tmp)]
            run_checked(cmd)
        elif args.format == "ffv1" and m["mode"] == 2:
            # Preserve decoded YUV samples exactly, including 4:4:4 chroma.
            cmd = input_args(m, args.start, args)
            cmd += ["-frames:v", str(frame_limit)]
            cmd += [
                "-vf",
                timing
                + ","
                + f"setparams=range={args.yuv_range}:colorspace="
                + ("smpte170m" if args.matrix == "601" else "bt709"),
                "-c:v",
                "ffv1",
                "-level",
                "3",
                "-g",
                "1",
                "-pix_fmt",
                "yuv444p",
                "-color_range",
                "pc" if args.yuv_range == "full" else "tv",
                "-colorspace",
                "smpte170m" if args.matrix == "601" else "bt709",
                "-y",
                str(tmp),
            ]
            run_checked(cmd)
        else:
            if args.format != "rgba":
                enc = [
                    executable("ffmpeg"),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-y",
                    "-f",
                    "rawvideo",
                    "-pixel_format",
                    "rgba",
                    "-video_size",
                    f"{m['output_width']}x{m['output_height']}",
                    "-framerate",
                    f"{m['fps_num']}/{m['fps_den']}",
                    "-i",
                    "pipe:0",
                    "-an",
                ]
                if args.format == "mp4":
                    enc[1:1] = device_args(args)
                    enc += [
                        "-vf",
                        "scale=in_range=full:out_range=limited:out_color_matrix=bt709,"
                        "pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1," + pixel_filter(args),
                    ] + mp4_args(args)
                else:
                    enc += [
                        "-c:v",
                        "ffv1",
                        "-level",
                        "3",
                        "-g",
                        "1",
                        "-pix_fmt",
                        "bgra",
                    ]
                encoder = subprocess.Popen(
                    enc + [str(tmp)], stdin=subprocess.PIPE, env=external_env()
                )
                sink = encoder.stdin
            cmd = input_args(m, args.start, args)
            cmd += [
                "-frames:v",
                str(frame_limit),
                "-vf",
                timing,
                "-fps_mode",
                "passthrough",
                "-pix_fmt",
                "yuv444p",
                "-f",
                "rawvideo",
                "pipe:1",
            ]
            decoder = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=external_env())
            shape = (3, m["theora_height"], m["theora_width"])
            size = int(np.prod(shape))
            while True:
                raw = read_frame(decoder.stdout, size)
                if raw is None:
                    break
                rgba = unpack(
                    np.frombuffer(raw, np.uint8).reshape(shape),
                    m,
                    args.yuv_range,
                    args.matrix,
                )
                if args.format == "mp4" and m["alpha"] and args.alpha == "black":
                    # Straight alpha, round to nearest; original hidden RGB is retained in FFV1/RGBA.
                    rgb = rgba[:, :, :3].astype(np.uint16)
                    rgba[:, :, :3] = ((rgb * rgba[:, :, 3:4] + 127) // 255).astype(
                        np.uint8
                    )
                    rgba[:, :, 3] = 255
                sink.write(rgba.tobytes())
                count += 1
            decoder.stdout.close()
            if decoder.wait():
                raise RuntimeError("FFmpeg decoder failed")
            if encoder:
                encoder.stdin.close()
                if encoder.wait():
                    raise RuntimeError("FFmpeg encoder failed")
            else:
                sink.flush()
            if not count:
                raise RuntimeError("No video frames decoded")
        if tmp:
            if args.format in ("mp4", "ffv1"):
                mux_audio(
                    tmp,
                    m,
                    args.format,
                    args.audio,
                    actual_start,
                    Fraction(frame_limit * m["fps_den"], m["fps_num"]),
                    media["streams"],
                )
            # Atomic no-clobber publication on Windows and POSIX (same filesystem).
            os.link(tmp, output)
            tmp.unlink()
        print(
            f'OK: {output or "stdout"}; streamed frames={count or "native ffmpeg/extract"}',
            file=sys.stderr,
        )
    finally:
        for child in (decoder, encoder):
            if child and child.poll() is None:
                child.kill()
                child.wait()
        if tmp and tmp.exists():
            tmp.unlink()


def mp4_args(args):
    return video_args(args) + ["-movflags", "+faststart"]
