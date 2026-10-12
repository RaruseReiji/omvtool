"""Stage and FFmpeg progress on stderr, including heartbeats during slow work."""

import re
import subprocess
import sys
import threading
import time

from .runtime import external_env


class Progress:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.started = time.monotonic()
        self.stage = "checking input"
        self.stage_started = self.started
        self.done = 0
        self.total = None
        self.unit = "frames"
        self.readers = {}

    def __enter__(self):
        if self.enabled:
            self.render()
            self.worker = threading.Thread(target=self.heartbeat, daemon=True)
            self.worker.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        if self.enabled:
            self.worker.join()

    def phase(self, stage, total=None, unit="frames"):
        with self.lock:
            self.stage, self.total, self.unit = stage, total, unit
            self.done = 0
            self.stage_started = time.monotonic()
        self.render()

    def update(self, done):
        with self.lock:
            self.done = max(self.done, done)

    def heartbeat(self):
        while not self.stop.wait(1):
            self.render()

    def render(self):
        if not self.enabled:
            return
        with self.lock:
            now = time.monotonic()
            detail = ""
            if self.total is not None and self.total > 0:
                done = min(self.done, self.total)
                rate = done / max(now - self.stage_started, 0.001)
                eta = f"{(self.total - done) / rate:.1f}s" if rate else "--"
                detail = f" {done:g}/{self.total:g} {self.unit} ({100 * done / self.total:.1f}%) {rate:.1f} {self.unit}/s ETA={eta}"
            print(
                f"PROGRESS {self.stage}:{detail} elapsed={now - self.started:.1f}s",
                file=sys.stderr,
                flush=True,
            )

    def spawn(self, cmd, **kwargs):
        if not self.enabled:
            return subprocess.Popen(cmd, env=external_env(), **kwargs)
        cmd = [
            *cmd[:1],
            "-nostats",
            "-stats_period",
            "0.5",
            "-progress",
            "pipe:2",
            *cmd[1:],
        ]
        child = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, env=external_env(), **kwargs
        )
        reader = threading.Thread(target=self.read, args=(child,), daemon=True)
        self.readers[child] = reader
        reader.start()
        return child

    def read(self, child):
        for raw in iter(child.stderr.readline, b""):
            line = raw.decode(errors="replace").rstrip()
            key, _, value = line.partition("=")
            if key == "frame" and self.unit == "frames":
                try:
                    self.update(int(value))
                except ValueError:
                    pass
            elif key == "out_time_us" and self.unit == "seconds":
                try:
                    self.update(int(value) / 1_000_000)
                except ValueError:
                    pass
            elif not re.fullmatch(
                r"(?:frame|fps|stream_\d+_\d+_q|bitrate|total_size|out_time_us|out_time_ms|out_time|dup_frames|drop_frames|speed|progress)",
                key,
            ):
                print(line, file=sys.stderr, flush=True)
        child.stderr.close()

    def wait(self, child):
        code = child.wait()
        reader = self.readers.pop(child, None)
        if reader:
            reader.join()
        self.render()
        return code
