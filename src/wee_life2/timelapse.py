"""Glue a run's timelapse frames (RUN_DIR/frames/frame_*.png) into an mp4 with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def make_timelapse(run_dir: Path, fps: int = 30, scale: float = 100, out: Path | None = None) -> Path:
    """Write the mp4 (default RUN_DIR/timelapse.mp4) and return its path; ``scale`` is in percent."""
    if scale <= 0:
        sys.exit("--scale must be > 0")
    frames = run_dir / "frames"
    if not any(frames.glob("frame_*.png")):
        sys.exit(f"no frames in {frames} (start the run with: uv run wee-life2 --timelapse)")
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH")
    out = out or run_dir / "timelapse.mp4"
    s = scale / 100
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-pattern_type", "glob", "-i", str(frames / "frame_*.png"),
            # libx264/yuv420p needs even dimensions, so round the scaled size down to even.
            "-vf", f"scale=trunc(iw*{s}/2)*2:trunc(ih*{s}/2)*2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out),
        ],
        check=True,
    )
    return out
