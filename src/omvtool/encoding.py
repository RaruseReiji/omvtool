"""Codec profiles and hardware encoder probing using the selected FFmpeg build."""

import functools
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from copy import copy

from .runtime import executable, external_env

SOFTWARE = {
    "h264": ("libx264",),
    "hevc": ("libx265",),
    "av1": ("libsvtav1", "libaom-av1"),
}
HARDWARE = {
    codec: {
        backend: f"{codec}_{backend}" for backend in ("nvenc", "qsv", "amf", "vaapi")
    }
    for codec in SOFTWARE
}
HARDWARE["h264"]["videotoolbox"] = "h264_videotoolbox"
HARDWARE["hevc"]["videotoolbox"] = "hevc_videotoolbox"
X26_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)


@functools.lru_cache(maxsize=16)
def encoder_list(ffmpeg):
    p = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=True,
        env=external_env(),
    )
    return {
        parts[1]
        for line in p.stdout.splitlines()
        if len(parts := line.split()) >= 2 and parts[0].startswith("V")
    }


def backend(encoder):
    if encoder.startswith("lib"):
        return "software"
    return encoder.rsplit("_", 1)[1]


def validate(a):
    if getattr(a, "alpha", "black") == "preserve":
        if (
            a.format != "mp4"
            or a.codec != "hevc"
            or a.encoder not in ("software", "libx265")
        ):
            raise ValueError(
                "--alpha preserve requires --codec hevc --encoder software (libx265); use FFV1 for lossless alpha"
            )
    if a.format == "ffv1":
        if (
            a.codec != "h264"
            or a.encoder != "software"
            or any(
                x is not None
                for x in (a.crf, a.quality, a.bitrate, a.preset, a.encode_device)
            )
        ):
            raise ValueError(
                "--format ffv1 cannot be combined with lossy codec/encoder/quality options"
            )
        return
    if a.crf is not None and not 0 <= a.crf <= (63 if a.codec == "av1" else 51):
        raise ValueError("--crf must be 0..63 for AV1, or 0..51 for H.264/HEVC")
    if a.bitrate is not None and (
        not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?[kKmMgG]?", a.bitrate)
    ):
        raise ValueError(
            "--bitrate must be a positive FFmpeg bitrate such as 8M or 4000k"
        )
    if a.quality is not None and not 0 <= a.quality <= 100:
        raise ValueError("--quality must be within the selected hardware encoder range")
    if a.encoder == "auto" and any(
        x is not None for x in (a.crf, a.quality, a.preset, a.encode_device)
    ):
        raise ValueError(
            "--encoder auto accepts defaults or --bitrate; select a backend for encoder-specific options"
        )


def device_args(a):
    b = backend(a.selected_encoder)
    if b == "vaapi":
        return ["-vaapi_device", a.encode_device or "/dev/dri/renderD128"]
    if b == "qsv" and a.encode_device:
        return ["-qsv_device", a.encode_device]
    if a.encode_device and b != "nvenc":
        raise ValueError("--encode-device is supported for NVENC, QSV and VAAPI")
    return []


def pixel_filter(a):
    if getattr(a, "alpha", "black") == "preserve":
        return "format=yuva420p"
    b = backend(a.selected_encoder)
    if b == "vaapi":
        return "format=nv12,hwupload"
    return "format=nv12" if b == "qsv" else "format=yuv420p"


def video_args(a):
    enc = a.selected_encoder
    b = backend(enc)
    out = ["-c:v", enc]
    if b == "software":
        if a.quality is not None:
            raise ValueError(
                "--quality is for hardware encoders; use --crf with software encoders"
            )
        preset = a.preset or ("6" if a.codec == "av1" else "slow")
        if enc in ("libx264", "libx265"):
            if preset not in X26_PRESETS:
                raise ValueError(
                    f'{enc} preset must be one of: {", ".join(X26_PRESETS)}'
                )
            out += ["-preset", preset]
        else:
            limit = 13 if enc == "libsvtav1" else 8
            if not preset.isdigit() or not 0 <= int(preset) <= limit:
                raise ValueError(f"{enc} preset must be 0..{limit}")
            out += ["-preset" if enc == "libsvtav1" else "-cpu-used", preset]
        if a.bitrate:
            out += ["-b:v", a.bitrate]
        else:
            quality = (
                a.crf
                if a.crf is not None
                else {"h264": 16, "hevc": 20, "av1": 28}[a.codec]
            )
            out += ["-crf", str(quality)]
            if enc == "libaom-av1":
                out += ["-b:v", "0"]
    else:
        if a.crf is not None:
            raise ValueError("Hardware encoders use --quality or --bitrate, not --crf")
        limit = 100 if b == "videotoolbox" else 51
        if a.quality is not None and not 0 <= a.quality <= limit:
            raise ValueError(f"{enc} --quality must be 0..{limit}")
        q = str(
            a.quality if a.quality is not None else (65 if b == "videotoolbox" else 20)
        )
        if b == "nvenc":
            preset = a.preset or "p5"
            if preset not in ("p1", "p2", "p3", "p4", "p5", "p6", "p7"):
                raise ValueError("NVENC preset must be p1..p7")
            out += ["-preset", preset, "-rc", "vbr"]
            out += ["-b:v", a.bitrate] if a.bitrate else ["-cq", q, "-b:v", "0"]
            if a.encode_device:
                if not a.encode_device.isdigit():
                    raise ValueError(
                        "NVENC --encode-device must be a nonnegative GPU index"
                    )
                out += ["-gpu", a.encode_device]
        elif b == "qsv":
            preset = a.preset or "medium"
            if preset not in (
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
                "slower",
                "veryslow",
            ):
                raise ValueError("Invalid QSV preset")
            out += ["-preset", preset]
            out += ["-b:v", a.bitrate] if a.bitrate else ["-global_quality", q]
        elif b == "amf":
            if a.preset:
                out += ["-quality", a.preset]
            out += (
                ["-rc", "vbr_peak", "-b:v", a.bitrate]
                if a.bitrate
                else ["-rc", "cqp", "-qp_i", q, "-qp_p", q]
            )
        elif b == "vaapi":
            if a.preset:
                raise ValueError("VAAPI does not use --preset")
            out += (
                ["-b:v", a.bitrate]
                if a.bitrate
                else ["-rc_mode", "CQP", "-global_quality", q]
            )
        elif b == "videotoolbox":
            if a.preset:
                raise ValueError("VideoToolbox does not use --preset")
            out += ["-allow_sw", "0"]
            out += ["-b:v", a.bitrate] if a.bitrate else ["-q:v", q]
    out += [
        "-pix_fmt",
        (
            "+yuva420p"
            if getattr(a, "alpha", "black") == "preserve"
            else ("vaapi" if b == "vaapi" else ("nv12" if b == "qsv" else "yuv420p"))
        ),
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
    ]
    if a.codec == "hevc":
        out += ["-tag:v", "hvc1"]
    return out


