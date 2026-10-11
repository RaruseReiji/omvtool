"""Verify PE/ELF/Mach-O architecture and that the frozen entry point starts."""

import argparse
import struct
import subprocess
from pathlib import Path


def architecture(path):
    h = path.read_bytes()
    if h[:2] == b"MZ":
        offset = struct.unpack_from("<I", h, 0x3C)[0]
        if h[offset : offset + 4] != b"PE\0\0":
            raise ValueError("Invalid PE signature")
        return {0x8664: "x64", 0xAA64: "arm64"}[
            struct.unpack_from("<H", h, offset + 4)[0]
        ]
    if h[:4] == b"\x7fELF":
        if h[4:6] != b"\x02\x01":
            raise ValueError("Expected 64-bit little-endian ELF")
        return {62: "x64", 183: "arm64"}[struct.unpack_from("<H", h, 18)[0]]
    if h[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("Expected 64-bit Mach-O")
    return {0x01000007: "x64", 0x0100000C: "arm64"}[struct.unpack_from("<I", h, 4)[0]]


def verify(path, expected):
    actual = architecture(path)
    if actual != expected:
        raise ValueError(f"Expected {expected}, found {actual}")
    for args in (["--version"], ["--help"], ["convert", "--help"], ["pipe", "--help"]):
        result = subprocess.run(
            [str(path.resolve()), *args],
            capture_output=True,
            encoding="utf8",
            timeout=60,
            check=True,
        )
        if "omvtool" not in result.stdout:
            raise RuntimeError(f"Unexpected startup output: {result.stdout}")
    print(f"PASS: {path.name}: {actual}, startup and subcommand help")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary", type=Path)
    p.add_argument("architecture", choices=["x64", "arm64"])
    a = p.parse_args()
    verify(a.binary, a.architecture)
