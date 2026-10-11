# OMVTool

An independent streaming SiglusEngine OMV converter. Reconstructs the supported
BGR, packed BGR+alpha and YUV layouts, preserves rational frame rates and repeated
frames, and optionally retains all embedded audio tracks. No intermediate PNGs.

Requires external **FFmpeg and ffprobe**. The FFmpeg build must support Theora,
libx264, FFV1, AAC and the filters checked by `omvtool doctor`.
Python source installation requires Python 3.10+ and NumPy. Standalone binaries
bundle Python and NumPy, but not FFmpeg.

```console
python -m pip install .
omvtool doctor
omvtool convert input.omv -o output.mp4
omvtool convert effect.omv -o effect.mkv --format ffv1
omvtool convert mov -o converted
omvtool inspect input.omv --json
omvtool extract input.omv -o original.ogv
omvtool --help
```

Default MP4: H.264 CRF 16, slow preset, limited-range BT.709 YUV420p, black alpha
composite. Embedded AAC is copied; other audio becomes AAC 256 kb/s per track.
FFV1/MKV preserves decoded RGBA for modes 0/1 or YUV444 samples for mode 2 and
copies all embedded audio. MP4 is lossy and does not retain alpha.

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
[references/comparison](docs/references.md), and [release instructions](docs/release.md).
MIT; bundled components retain their own licenses.
