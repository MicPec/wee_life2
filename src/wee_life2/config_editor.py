"""Terminal-based config editor using Textual."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from textual_slider import Slider

from .core import config
from .core import config_json


# Number of discrete steps per unit of float range.
_FLOAT_SLIDER_STEPS = 1000


class _ColorField(Horizontal):
    """A row with three RGB sliders + inputs and a live color preview."""

    def __init__(self, key: str, value: tuple[int, int, int], comment: str | None) -> None:
        self.key = key
        self.value = value
        self.comment = comment
        self._sliders: list[Slider] = []
        self._inputs: list[Input] = []
        self._preview: Static | None = None
        self._updating = False
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"{self.key}  ({type(self.value).__name__})", classes="field-name color-field-name")
        for idx, channel in enumerate("RGB"):
            with Vertical(classes="color-channel"):
                slider = Slider(
                    0, 255, step=1, value=self.value[idx], id=f"color-{self.key}-{idx}", classes="color-slider"
                )
                self._sliders.append(slider)
                input_ = Input(
                    str(self.value[idx]), id=f"color-input-{self.key}-{idx}", classes="color-input", compact=True
                )
                self._inputs.append(input_)
                with Horizontal(classes="color-controls"):
                    yield slider
                    yield input_
                yield Label(channel, classes="channel-label")
        self._preview = Static("   \n   \n   ", id=f"color-preview-{self.key}", classes="color-preview")
        self._preview.styles.background = Color(*self.value)
        yield self._preview

    def _update_preview(self) -> None:
        try:
            rgb = [int(input_.value) for input_ in self._inputs]
            if self._preview:
                self._preview.styles.background = Color(*rgb)
        except (ValueError, IndexError):
            pass

    def on_slider_changed(self, event: Slider.Changed) -> None:
        if not self.is_mounted or self._updating:
            return
        if not event.slider or event.slider not in self._sliders:
            return
        idx = self._sliders.index(event.slider)
        if self._inputs[idx].value != str(event.value):
            self._updating = True
            self._inputs[idx].value = str(event.value)
            self._updating = False
            self._update_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self.is_mounted or self._updating:
            return
        if not event.input or event.input not in self._inputs:
            return
        idx = self._inputs.index(event.input)
        try:
            value = max(0, min(255, int(event.value)))
        except ValueError:
            return
        if self._sliders[idx].value != value:
            self._updating = True
            self._sliders[idx].value = value
            self._updating = False
        self._update_preview()

    def get_value(self) -> tuple[int, int, int]:
        rgb = []
        for input_ in self._inputs:
            rgb.append(max(0, min(255, int(input_.value))))
        return tuple(rgb)


class _NumericField(Horizontal):
    """A row with a slider and an input for an int or float value."""

    def __init__(self, key: str, value: int | float, is_float: bool, comment: str | None) -> None:
        self.key = key
        self.is_float = is_float
        self.min_value, self.max_value = _numeric_range(value, key)
        if is_float:
            self.slider_max = max(1, int(self.max_value * _FLOAT_SLIDER_STEPS))
            self.slider_value = _float_to_slider(value, self.min_value, self.max_value, self.slider_max)
        else:
            self.slider_max = max(int(self.max_value), int(self.min_value) + 1)
            self.slider_value = max(int(self.min_value), min(int(value), self.slider_max))
        display = str(value)
        self.initial_display = display
        self.comment = comment
        self._input: Input | None = None
        self._slider: Slider | None = None
        self._updating = False
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"{self.key}  ({'float' if self.is_float else 'int'})", classes="field-name")
        self._slider = Slider(
            0,
            self.slider_max,
            step=1,
            value=self.slider_value,
            id=f"slider-{self.key}",
            classes="numeric-slider",
        )
        yield self._slider
        self._input = Input(self.initial_display, id=f"input-{self.key}", classes="numeric-input", compact=True)
        yield self._input

    def on_slider_changed(self, event: Slider.Changed) -> None:
        if not self.is_mounted or self._updating:
            return
        if not event.slider or event.slider is not self._slider:
            return
        if self.is_float:
            value = _slider_to_float(event.value, self.min_value, self.max_value, self.slider_max)
            text = f"{value:.4f}"
        else:
            value = int(round(event.value))
            value = max(self.min_value, min(value, self.max_value))
            text = str(value)
        if self._input and self._input.value != text:
            self._updating = True
            self._input.value = text
            self._updating = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self.is_mounted or self._updating:
            return
        if not event.input or event.input is not self._input:
            return
        try:
            raw = float(event.value) if self.is_float else int(float(event.value))
        except ValueError:
            return
        value = max(self.min_value, min(raw, self.max_value))
        if self.is_float:
            slider_value = _float_to_slider(value, self.min_value, self.max_value, self.slider_max)
        else:
            slider_value = int(round(value))
        if self._slider and self._slider.value != slider_value:
            self._updating = True
            self._slider.value = slider_value
            self._updating = False

    def get_value(self) -> int | float:
        if not self._input:
            raise RuntimeError("Input not composed")
        text = self._input.value
        if self.is_float:
            return float(text)
        return int(float(text))


class _BoolField(Horizontal):
    """A row with a checkbox for a boolean constant."""

    def __init__(self, key: str, value: bool, comment: str | None) -> None:
        self.key = key
        self.value = value
        self.comment = comment
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Checkbox(self.key, value=self.value, id=f"bool-{self.key}", compact=True)

    def get_value(self) -> bool:
        return self.query_one(f"#bool-{self.key}", Checkbox).value


class _StringField(Horizontal):
    """A row with a text input for a string constant."""

    def __init__(self, key: str, value: str, comment: str | None) -> None:
        self.key = key
        self.value = value
        self.comment = comment
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"{self.key}  (str)", classes="field-name")
        yield Input(self.value, id=f"string-{self.key}", compact=True)

    def get_value(self) -> str:
        return self.query_one(f"#string-{self.key}", Input).value


class _TupleField(Horizontal):
    """A row with an input for non-color tuples (rare)."""

    def __init__(self, key: str, value: tuple[Any, ...], comment: str | None) -> None:
        self.key = key
        self.value = value
        self.comment = comment
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"{self.key}  (tuple)", classes="field-name")
        yield Input(repr(self.value), id=f"tuple-{self.key}", compact=True)

    def get_value(self) -> tuple[Any, ...]:
        text = self.query_one(f"#tuple-{self.key}", Input).value
        result = ast.literal_eval(text)
        if not isinstance(result, (list, tuple)):
            raise ValueError(f"{self.key}: expected tuple/list")
        return tuple(result)


class _DictField(Vertical):
    """A text area for a dictionary constant."""

    def __init__(self, key: str, value: dict[str, Any], comment: str | None) -> None:
        self.key = key
        self.value = value
        self.comment = comment
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dict-label"):
            yield Label(f"{self.key}  (dict)", classes="field-name")
        yield TextArea(
            json.dumps(self.value, indent=2, ensure_ascii=False),
            id=f"dict-{self.key}",
            language="json",
        )

    def get_value(self) -> dict[str, Any]:
        text = self.query_one(f"#dict-{self.key}", TextArea).text
        return json.loads(text)


class ConfigEditorApp(App[None]):
    """Textual TUI for editing wee-life2 JSON config presets."""

    CSS = """
    Screen { align: center middle; }

    .toolbar {
        height: 3;
        margin: 0 1;
    }

    .toolbar Static {
        content-align: center middle;
        width: auto;
    }

    .toolbar Input {
        width: 40;
    }

    .toolbar Button {
        margin: 0 1;
    }

    .status {
        height: 1;
        color: $text-muted;
    }

    TabbedContent {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }

    TabPane {
        padding: 0 1;
        height: 1fr;
    }

    VerticalScroll {
        height: 1fr;
    }

    .field-row {
        height: auto;
        align: center middle;
        margin: 0 1 1 1;
        padding: 0 1;
    }

    .field-row > .field-name {
        width: 30;
        text-align: left;
    }

    .field-row > .color-field-name {
        width: 26;
    }

    Slider {
        height: 1;
        min-height: 1;
        border: none;
        padding: 0 1;
        background: $surface;
        color: $text;
    }

    Slider > .slider--slider {
        color: $primary;
        background: $background;
    }

    .numeric-slider {
        width: 1fr;
    }

    .numeric-input {
        width: 12;
    }

    .color-slider {
        width: 6;
    }

    .color-channel {
        width: auto;
        height: 3;
    }

    .color-controls {
        width: auto;
    }

    .color-input {
        width: 4;
    }

    .channel-label {
        width: 4;
        text-align: center;
        color: $text-muted;
    }

    .color-preview {
        width: 4;
        height: 3;
        border: solid $border;
        margin: 0 1;
    }

    .dict-field {
        height: 1fr;
    }

    .dict-label {
        height: auto;
    }

    TextArea {
        height: 1fr;
        width: 1fr;
    }

    Checkbox {
        width: 1fr;
    }

    .error {
        color: $error;
    }

    .success {
        color: $success;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+r", "revert", "Revert"),
    ]

    def __init__(self, initial_path: str | Path | None = None) -> None:
        self._current_path = Path(initial_path) if initial_path else None
        self._comments = config_json.config_comments()
        self._sections = _load_sections()
        self._status: str = "Ready"
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(classes="toolbar"):
            yield Static("File:")
            yield Input(
                str(self._current_path) if self._current_path else "",
                id="path-input",
                classes="path-input",
            )
            yield Button("Open", id="open", variant="primary")
            yield Button("Save", id="save")
            yield Button("Revert", id="revert")
            yield Button("Quit", id="quit")
        yield Static(self._status, id="status", classes="status")
        with TabbedContent():
            for section_name, keys in self._sections.items():
                with TabPane(section_name, id=f"tab-{_slug(section_name)}"):
                    with VerticalScroll():
                        for key in keys:
                            if key.startswith("_") or not hasattr(config, key):
                                continue
                            widget = self._build_field(key)
                            if widget:
                                yield widget
        yield Footer()

    def _build_field(self, key: str) -> Any | None:
        value = getattr(config, key)
        comment = self._comments.get(key)
        widget: Any
        if isinstance(value, bool):
            widget = _BoolField(key, value, comment)
        elif isinstance(value, tuple) and _is_color_key(key):
            widget = _ColorField(key, value, comment)
        elif isinstance(value, tuple):
            widget = _TupleField(key, value, comment)
        elif isinstance(value, dict):
            widget = _DictField(key, value, comment)
            widget.add_class("dict-field")
        elif isinstance(value, int):
            widget = _NumericField(key, value, is_float=False, comment=comment)
        elif isinstance(value, float):
            widget = _NumericField(key, value, is_float=True, comment=comment)
        elif isinstance(value, str):
            widget = _StringField(key, value, comment)
        else:
            return None
        widget.add_class("field-row")
        widget.id = f"field-{key}"
        if comment:
            widget.tooltip = comment
        return widget

    async def on_mount(self) -> None:
        await self._load_file()

    async def _load_file(self) -> None:
        if self._current_path and self._current_path.exists():
            try:
                data = json.loads(self._current_path.read_text(encoding="utf-8"))
                config_json.config_from_dict(data)
                self._set_status(f"Loaded: {self._current_path}")
            except (ValueError, OSError) as exc:
                self._set_status(f"Error loading {self._current_path}: {exc}", error=True)
                self._current_path = None
        await self._recompose_content()

    async def _recompose_content(self) -> None:
        await self.recompose()

    def _set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.remove_class("error", "success")
        status.add_class("error" if error else "success")

    def _collect_values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in config_json.config_to_dict().keys():
            if key.startswith("_") or not hasattr(config, key):
                continue
            current = getattr(config, key)
            widget = self._find_field_widget(key, current)
            if widget is None:
                continue
            raw = widget.get_value()
            try:
                coerced = config_json.coerce_value(raw, current)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid value for '{key}': {exc}") from exc
            result[key] = coerced
        return result

    def _find_field_widget(self, key: str, current: Any) -> Any | None:
        if isinstance(current, bool):
            return self.query_one(f"#bool-{key}", Checkbox).parent
        if isinstance(current, tuple) and _is_color_key(key):
            return self.query_one(f"#color-preview-{key}", Static).parent
        if isinstance(current, tuple):
            return self.query_one(f"#tuple-{key}", Input).parent
        if isinstance(current, dict):
            return self.query_one(f"#dict-{key}", TextArea).parent
        if isinstance(current, (int, float)):
            return self.query_one(f"#input-{key}", Input).parent
        if isinstance(current, str):
            return self.query_one(f"#string-{key}", Input).parent
        return None

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "save":
            self.action_save()
        elif button_id == "open":
            await self.action_open()
        elif button_id == "revert":
            await self.action_revert()
        elif button_id == "quit":
            self.action_quit()

    def action_save(self) -> None:
        path_text = self.query_one("#path-input", Input).value.strip()
        if not path_text:
            self._set_status("No file path specified", error=True)
            return
        path = Path(path_text)
        try:
            data = self._collect_values()
            config_json.config_from_dict(data)
            config_json.save_config_file(path)
            self._current_path = path
            self._set_status(f"Saved: {path}")
        except ValueError as exc:
            self._set_status(str(exc), error=True)

    async def action_open(self) -> None:
        path_text = self.query_one("#path-input", Input).value.strip()
        if not path_text:
            self._set_status("No file path specified", error=True)
            return
        path = Path(path_text)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            config_json.config_from_dict(data)
            self._current_path = path
            self._set_status(f"Loaded: {path}")
            await self._recompose_content()
        except (ValueError, OSError) as exc:
            self._set_status(f"Error loading {path}: {exc}", error=True)

    async def action_revert(self) -> None:
        importlib.reload(config)
        self._current_path = None
        self.query_one("#path-input", Input).value = ""
        self._set_status("Reverted to config.py defaults")
        await self._recompose_content()

    def action_quit(self) -> None:
        self.exit()


