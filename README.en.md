# OMVTool

A streaming SiglusEngine `.omv` converter with H.264, HEVC and AV1 MP4 output,
lossless FFV1/MKV output, and support for BGR, packed BGR+alpha and YUV layouts.
It preserves rational frame rates and repeated frames without intermediate PNGs.
Embedded audio tracks are retained when present.

## Quick start

OMVTool requires **FFmpeg and ffprobe**. Download them from the [official FFmpeg
page](https://ffmpeg.org/download.html). On Windows, the builds at [gyan.dev](https://www.gyan.dev/ffmpeg/builds/),
such as [`ffmpeg-git-full.7z`](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z),
can be extracted and `bin\ffmpeg.exe` plus `bin\ffprobe.exe` copied beside
`omvtool.exe`; alternatively add them to `PATH`. macOS and Linux users can
download the corresponding executables from the official page and keep their
execute permission. The working directory, `PATH`, and explicit environment
overrides are supported. Run `omvtool doctor` to check the installation.

Standalone binaries bundle Python and NumPy but not FFmpeg. Download the package
for your platform and architecture, extract it, and run `omvtool` (`omvtool.exe`
on Windows). Source installation requires Python 3.10+:

```console
python -m pip install .
omvtool doctor

# H.264 MP4 (CRF 16 / slow) with embedded audio retained
omvtool convert "movie.omv" -o "movie.mp4"

# HEVC and AV1 software encoding
omvtool convert "movie.omv" -o "hevc.mp4" --codec hevc
omvtool convert "movie.omv" -o "av1.mp4" --codec av1

# NVIDIA hardware encoding; --encoder auto also probes available hardware
omvtool convert "movie.omv" -o "av1_gpu.mp4" --codec av1 --encoder nvenc

# Change output frame rate by duplicating or dropping frames
omvtool convert "movie.omv" -o "movie_60.mp4" --fps 60

# Explicitly replace an existing output after successful conversion
omvtool convert "movie.omv" -o "movie.mp4" --overwrite

# Lossless decoded pixels, including alpha where applicable
omvtool convert "effect.omv" -o "effect.mkv" --format ffv1

# Recursive directory conversion
omvtool convert "mov" -o "converted"

omvtool inspect "movie.omv" --json
omvtool extract "movie.omv" -o "original.ogv"
```

PowerShell users running a release from the current directory can use
`./omvtool.exe`. After source installation, `python -m omvtool` accepts the same
arguments. Quote paths containing spaces or non-ASCII characters.

## Behavior and limitations

Default MP4 uses H.264 CRF 16 / slow, limited-range BT.709 YUV420p, and composites
alpha over black. HEVC defaults to libx265 CRF 20 / slow; AV1 prefers libsvtav1
CRF 28 / preset 6 and falls back to libaom-av1. Hardware encoders include NVENC,
QSV, AMF, VAAPI and VideoToolbox when supported by the FFmpeg build, GPU and
driver. Use `--quality` or `--bitrate` for backend-specific control. `--encoder
auto` probes hardware and falls back to software; an explicit unavailable encoder
fails. HEVC alpha preservation is opt-in with `--alpha preserve` and requires an
alpha-capable libx265 build.

`--fps` accepts values such as `24`, `29.97`, `60` and `30000/1001`; it changes
the number of output frames while preserving playback speed. `--overwrite` uses a
temporary file and replaces the destination only after a complete successful
conversion; input files are never overwritten. Directory conversion recurses,
retains relative paths, skips existing outputs and zero-frame placeholders, and
continues after individual failures.

`omvtool pipe` writes headerless packed RGBA frames to binary stdout. Read the
dimensions and rational frame rate with `inspect` and use a binary-safe subprocess
pipe. `extract` copies the complete embedded Ogg payload, including audio, but does
not reconstruct special pixel layouts.

Supported files have a 168-byte header, version `0x101`, mode 0/1/2 and Theora
4:4:4 payloads. Unknown layouts fail rather than guessing. Mode 2 defaults to
full-range BT.601; `--yuv-range` and `--matrix` can override it. Theora decoding
and color/alpha reconstruction use the CPU. Run `omvtool diagnose INPUT -o
report.json --consent` to create a local structural report for an unknown file;
review it before sharing manually. `--force-mode 0/1/2` can override a declared
mode while retaining header and sampling checks.

See the [Chinese full manual](docs/usage.md), [format notes](docs/format.md),
[development guide](docs/development.md), and [references/comparison](docs/references.md).

Thanks to [omvdecoder](https://github.com/xmoezzz/omvdecoder), [SiglusExtract](https://github.com/xmoezzz/SiglusExtract)
and [SiglusSceneScriptUtility](https://github.com/Jirehlov/SiglusSceneScriptUtility)
for format and implementation references. MIT license; bundled components retain
their own licenses.
