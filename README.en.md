# OMVTool

A streaming SiglusEngine OMV converter with H.264, HEVC and AV1 output. Reconstructs
BGR, packed BGR+alpha and YUV layouts, preserves rational frame rates and repeated
frames, and optionally retains all embedded audio tracks. No intermediate PNGs.

Requires **FFmpeg and ffprobe**. Place them beside the OMVTool executable (Windows:
`ffmpeg.exe`, `ffprobe.exe`); no PATH configuration is needed. The working directory,
PATH and explicit environment overrides are also supported. Run `omvtool doctor`
to check codecs and filters, or `omvtool doctor --test-encoders` to test encoding.
Python source installation requires Python 3.10+ and NumPy. Standalone binaries
bundle Python and NumPy, but not FFmpeg.

```console
python -m pip install .
omvtool doctor
omvtool convert input.omv -o output.mp4
omvtool convert input.omv -o hevc.mp4 --codec hevc
omvtool convert input.omv -o av1.mp4 --codec av1
omvtool convert input.omv -o av1_gpu.mp4 --codec av1 --encoder nvenc
omvtool convert effect.omv -o effect.mkv --format ffv1
omvtool convert mov -o converted
omvtool inspect input.omv --json
omvtool extract input.omv -o original.ogv
omvtool --help
```

Default MP4: H.264 CRF 16, slow preset, limited-range BT.709 YUV420p, black alpha
composite. Embedded AAC is copied; other audio becomes AAC 256 kb/s per track.
FFV1/MKV preserves decoded RGBA for modes 0/1 or YUV444 samples for mode 2 and
copies all embedded audio. MP4 is lossy. HEVC alpha is opt-in with `--alpha preserve` and requires a working alpha-enabled libx265 build; an actual encode/decode check runs first.

HEVC defaults to libx265 CRF 20 / slow; AV1 prefers libsvtav1 CRF 28 / preset 6,
with libaom-av1 as a fallback. Choose `--encoder nvenc`, `qsv`, `amf`, `vaapi` or
`videotoolbox` for hardware encoding. `--encoder auto` tests hardware before using
it and falls back to software; explicit choices fail if unavailable. Theora normally
decodes in software, and color/alpha reconstruction uses the CPU. Hardware quality
uses `--quality` (backend-specific); `--bitrate 8M` sets a target bitrate. See the manual.

`omvtool pipe input.omv` writes headerless packed RGBA frames to binary stdout.
It contains video only; read size and rational frame rate using `inspect`.
Use a binary-safe subprocess pipe; legacy Windows PowerShell text pipelines can
corrupt bytes. `extract` copies the entire embedded Ogg payload, including audio,
but does not reconstruct the special pixel layouts.

Supported header: 168 bytes, version 0x101, mode 0/1/2, Theora 4:4:4. Unknown
layouts fail rather than guessing. The default mode-2 interpretation is
full-range BT.601; `--yuv-range` and `--matrix` can override it. We have not
verified every SiglusEngine title or compared every output to the live game.

Directory conversions recurse, retain relative paths, skip existing outputs and
zero-frame placeholders, continue after individual failures, and return a
nonzero exit code if any item fails. Single-file conversions refuse overwrites.
All paths are local; no assets are uploaded.

See the [Chinese full manual](docs/usage.md), [format notes](docs/format.md),
and [references/comparison](docs/references.md).
MIT; bundled components retain their own licenses.

Thanks to omvdecoder, SiglusExtract and SiglusSceneScriptUtility for format and
implementation references; see [references and acknowledgements](docs/references.md).

Unknown layouts stop with a diagnostic hint. `omvtool diagnose INPUT -o report.json --consent` creates a local JSON of structural numeric fields only; review it before manually attaching it to an issue. No upload is performed. `--force-mode 0/1/2` overrides the declared mode while keeping version, dimensions and sampling checks. See the full manual for details.

Use `convert --fps 60` or `--fps 30000/1001` to duplicate/drop frames without changing playback speed. `--frames` counts output frames. Stage/frame/elapsed/ETA progress goes to stderr; disable it with `--no-progress`. Tagged v* builds publish a GitHub Release after all builds and checks pass. Tests stay in the source repository for CI, and are excluded from binary packages.

Use `convert --overwrite` to replace an existing output only after the complete temporary file has been written; the input is never overwritten. Without it, single-file conversion fails and directory conversion skips existing outputs.
