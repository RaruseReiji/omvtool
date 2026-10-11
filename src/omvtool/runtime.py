"""Locate external tools without inheriting frozen-app library search paths."""

import os
import shutil
import sys


def executable(name):
    value = os.environ.get("OMVTOOL_" + name.upper(), name)
    found = shutil.which(value)
    if not found:
        raise FileNotFoundError(
            f"{name} not found. Install FFmpeg or set OMVTOOL_{name.upper()}."
        )
    return found


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
