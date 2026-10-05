"""Load and save simulation configuration from/to JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


__all__ = [
    "config_to_dict",
    "config_from_dict",
    "load_config_file",
    "save_config_file",
    "coerce_value",
    "config_comments",
]


_JSON_SERIALIZABLE_TYPES = (int, float, bool, str, list, tuple, dict)

_TRUE_TOKENS = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})


def _is_public_config_attr(name: str, value: object) -> bool:
    return not name.startswith("_") and not callable(value) and isinstance(value, _JSON_SERIALIZABLE_TYPES)


def config_to_dict() -> dict[str, Any]:
    """Return a flat dict of all public, JSON-serializable config constants."""
    return {name: value for name, value in vars(config).items() if _is_public_config_attr(name, value)}


def coerce_value(value: Any, current: Any) -> Any:
    """Convert *value* to a type compatible with *current*.

    Supports CLI strings, JSON-native values, and values coming back from
    the editor.  Tuples and lists are preserved as their original kind.
    """
    if not isinstance(current, bool) and isinstance(value, bool):
        raise TypeError(f"expected {type(current).__name__}, got bool")

    if isinstance(current, bool):
        if isinstance(value, str):
            token = value.strip().lower()
            if token in _TRUE_TOKENS:
                return True
            if token in _FALSE_TOKENS:
                return False
            # Never silently coerce garbage to False: `--set FLAG=banana`
            # used to quietly disable the flag instead of reporting an error.
            raise TypeError(f"expected one of {sorted(_TRUE_TOKENS | _FALSE_TOKENS)}, got {value!r}")
        if isinstance(value, bool):
            return value
        raise TypeError(f"expected bool, got {type(value).__name__}")

    if isinstance(current, int):
        if isinstance(value, str):
            return int(value)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise TypeError(f"expected int, got {type(value).__name__}")

    if isinstance(current, float):
        if isinstance(value, str):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"expected float, got {type(value).__name__}") from exc

    if isinstance(current, str):
        return str(value)

    if isinstance(current, tuple):
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"expected tuple/list, got {type(value).__name__}")
        if not current:
            return tuple(value)
        inner_sample = current[0]
        return tuple(coerce_value(item, inner_sample) for item in value)

    if isinstance(current, list):
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"expected list/tuple, got {type(value).__name__}")
        if not current:
            return list(value)
        inner_sample = current[0]
        return list(coerce_value(item, inner_sample) for item in value)

    if isinstance(current, dict):
        if not isinstance(value, dict):
            raise TypeError(f"expected dict, got {type(value).__name__}")
        if not current:
            return dict(value)
        sample_key = next(iter(current))
        sample_value = current[sample_key]
        return {coerce_value(k, sample_key): coerce_value(v, sample_value) for k, v in value.items()}

    raise TypeError(f"unsupported config type: {type(current).__name__}")


def config_from_dict(data: dict[str, Any], *, strict: bool = True) -> None:
    """Apply a flat dict of config values to the live config module.

    Raises ValueError/TypeError for unknown keys or incompatible types.
    """
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if not hasattr(config, key):
            if strict:
                raise ValueError(f"Unknown config option '{key}'")
            continue
        current = getattr(config, key)
        try:
            coerced = coerce_value(value, current)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value for '{key}': {exc}") from exc
        setattr(config, key, coerced)


def load_config_file(path: Path | str) -> None:
    """Load a JSON config file and apply it to the live config module."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a JSON object")
    config_from_dict(data)


def save_config_file(path: Path | str, *, indent: int = 2) -> None:
    """Save the current config state to a JSON file."""
    path = Path(path)
    data = config_to_dict()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def config_comments() -> dict[str, str]:
    """Extract inline comments for public config constants from config.py.

    Returns a mapping of constant name to comment text.  Falls back to an
    empty dict if the source cannot be read.
    """
    import inspect
    import re

    try:
        source = inspect.getsource(config)
    except (OSError, TypeError):
        return {}

    comments: dict[str, str] = {}
    for line in source.splitlines():
        match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=\s*[^#]+#\s*(.+)$", line)
        if match:
            comments[match.group(1)] = match.group(2).strip()
    return comments
