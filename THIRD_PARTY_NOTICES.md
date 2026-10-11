# Third-party components

OMVTool's independent Python implementation is distributed under MIT. No upstream
omvdecoder Rust source, SiglusEngine source, game assets or proprietary libraries
are included. Format research references are listed in `docs/references.md`.

Binary builds contain CPython, NumPy and the PyInstaller bootloader. Their licenses
remain applicable independently of OMVTool's MIT license. The build script copies
the installed CPython, NumPy (including wheel library notices) and PyInstaller
license files into the release's `licenses/` directory. NumPy wheels may contain
OpenBLAS and other components; consult the notices from that particular wheel.

- [CPython license](https://docs.python.org/3/license.html)
- [NumPy license](https://github.com/numpy/numpy/blob/main/LICENSE.txt)
- [PyInstaller license and bootloader exception](https://pyinstaller.org/en/stable/license.html)

FFmpeg and ffprobe are external executables and are **not bundled**. Users supply
their own installation. Its license depends on its build configuration, including
optional GPL components such as libx264. See [FFmpeg legal information](https://ffmpeg.org/legal.html).
