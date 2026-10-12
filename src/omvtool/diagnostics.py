"""Opt-in, local-only structural reports. Never include paths or media bytes."""

import json
import struct
from pathlib import Path

from . import __version__
from .header import inspect


def diagnose(source, output, consent=False):
    if not consent:
        raise ValueError(
            "No report written. --consent permits reading the first 168 bytes and "
            "up to 65536 payload bytes to extract structural metadata. The JSON "
            "contains file size and numeric header fields, but no paths, names, "
            "raw bytes, images, audio, hashes or machine information. Nothing is uploaded."
        )
    source, output = Path(source), Path(output)
    report = dict(
        schema_version=1, tool_version=__version__, file_size=source.stat().st_size
    )
    with source.open("rb") as stream:
        header = stream.read(168)
    report["header_bytes_available"] = len(header)
    # Named numeric fields only, even when the header version is unknown.
    report["candidate_header_fields"] = {
        name: struct.unpack_from("<I", header, offset)[0]
        for name, offset in (
            ("header_size", 0),
            ("version", 4),
            ("mode", 0x28),
            ("width", 0x2C),
            ("height", 0x30),
            ("frame_time_us", 0x3C),
            ("pages", 0x4C),
            ("frames", 0x50),
        )
        if len(header) >= offset + 4
    }
    try:
        metadata = inspect(source)
        report["metadata"] = {
            key: value
            for key, value in metadata.items()
            if key not in ("path", "prefix_hex", "serial")
        }
        report["status"] = (
            "known_header" if metadata["mode"] in (0, 1, 2) else "unknown_mode"
        )
    except ValueError:
        # Do not serialize exception text, which could contain private data.
        report["status"] = "unrecognized_or_damaged_structure"
    if source.resolve() == output.resolve():
        raise ValueError("Report output must differ from source")
    # Exclusive creation protects existing files; no parent directories are created.
    with output.open("x", encoding="utf8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"Local report written: {output}. Review its contents before manually attaching it to an issue. Nothing was uploaded."
    )
    return 0
