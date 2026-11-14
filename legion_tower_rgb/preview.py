"""Animated side view of the case, drawn with Cairo.

An approximation of what each effect looks like, driven by the settings in
the window (not read from the hardware). Layout is schematic: front on the
left, two front fans, rear fan, two top fans, CPU cooler, ambient strip along
the top inside edge, "L" logo at the top of the front panel.
"""

from __future__ import annotations

import colorsys
import math
import random

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from . import protocol  # noqa: E402

LEDS_PER_FAN = 12
# Seconds per cycle for speed 1..4 (assumes 4 is the fastest).
PERIODS = {1: 6.0, 2: 4.0, 3: 2.5, 4: 1.5}
CASE_W, CASE_H = 300.0, 340.0

# Fan centers and radius in case coordinates.
FANS = {
    "front-fan-upper": (38, 120, 30),
    "front-fan-lower": (38, 210, 30),
    "rear-fan": (262, 95, 26),
    "top-fan-front": (115, 30, 22),
    "top-fan-rear": (185, 30, 22),
    "cpu-fan": (175, 120, 24),
}


def _hue(h: float) -> tuple[float, float, float]:
    return colorsys.hsv_to_rgb(h % 1.0, 1.0, 1.0)


class CasePreview(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(content_width=320, content_height=360, hexpand=True)
        self.states = protocol.vantage_default()
        self._t = 0.0
        self._rng = random.Random(1)
        self._random_colors: dict[tuple[str, int], tuple[float, float, float]] = {}
        self._random_tick = -1
        self.set_draw_func(self._draw)
        self.add_tick_callback(self._on_tick)

    def set_states(self, states: dict[str, protocol.ZoneState]) -> None:
        self.states = dict(states)
        self.queue_draw()

    def _on_tick(self, _widget, clock) -> bool:
        self._t = clock.get_frame_time() / 1e6
        self.queue_draw()
        return True

    # --- effect model -----------------------------------------------------

    def _led(self, key: str, index: int, count: int, x_pos: float) -> tuple[float, float, float]:
        """Color of one LED (0..1 floats, already scaled by brightness)."""
        s = self.states[key]
        e = s.effect.key
        base = (1.0, 1.0, 1.0) if key == "ambient" else tuple(c / 255 for c in s.rgb)
        period = PERIODS.get(s.speed, 3.0)
        phase = (self._t / period) % 1.0
        level = 0.25 + 0.75 * (s.brightness - 1) / 3
        if e == "off":
            return (0.0, 0.0, 0.0)
        if e == "static":
            color, k = base, 1.0
        elif e == "breathing":
            color, k = base, 0.5 - 0.5 * math.cos(2 * math.pi * phase)
        elif e == "flicker":
            slot = int(self._t / (period / 8))
            color, k = base, 1.0 if (hash((key, index // 3, slot)) & 3) else 0.1
        elif e == "wave":
            color, k = _hue(x_pos - phase), 1.0
        elif e == "spectrum":
            color, k = _hue(phase), 1.0
        elif e == "rainbow":
            color, k = _hue(index / count - phase), 1.0
        elif e == "random":
            color, k = self._random_color(key, index, period), 1.0
        elif e.startswith("meteor"):
            head = phase * count
            dist = (head - index) % count
            k = max(0.0, 1.0 - dist / (count * 0.45))
            if "rainbow" in e:
                color = _hue(index / count)
            elif "cycle" in e:
                color = _hue(self._t / (period * 4))
            else:
                color = base
        else:
            color, k = base, 1.0
        return tuple(c * k * level for c in color)  # type: ignore[return-value]

    def _random_color(self, key: str, index: int, period: float) -> tuple[float, float, float]:
        tick = int(self._t / (period / 2))
        if tick != self._random_tick:
            self._random_tick = tick
            self._random_colors.clear()
        if (key, index) not in self._random_colors:
            self._random_colors[(key, index)] = _hue(self._rng.random())
        return self._random_colors[(key, index)]

    # --- drawing ------------------------------------------------------------

    def _draw(self, _area, cr, width: int, height: int) -> None:
        scale = min(width / (CASE_W + 20), height / (CASE_H + 20))
        cr.translate((width - CASE_W * scale) / 2, (height - CASE_H * scale) / 2)
        cr.scale(scale, scale)

        # Case body and glass panel.
        cr.set_source_rgb(0.09, 0.09, 0.11)
        self._rounded(cr, 0, 0, CASE_W, CASE_H, 12)
        cr.fill()
        cr.set_source_rgb(0.13, 0.13, 0.16)
        self._rounded(cr, 76, 56, 172, 230, 6)
        cr.fill()
        # PSU shroud.
        cr.set_source_rgb(0.06, 0.06, 0.07)
        cr.rectangle(76, 286, 224, 54)
        cr.fill()

        self._draw_ambient(cr)
        for key, (x, y, r) in FANS.items():
            self._draw_fan(cr, key, x, y, r)
        self._draw_logo(cr)

    def _draw_ambient(self, cr) -> None:
        segments = 16
        for i in range(segments):
            x = 80 + i * (164 / segments)
            color = self._led("ambient", i, segments, x / CASE_W)
            self._glow(cr, x + 5, 62, 6, color)
            cr.set_source_rgb(*self._visible(color))
            cr.rectangle(x, 60, 164 / segments - 1, 4)
            cr.fill()

    def _draw_fan(self, cr, key: str, x: float, y: float, r: float) -> None:
        cr.set_source_rgb(0.04, 0.04, 0.05)
        cr.arc(x, y, r + 3, 0, 2 * math.pi)
        cr.fill()
        # Blades.
        cr.set_source_rgb(0.18, 0.18, 0.21)
        for b in range(7):
            a = b * 2 * math.pi / 7 + self._t * 3
            cr.move_to(x, y)
            cr.arc(x, y, r * 0.72, a, a + 0.5)
            cr.close_path()
            cr.fill()
        for i in range(LEDS_PER_FAN):
            a = i * 2 * math.pi / LEDS_PER_FAN - math.pi / 2
            lx, ly = x + math.cos(a) * r * 0.88, y + math.sin(a) * r * 0.88
            color = self._led(key, i, LEDS_PER_FAN, lx / CASE_W)
            self._glow(cr, lx, ly, r * 0.32, color)
            cr.set_source_rgb(*self._visible(color))
            cr.arc(lx, ly, max(2.0, r * 0.1), 0, 2 * math.pi)
            cr.fill()

    def _draw_logo(self, cr) -> None:
        color = self._led("logo", 0, 1, 0.1)
        self._glow(cr, 38, 50, 20, color)
        cr.set_source_rgb(*self._visible(color))
        cr.set_line_width(4)
        cr.set_line_cap(1)   # round
        cr.set_line_join(1)  # round
        # "L" mark at the top of the front panel.
        cr.move_to(31, 37)
        cr.line_to(31, 63)
        cr.line_to(47, 63)
        cr.stroke()

    @staticmethod
    def _visible(color: tuple[float, float, float]) -> tuple[float, float, float]:
        # Keep dark LEDs faintly visible so the layout reads when off.
        return tuple(max(c, 0.12) for c in color)  # type: ignore[return-value]

    @staticmethod
    def _glow(cr, x: float, y: float, radius: float, color: tuple[float, float, float]) -> None:
        if max(color) < 0.05:
            return
        import cairo
        g = cairo.RadialGradient(x, y, 0, x, y, radius)
        g.add_color_stop_rgba(0, *color, 0.55)
        g.add_color_stop_rgba(1, *color, 0.0)
        cr.set_source(g)
        cr.arc(x, y, radius, 0, 2 * math.pi)
        cr.fill()

    @staticmethod
    def _rounded(cr, x: float, y: float, w: float, h: float, r: float) -> None:
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