def probe_alpha(a):
    """Require real MP4 alpha round-trip; a listed pixel format is insufficient."""
    if a.selected_encoder != "libx265":
        return False, "Only libx265 alpha is currently supported"
    return _probe_alpha(executable("ffmpeg"), tuple(video_args(a)))


@functools.lru_cache(maxsize=16)
def _probe_alpha(ffmpeg, args):
    width, height = 256, 192
    # Constant RGB with an independent alpha ramp catches opaque fallback.
    row = b"".join(bytes((80, 120, 160, x)) for x in range(width))
    try:
        with tempfile.TemporaryDirectory(prefix="omvtool-alpha-") as folder:
            output = Path(folder) / "probe.mp4"
            encoded = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-nostdin",
                    "-f",
                    "rawvideo",
                    "-pixel_format",
                    "rgba",
                    "-video_size",
                    f"{width}x{height}",
                    "-framerate",
                    "30",
                    "-i",
                    "pipe:0",
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=in_range=full:out_range=limited:out_color_matrix=bt709,format=yuva420p",
                    *args,
                    str(output),
                ],
                input=row * height,
                capture_output=True,
                timeout=30,
                env=external_env(),
            )
            if encoded.returncode:
                lines = encoded.stderr.decode(errors="replace").splitlines()
                return False, next(
                    (line for line in lines if "alpha" in line.lower()),
                    "libx265 trial encoding failed",
                )
            decoded = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(output),
                    "-vf",
                    "alphaextract",
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "gray",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ],
                capture_output=True,
                timeout=30,
                env=external_env(),
            )
            pixels = decoded.stdout
            if decoded.returncode or len(pixels) != width * height:
                return False, "Encoded alpha could not be decoded by this FFmpeg"
            error = sum(
                abs(value - (i % width)) for i, value in enumerate(pixels)
            ) / len(pixels)
            if error > 16 or min(pixels) >= 32 or max(pixels) <= 223:
                return (
                    False,
                    "Alpha ramp was lost or severely distorted (try a lower --crf)",
                )
            return True, "HEVC alpha MP4 round-trip passed"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, type(exc).__name__ + " during alpha trial encoding"


def probe_encoder(a, width=256, height=192):
    """Compiled-in encoder names alone do not establish driver/device availability."""
    try:
        cmd = [
            executable("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
        ] + device_args(a)
        cmd += (
            [
                "-f",
                "lavfi",
                "-i",
                f"color=size={width + width % 2}x{height + height % 2}:rate=30",
                "-frames:v",
                "1",
                "-vf",
                pixel_filter(a),
            ]
            + video_args(a)
            + ["-f", "null", "-"]
        )
        result = subprocess.run(
            cmd, capture_output=True, env=external_env(), timeout=30
        )
        return result.returncode == 0, result.stderr.decode(errors="replace").strip()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def select_encoder(a, width, height):
    validate(a)
    available = encoder_list(executable("ffmpeg"))
    if a.encoder == "auto":
        candidates = (
            ("videotoolbox",)
            if sys.platform == "darwin"
            else ("nvenc", "qsv", "amf", "vaapi")
        )
        for name in candidates:
            enc = HARDWARE[a.codec].get(name)
            if enc not in available:
                continue
            candidate = copy(a)
            candidate.selected_encoder = enc
            ok, reason = probe_encoder(candidate, width, height)
            if ok:
                return enc
            print(
                f'UNAVAILABLE {enc}: {reason.splitlines()[-1] if reason else "probe failed"}',
                file=sys.stderr,
            )
        print("No working hardware encoder found; using software.", file=sys.stderr)
        requested = "software"
    else:
        requested = a.encoder
    if requested == "software":
        enc = next((enc for enc in SOFTWARE[a.codec] if enc in available), None)
    else:
        enc = HARDWARE[a.codec].get(requested, requested)
        if enc not in (*SOFTWARE[a.codec], *HARDWARE[a.codec].values()):
            raise ValueError(
                f"Encoder {requested} does not support selected codec {a.codec}"
            )
    if enc not in available:
        raise ValueError(
            f"FFmpeg encoder unavailable: {enc or a.codec}; run omvtool doctor"
        )
    return enc
