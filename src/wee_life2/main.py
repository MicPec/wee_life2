"""Entry point for wee-life2."""

from __future__ import annotations

import argparse
import os


def _prefer_native_wayland() -> None:
    """Avoid SDL falling back to XWayland's GLX probing.

    On some Wayland sessions (notably with certain NVIDIA/EGL driver setups),
    SDL's x11 video driver probes GLX through XWayland during init and that
    probe can crash the whole process with an unrecoverable X error, before
    any Python exception can be caught. If we're clearly running under
    Wayland and the user hasn't already picked a driver, prefer SDL's native
    wayland backend instead.
    """
    if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("SDL_VIDEODRIVER"):
        os.environ["SDL_VIDEODRIVER"] = "wayland"


_prefer_native_wayland()

from .core.map_storage import MapStorage  # noqa: E402
from .render.map_editor import MapEditor  # noqa: E402
from .simulation import Simulation  # noqa: E402


def _coerce_config_value(raw: str, current: object) -> object:
    """Cast a raw CLI string to match the type of the existing config constant."""
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _apply_config_overrides(pairs: list[str]) -> None:
    """Apply --set KEY=VALUE overrides directly onto the config module."""
    from .core import config

    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --set value '{pair}', expected KEY=VALUE")
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if key.startswith("_") or not hasattr(config, key):
            raise SystemExit(f"Unknown config option '{key}' (see core/config.py for valid names)")
        current = getattr(config, key)
        setattr(config, key, _coerce_config_value(raw_value.strip(), current))


def _print_config_values(keys: list[str]) -> None:
    """Print current config.py values for --get KEY."""
    from .core import config

    for key in keys:
        key = key.strip()
        if key.startswith("_") or not hasattr(config, key):
            print(f"{key}: <unknown config option>")
            continue
        print(f"{key} = {getattr(config, key)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wee Life 2 - Artificial Life Simulation")
    parser.add_argument(
        "--width",
        type=int,
        default=1200,
        help="World width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=900,
        help="World height in pixels",
    )
    parser.add_argument(
        "--edit-map",
        action="store_true",
        help="Open the map editor instead of running the simulation",
    )
    parser.add_argument(
        "--map-file",
        type=str,
        default=None,
        help="Path to the map file to load/save",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override a config.py constant, e.g. --set MATING_RATE=0.3 (repeatable)",
    )
    parser.add_argument(
        "--get",
        action="append",
        default=[],
        metavar="KEY",
        help="Print the current value of a config.py constant and exit (repeatable)",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Disable writing per-run statistics to disk",
    )
    args = parser.parse_args()

    if args.no_stats:
        from .core import config as _config

        _config.STATS_ENABLED = False

    if args.set:
        _apply_config_overrides(args.set)

    if args.get:
        _print_config_values(args.get)
        return

    storage = MapStorage(args.map_file)

    if args.edit_map:
        editor = MapEditor(
            width=args.width,
            height=args.height,
            storage=storage,
        )
        editor.run()
    else:
        sim = Simulation(
            width=float(args.width),
            height=float(args.height),
            storage=storage,
        )
        sim.run()
