"""Entry point for wee-life2."""

from __future__ import annotations

import argparse
import json
import os
import sys


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


def _coerce_config_value(raw: str, current: object) -> object:
    """Cast a raw CLI string to match the type of the existing config constant."""
    from .core.config_json import coerce_value

    return coerce_value(raw, current)


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
        try:
            coerced = _coerce_config_value(raw_value.strip(), current)
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Invalid value for --set {key}={raw_value.strip()!r}: {exc}") from exc
        setattr(config, key, coerced)


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
        "--config-file",
        type=str,
        default=None,
        help="Load a JSON config file before running (overridable by --set)",
    )
    parser.add_argument(
        "--edit-config",
        action="store_true",
        help="Open the JSON config editor instead of running the simulation",
    )
    parser.add_argument(
        "--load-snapshot",
        type=str,
        default=None,
        metavar="PATH",
        help="Load a stats snapshot JSON and continue the simulation from it",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Disable writing per-run statistics to disk",
    )
    args = parser.parse_args()

    if args.config_file and not args.edit_config:
        from .core.config_json import load_config_file

        try:
            load_config_file(args.config_file)
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(f"Config file error: {exc}") from exc

    if args.set:
        _apply_config_overrides(args.set)

    # Applied last so an explicit --no-stats always wins over a config file or
    # a --set STATS_ENABLED=True that would otherwise re-enable logging.
    if args.no_stats:
        from .core import config as _config

        _config.STATS_ENABLED = False

    if args.get:
        _print_config_values(args.get)
        return

    if args.edit_config:
        if args.set or args.get:
            raise SystemExit("Cannot combine --edit-config with --set or --get")
        from .config_editor import ConfigEditorApp

        ConfigEditorApp(initial_path=args.config_file).run()
        return

    from .core.map_storage import MapStorage
    from .render.map_editor import MapEditor
    from .simulation import Simulation

    storage = MapStorage(args.map_file)

    if args.edit_map:
        if args.load_snapshot:
            raise SystemExit("Cannot combine --load-snapshot with --edit-map")
        editor = MapEditor(
            width=args.width,
            height=args.height,
            storage=storage,
        )
        editor.run()
    else:
        if args.load_snapshot:
            try:
                # The snapshot's geometry wins over --width/--height: a
                # mismatch is a hard error in world_from_dict, so build the
                # world to fit.
                with open(args.load_snapshot, encoding="utf-8") as f:
                    snapshot = json.load(f)
                snap_world = snapshot["world"]
                width = float(snap_world["width"])
                height = float(snap_world["height"])
                if (width, height) != (float(args.width), float(args.height)):
                    print(
                        f"note: using snapshot world size {width:.0f}x{height:.0f} "
                        f"(ignoring --width/--height {args.width}x{args.height})",
                        file=sys.stderr,
                    )
                sim = Simulation(width=width, height=height, storage=storage, snapshot=snapshot)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise SystemExit(f"Snapshot error in {args.load_snapshot}: {exc}") from exc
        else:
            sim = Simulation(
                width=float(args.width),
                height=float(args.height),
                storage=storage,
                # A fresh game always gets a fresh board; a saved map is only
                # loaded when --map-file names it explicitly.
                random_map=args.map_file is None,
            )
        sim.run()
