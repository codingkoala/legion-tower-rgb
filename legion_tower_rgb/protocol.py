"""Packet builder for the Lenovo Legion Tower lighting controller.

The controller is an ITE IT8297 behind USB ID 17ef:c955 (HID usage page
0xFF89). Lighting commands are 64-byte HID feature reports with report ID 0xCC.

Protocol facts come from OpenRGB's LenovoMotherboardController (GPL-2.0+),
which was written for a sibling Legion Tower model. They are NOT yet verified
on the Legion T5 26ARA8. This module only builds bytes; it never touches
hardware, so it is safe to import and test anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

VENDOR_ID = 0x17EF
PRODUCT_ID = 0xC955
USAGE_PAGE = 0xFF89

REPORT_ID = 0xCC
PACKET_LENGTH = 64  # including the report ID byte

SPEED_RANGE = (1, 4)
BRIGHTNESS_RANGE = (1, 4)


class Zone(IntEnum):
    CPU_FAN = 0x12
    REAR_FAN = 0x11


ZONE_TITLES = {
    Zone.CPU_FAN: "CPU fan",
    Zone.REAR_FAN: "Rear fan",
}


@dataclass(frozen=True)
class Effect:
    key: str
    title: str
    code: int
    uses_color: bool
    uses_speed: bool


EFFECTS = [
    Effect("static", "Static", 0x01, True, False),
    Effect("sparkle", "Sparkle", 0x02, True, True),
    Effect("breathing", "Breathing", 0x03, True, True),
    Effect("wave", "Wave", 0x04, False, True),
    Effect("specter", "Specter", 0x06, True, True),
    Effect("rainbow-wave", "Rainbow wave", 0x09, False, True),
    Effect("random", "Random", 0x0A, False, True),
]
EFFECTS_BY_KEY = {e.key: e for e in EFFECTS}


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    lo, hi = bounds
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {value}")


def build_set_mode(zone: Zone, effect: Effect, speed: int, brightness: int,
                   rgb: tuple[int, int, int]) -> list[bytes]:
    """The two feature reports that set one zone's effect, in sending order."""
    zone = Zone(zone)
    _check_range("speed", speed, SPEED_RANGE)
    _check_range("brightness", brightness, BRIGHTNESS_RANGE)
    for c in rgb:
        _check_range("color channel", c, (0, 255))
    settings = bytes([zone, effect.code, speed, brightness, *rgb])

    first = bytearray(PACKET_LENGTH)
    first[0] = REPORT_ID
    first[1:1 + len(settings)] = settings

    second = bytearray(PACKET_LENGTH)
    second[0] = REPORT_ID
    second[1] = 0x28
    second[2] = 0x06
    second[33:33 + len(settings)] = settings

    return [bytes(first), bytes(second)]


def hexdump(packet: bytes) -> str:
    """Compact hex, trailing zeros elided, for previews and logs."""
    end = len(packet.rstrip(b"\x00")) or 1
    body = " ".join(f"{b:02x}" for b in packet[:end])
    return body + (f"  (+{len(packet) - end} zero bytes)" if end < len(packet) else "")
