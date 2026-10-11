"""Locate external tools without inheriting frozen-app library search paths."""

import os
import shutil
import sys
from pathlib import Path


def executable(name):
    override = os.environ.get("OMVTOOL_" + name.upper())
    if override:
        found = shutil.which(override)
        if not found:
            raise FileNotFoundError(
                f"OMVTOOL_{name.upper()} does not point to an executable: {override}"
            )
        return found
    filename = name + (".exe" if os.name == "nt" else "")
    # Frozen builds live beside their executable, never in the onefile temp dir.
    app_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(sys.argv[0]).resolve().parent
    )
    directories = (
        (app_dir, Path.cwd())
        if getattr(sys, "frozen", False)
        else (app_dir, Path(__file__).resolve().parents[2], Path.cwd())
    )
    for directory in dict.fromkeys(directories):
        candidate = directory / filename
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} not found. Place {filename} beside OMVTool or in the working directory, add it to PATH, or set OMVTOOL_{name.upper()}."
    )


def external_env():
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        for key in ("LD_LIBRARY_PATH", "LIBPATH"):
            original = env.pop(key + "_ORIG", None)
            if original is None:
                env.pop(key, None)
            else:
                env[key] = original
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.SetDllDirectoryW(None)
    return env