def _is_color_key(key: str) -> bool:
    return key.startswith("COLOR_")


def _load_sections() -> dict[str, list[str]]:
    """Parse config.py source to group keys by section comments."""
    source = inspect.getsource(config)
    sections: dict[str, list[str]] = {}
    current = "Other"

    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if "=" not in text and re.match(r"^[A-Z]", text):
                current = text
                sections.setdefault(current, [])
        elif m := re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line):
            key = m.group(1)
            sections.setdefault(current, []).append(key)

    # Ensure every public constant is present
    public = set(config_json.config_to_dict().keys())
    found = {k for keys in sections.values() for k in keys}
    missing = public - found
    if missing:
        sections.setdefault("Other", []).extend(sorted(missing))
    return sections


def _numeric_range(value: int | float, key: str) -> tuple[int | float, int | float]:
    """Return a sensible (min, max) range for the given numeric constant."""
    low = 0
    high: int | float
    if _is_fraction_like(key, value):
        high = 1
    else:
        high = max(value * 3, value + 10, 1)
    return low, high


def _is_fraction_like(key: str, value: int | float) -> bool:
    """Heuristic: is this a probability/fraction/discount type constant?"""
    if value > 1.0:
        return False
    fraction_markers = (
        "_FRACTION",
        "_CHANCE",
        "_DISCOUNT",
        "_SLOWDOWN",
        "_RATE",
        "_STRENGTH",
        "POPULATION_CAP",
        "SPECIES_CAP_FRACTION",
        "FRICTION",
    )
    return any(marker in key for marker in fraction_markers)


def _float_to_slider(value: float, min_value: float, max_value: float, slider_max: int) -> int:
    if max_value == min_value:
        return 0
    return int((value - min_value) / (max_value - min_value) * slider_max)


def _slider_to_float(slider_value: int, min_value: float, max_value: float, slider_max: int) -> float:
    raw = min_value + (slider_value / slider_max) * (max_value - min_value)
    return round(raw, 4)


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
