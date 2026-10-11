"""Binary-safe video pipe with original embedded audio; requires source installation.

Usage: python examples/pipe_to_ffmpeg.py INPUT.omv OUTPUT.mp4
Alpha is discarded in this customization example. Use convert for black composite.
"""

import subprocess
import sys
from pathlib import Path

from omvtool.converter import layout
from omvtool.runtime import executable, external_env


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    source, output = map(Path, sys.argv[1:])
    m = layout(source)
    producer = subprocess.Popen(
        [sys.executable, "-m", "omvtool", "pipe", str(source)], stdout=subprocess.PIPE
    )
    consumer = None
    try:
        cmd = [
            executable("ffmpeg"),
            "-hide_banner",
            "-nostdin",
            "-n",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgba",
            "-video_size",
            f"{m['output_width']}x{m['output_height']}",
            "-framerate",
            f"{m['fps_num']}/{m['fps_den']}",
            "-i",
            "pipe:0",
            "-i",
            f"subfile,,start,{m['ogg_offset']},,:{m['path']}",
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-t",
            str(m["frames"] * m["fps_den"] / m["fps_num"]),
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-vf",
            "scale=in_range=full:out_range=limited:out_color_matrix=bt709,pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-preset",
            "slow",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            str(output),
        ]
        consumer = subprocess.Popen(cmd, stdin=producer.stdout, env=external_env())
        producer.stdout.close()
        status = consumer.wait()
        if status:
            raise RuntimeError(f"FFmpeg failed: {status}")
        if producer.wait():
            raise RuntimeError("OMV producer failed")
    finally:
        for child in (producer, consumer):
            if child is not None and child.poll() is None:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
