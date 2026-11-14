"""Packet builder for the Lenovo Legion Tower lighting controller.

The controller is an ITE IT8297 behind USB ID 17ef:c955 (HID usage page
0xFF89). Every command is a 64-byte HID feature report with report ID 0xCC,
sent as SET_REPORT (wValue 0x03CC).

The layout below comes from USB captures of Lenovo Vantage on a Legion T5
26ARA8 (see docs/PROTOCOL.md). Vantage always sends the full state: one
packet per zone, then two commit packets. This module only builds bytes; it
never touches hardware, so it is safe to import and test anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

VENDOR_ID = 0x17EF
PRODUCT_ID = 0xC955
USAGE_PAGE = 0xFF89

REPORT_ID = 0xCC
PACKET_LENGTH = 64  # including the report ID byte

SPEED_RANGE = (1, 4)
BRIGHTNESS_RANGE = (1, 4)

CMD_COMMIT = 0x2D   # cc 2d ff ff 00: sent after the zone packets
CMD_SAVE = 0x5E     # cc 5e: sent last


@dataclass(frozen=True)
class Zone:
    code: int
    key: str
    title: str
    verified: bool  # code confirmed by a capture of that zone being changed


# Order is the one Vantage uses when it sends the state.
ZONES = [
    Zone(0x18, "ambient", "Ambient", True),
    Zone(0x13, "cpu-fan", "CPU fan", True),
    Zone(0x11, "rear-fan", "Rear fan", True),
    Zone(0x10, "front-fan-upper", "Front fan, upper", True),
    Zone(0x14, "front-fan-lower", "Front fan, lower", True),
    Zone(0x12, "top-fan-front", "Top fan, front", True),
    Zone(0x15, "top-fan-rear", "Top fan, rear", True),
    Zone(0x17, "logo", "Logo", True),
]
# The GPU lighting Vantage shows is not on this controller (likely WMI
# LENOVO_GAMEZONE_GPU_LED_DATA or the graphics card itself).
ZONES_BY_KEY = {z.key: z for z in ZONES}


@dataclass(frozen=True)
class Effect:
    key: str
    title: str
    code: int
    uses_color: bool
    uses_speed: bool
    verified: bool


EFFECTS = [
    Effect("off", "Off", 0x00, False, False, True),
    Effect("static", "Static", 0x01, True, False, True),
    Effect("flicker", "Flicker", 0x02, True, True, True),
    Effect("breathing", "Breathing", 0x03, True, True, True),
    Effect("rainbow-wave", "Rainbow wave", 0x09, False, True, True),  # Vantage default on the fans
]
EFFECTS_BY_KEY = {e.key: e for e in EFFECTS}


@dataclass
class ZoneState:
    effect: Effect
    speed: int
    brightness: int
    rgb: tuple[int, int, int]


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    lo, hi = bounds
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {value}")


def _packet(*body: int) -> bytes:
    p = bytearray(PACKET_LENGTH)
    p[0] = REPORT_ID
    p[1:1 + len(body)] = bytes(body)
    return bytes(p)


def build_zone(zone: Zone, state: ZoneState) -> bytes:
    """cc ZZ EE SS BB RR GG BB, rest zero."""
    _check_range("speed", state.speed, SPEED_RANGE)
    _check_range("brightness", state.brightness, BRIGHTNESS_RANGE)
    for c in state.rgb:
        _check_range("color channel", c, (0, 255))
    return _packet(zone.code, state.effect.code, state.speed, state.brightness, *state.rgb)


def build_commit() -> list[bytes]:
    return [_packet(CMD_COMMIT, 0xFF, 0xFF, 0x00), _packet(CMD_SAVE)]


def build_apply(states: dict[str, ZoneState]) -> list[bytes]:
    """Full update like Vantage: every zone in ZONES order, then commit.

    `states` must hold every zone key: the controller gets the whole state.
    """
    missing = [z.key for z in ZONES if z.key not in states]
    if missing:
        raise ValueError(f"missing zone states: {', '.join(missing)}")
    return [build_zone(z, states[z.key]) for z in ZONES] + build_commit()


def vantage_default() -> dict[str, ZoneState]:
    """The state seen at the start of the capture (ambient static, fans rainbow)."""
    color = (0x00, 0xD3, 0xFE)
    states = {z.key: ZoneState(EFFECTS_BY_KEY["rainbow-wave"], 2, 3, color) for z in ZONES}
    states["ambient"] = ZoneState(EFFECTS_BY_KEY["static"], 2, 4, color)
    return states


def hexdump(packet: bytes) -> str:
    """Compact hex, trailing zeros elided, for previews and logs."""
    end = len(packet.rstrip(b"\x00")) or 1
    body = " ".join(f"{b:02x}" for b in packet[:end])
    return body + (f"  (+{len(packet) - end} zero bytes)" if end < len(packet) else "")
