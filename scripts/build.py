"""Build, verify and package a native executable on the current platform."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import sysconfig
from pathlib import Path

from verify_binary import verify

ROOT = Path(__file__).resolve().parents[1]


def licenses(destination):
    destination.mkdir()
    count = {}
    for name in ("numpy", "pyinstaller"):
        dist = importlib.metadata.distribution(name)
        selected = [
            f
            for f in dist.files or []
            if any(part.lower().startswith(("license", "copying")) for part in f.parts)
        ]
        if not selected:
            raise RuntimeError(f"Cannot locate installed {name} license files")
        for file in selected:
            source = Path(dist.locate_file(file))
            if source.is_file():
                relative = Path(*[p for p in file.parts if p not in (".", "..")])
                target = destination / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        count[name] = len(selected)
    candidates = [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sysconfig.get_path("stdlib")) / "LICENSE",
    ]
    license_path = next((p for p in candidates if p.is_file()), None)
    if license_path:
        shutil.copy2(license_path, destination / "CPython-LICENSE.txt")
    else:
        # Some hosted Linux distributions omit the upstream license text.
        import urllib.request

        url = f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE"
        with urllib.request.urlopen(url, timeout=30) as response:
            text = response.read()
        if b"PYTHON SOFTWARE FOUNDATION LICENSE" not in text:
            raise RuntimeError("Unexpected CPython license content")
        (destination / "CPython-LICENSE.txt").write_bytes(text)
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--architecture", choices=["x64", "arm64"])
    a = p.parse_args()
    aliases = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}
    actual = aliases.get(platform.machine().lower())
    if (
        not actual
        or struct.calcsize("P") != 8
        or a.architecture
        and actual != a.architecture
    ):
        raise RuntimeError(f"Unexpected Python architecture: {platform.machine()}")
    from omvtool import __version__

    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{__version__}":
        raise RuntimeError("Release tag must match the package version")
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[
        platform.system()
    ]
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--noupx",
            "--python-option",
            "X utf8",
            "--name",
            "omvtool",
            "--paths",
            str(ROOT / "src"),
            "--copy-metadata",
            "numpy",
            str(ROOT / "scripts" / "entrypoint.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    binary = ROOT / "dist" / ("omvtool.exe" if system == "windows" else "omvtool")
    verify(binary, actual)
    name = f"omvtool-{__version__}-{system}-{actual}"
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    stage = ROOT / "build" / name
    stage.mkdir(parents=True, exist_ok=False)
    shutil.copy2(binary, stage / binary.name)
    # Explicit allowlist: never archive the checkout or local research evidence.
    for file in (
        "README.md",
        "README.en.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CHANGELOG.md",
        "VALIDATION.md",
    ):
        shutil.copy2(ROOT / file, stage / file)
    shutil.copytree(ROOT / "docs", stage / "docs")
    shutil.copytree(ROOT / "examples", stage / "examples")
    notices = licenses(stage / "licenses")
    versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "pyinstaller", "pyinstaller-hooks-contrib", "setuptools")
    }
    info = dict(
        version=__version__,
        system=system,
        architecture=actual,
        python=platform.python_version(),
        dependencies=versions,
        commit=os.environ.get("GITHUB_SHA"),
        ffmpeg_bundled=False,
        license_files=notices,
    )
    (stage / "build-info.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf8"
    )
    extension = "zip" if system == "windows" else "gztar"
    archive = Path(
        shutil.make_archive(
            str(release / name), extension, root_dir=stage.parent, base_dir=stage.name
        )
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="ascii"
    )
    print(f"PACKAGED: {archive}\nSHA256: {digest}")


if __name__ == "__main__":
    main()
