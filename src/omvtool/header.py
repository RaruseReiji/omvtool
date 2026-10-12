"""Parse the supported OMV 0x101 header and embedded Theora identification."""

import struct
from pathlib import Path


class UnsupportedFormat(ValueError):
    def __str__(self):
        return super().__str__() + (
            ". Possible new or damaged layout. No report was collected or uploaded. "
            "Review collection scope with omvtool diagnose --help. To consent and create a local structural report, run: "
            'omvtool diagnose "INPUT.omv" -o report.json --consent; '
            "review the JSON and attach it manually to an issue."
        )


def inspect(path):
    path = Path(path).resolve()
    with open(path, "rb") as f:
        b = f.read(168)
        if len(b) != 168 or b[:8] != bytes.fromhex("a800000001010000"):
            raise UnsupportedFormat("Unsupported OMV header/version")
        off = struct.unpack_from("<I", b)[0]
        pages, frames = struct.unpack_from("<II", b, 0x4C)
        ogg = off + pages * 28 + frames * 32
        if not off <= ogg < path.stat().st_size:
            raise ValueError("Invalid OMV table sizes")
        f.seek(ogg)
        embedded = f.read(65536)
    if embedded[:6] != b"OggS\x00\x02":
        raise ValueError("Ogg BOS page missing at computed payload offset")
    th = embedded.find(b"\x80theora")
    if th < 0:
        raise ValueError("No Theora identification packet")
    t = embedded[th : th + 42]
    if len(t) != 42:
        raise ValueError("Truncated Theora identification packet")
    be = lambda i, n: int.from_bytes(t[i : i + n], "big")
    m = struct.unpack_from("<8I", b, 0x2C)
    return dict(
        path=str(path),
        size=path.stat().st_size,
        version=struct.unpack_from("<I", b, 4)[0],
        offset=off,
        ogg_offset=ogg,
        mode=struct.unpack_from("<I", b, 0x28)[0],
        prefix_hex=b[:76].hex(),
        width=m[0],
        height=m[1],
        reserved34=m[2],
        flags38=m[3],
        frame_time_us=m[4],
        serial=m[5],
        pages=pages,
        frames=frames,
        theora_width=be(14, 3),
        theora_height=be(17, 3),
        theora_version=list(t[7:10]),
        coded_width=be(10, 2) * 16,
        coded_height=be(12, 2) * 16,
        picture_x=be(20, 1),
        picture_y=be(21, 1),
        fps_num=be(22, 4),
        fps_den=be(26, 4),
        aspect_num=be(30, 3),
        aspect_den=be(33, 3),
        nominal_bitrate=be(37, 3),
        pixel_format=(be(40, 2) >> 3) & 3,
        colorspace=be(36, 1),
    )
