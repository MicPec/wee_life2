"""Glue a run's timelapse frames (RUN_DIR/frames/frame_*.png) into an mp4 with ffmpeg.

Usage: uv run python scripts/make_timelapse.py RUN_DIR [--fps 30] [--scale 50] [--out RUN_DIR/timelapse.mp4]

--scale is a percentage of the frame size (100 = full size).

Frames are only written when the run was started with `wee-life2 --timelapse [TICKS]`
(one frame every TICKS ticks, default 100) or `wee-life2 --headless TICKS`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wee_life2.timelapse import make_timelapse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--scale", type=float, default=100, help="output size in percent of the frame")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    print(make_timelapse(args.run_dir, args.fps, args.scale, args.out))


if __name__ == "__main__":
    main()
