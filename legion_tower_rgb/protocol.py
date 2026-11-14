"""Packet builder for the Lenovo Legion Tower lighting controller.

The controller is an ITE IT8297 behind USB ID 17ef:c955 (HID usage page
0xFF89). Every command is a 64-byte HID feature report with report ID 0xCC,
sent as SET_REPORT (wValue 0x03CC).

The layout comes from USB captures of Lenovo Vantage on a Legion T5 26ARA8,
cross-checked with the firmware's WMI class LENOVO_LIGHTING_INFO_LIST (see
docs/PROTOCOL.md). Vantage always sends the full state: one packet per zone,
then two commit packets. This module only builds bytes; it never touches
hardware, so it is safe to import and test anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

VENDOR_ID = 0x17EF
PRODUCT_ID = 0xC955
USAGE_PAGE = 0xFF89

REPORT_ID = 0xCC
PACKET_LENGTH = 64  # including the report ID byte

SPEED_RANGE = (1, 4)
BRIGHTNESS_RANGE = (1, 4)

# Command bytes; WMI LENOVO_LIGHTING_INFO_LIST lists the same values as
# applycmd = 45 (0x2D), Savecmd = 94 (0x5E) and Readcmd = 96 (0x60).
CMD_APPLY = 0x2D        # cc 2d ff ff 00: after the zone packets
CMD_SAVE = 0x5E         # cc 5e: last
CMD_CYCLE_PARAM = 0x41  # cc 41 ff 00 00: before enabling the meteor cycle
CMD_CYCLE = 0x42        # cc 42 01 / cc 42 00: meteor color cycle on / off
CMD_READ = 0x60         # cc 60 18, then GET_REPORT 0xCC: state of every zone


@dataclass(frozen=True)
class Zone:
    code: int
    key: str
    title: str


# Order is the one Vantage uses when it sends the state.
ZONES = [
    Zone(0x18, "ambient", "Ambient"),
    Zone(0x13, "cpu-fan", "CPU fan"),
    Zone(0x11, "rear-fan", "Rear fan"),
    Zone(0x10, "front-fan-upper", "Front fan, upper"),
    Zone(0x14, "front-fan-lower", "Front fan, lower"),
    Zone(0x12, "top-fan-front", "Top fan, front"),
    Zone(0x15, "top-fan-rear", "Top fan, rear"),
    Zone(0x17, "logo", "Logo"),
]
ZONES_BY_KEY = {z.key: z for z in ZONES}


@dataclass(frozen=True)
class Panel:
    """A light as Vantage shows it; WMI panelid groups zones the same way."""
    key: str
    title: str
    zones: tuple[str, ...]
    full_effects: bool  # fans and logo; ambient only has off/static/flicker/breathing
    has_color: bool = True  # the ambient strip is white only (WMI IsSupportRGB = 1)


PANELS = [
    Panel("ambient", "Ambient", ("ambient",), False, has_color=False),
    Panel("cpu-fan", "CPU fan", ("cpu-fan",), True),
    Panel("rear-fan", "Rear fan", ("rear-fan",), True),
    Panel("front-fans", "Front fans", ("front-fan-upper", "front-fan-lower"), True),
    Panel("top-fans", "Top fans", ("top-fan-front", "top-fan-rear"), True),
    Panel("logo", "Logo", ("logo",), True),
]
PANELS_BY_KEY = {p.key: p for p in PANELS}
# The GPU lights Vantage shows (WMI panels 15 and 16, type 3) are not on this
# controller: they go through ACPI/WMI only.


@dataclass(frozen=True)
class Effect:
    key: str
    title: str
    code: int
    uses_color: bool
    uses_speed: bool
    cycle: bool = False      # meteor variants that also enable the global color cycle
    sync: bool = False       # Vantage applies it to every zone except ambient
    basic: bool = True       # available on ambient too


EFFECTS = [
    Effect("off", "Off", 0x00, False, False),
    Effect("static", "Static", 0x01, True, False),
    Effect("flicker", "Flicker", 0x02, True, True),
    Effect("breathing", "Breathing", 0x03, True, True),
    Effect("wave", "Wave", 0x04, False, True, sync=True, basic=False),
    Effect("spectrum", "Spectrum", 0x06, False, True, sync=True, basic=False),
    Effect("rainbow", "Rainbow", 0x09, False, True, basic=False),
    Effect("random", "Random", 0x0A, False, True, basic=False),
    Effect("meteor", "Meteor", 0x0B, True, True, basic=False),
    Effect("meteor-rainbow", "Meteor rainbow", 0x0C, False, True, basic=False),
    Effect("meteor-cycle", "Meteor cycle", 0x0B, True, True, cycle=True, basic=False),
    Effect("meteor-rainbow-cycle", "Meteor rainbow cycle", 0x0C, False, True, cycle=True, basic=False),
]
EFFECTS_BY_KEY = {e.key: e for e in EFFECTS}


def effects_for(panel: Panel) -> list[Effect]:
    return EFFECTS if panel.full_effects else [e for e in EFFECTS if e.basic]


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


def _uses_cycle(states: dict[str, ZoneState]) -> bool:
    return any(s.effect.cycle for s in states.values())


def build_apply(states: dict[str, ZoneState],
                previous: dict[str, ZoneState] | None = None) -> list[bytes]:
    """Full update in Vantage's order.

    Zone packets, then (if a meteor cycle effect is used) the cycle commands,
    then apply and save. When leaving the cycle mode, `cc 42 00` goes first,
    as Vantage does. `states` must hold every zone key.
    """
    missing = [z.key for z in ZONES if z.key not in states]
    if missing:
        raise ValueError(f"missing zone states: {', '.join(missing)}")
    packets = []
    cycle = _uses_cycle(states)
    if not cycle and previous is not None and _uses_cycle(previous):
        packets.append(_packet(CMD_CYCLE, 0x00))
    packets += [build_zone(z, states[z.key]) for z in ZONES]
    if cycle:
        packets += [_packet(CMD_CYCLE_PARAM, 0xFF, 0x00, 0x00), _packet(CMD_CYCLE, 0x01)]
    packets += [_packet(CMD_APPLY, 0xFF, 0xFF, 0x00), _packet(CMD_SAVE)]
    return packets


def set_panel(states: dict[str, ZoneState], panel: Panel, *, effect: Effect | None = None,
              speed: int | None = None, brightness: int | None = None,
              rgb: tuple[int, int, int] | None = None) -> dict[str, ZoneState]:
    """New states with one panel changed, following Vantage's rules.

    Sync effects (wave, spectrum) go to every zone except ambient, as Vantage
    does.
    """
    if effect is not None and effect not in effects_for(panel):
        raise ValueError(f"{panel.title} does not support {effect.title}")
    new = dict(states)
    targets = list(panel.zones)
    if effect is not None and effect.sync:
        targets = [z.key for z in ZONES if z.key != "ambient"]
    for key in targets:
        s = new[key]
        new[key] = replace(s, effect=effect or s.effect,
                           speed=s.speed if speed is None else speed,
                           brightness=s.brightness if brightness is None else brightness,
                           rgb=s.rgb if rgb is None else rgb)
    return new


def build_read() -> bytes:
    return _packet(CMD_READ, 0x18)


@dataclass(frozen=True)
class ReadEntry:
    zone_code: int
    effect_code: int
    speed: int
    brightness: int
    rgb: tuple[int, int, int]


READ_FIRST_ZONE = 0x10
READ_HEADER = 5   # cc 01 NN 00 00
READ_ENTRY = 6    # EE SS BB RR GG BB


def parse_read(response: bytes) -> list[ReadEntry]:
    """Entries of the reply to build_read(), one per zone code from 0x10 up."""
    if len(response) < READ_HEADER or response[0] != REPORT_ID or response[1] != 0x01:
        raise ValueError(f"unexpected read reply: {response[:8].hex()}")
    count = response[2]
    if READ_HEADER + count * READ_ENTRY > len(response):
        raise ValueError(f"read reply too short for {count} entries")
    entries = []
    for i in range(count):
        e = response[READ_HEADER + i * READ_ENTRY:READ_HEADER + (i + 1) * READ_ENTRY]
        entries.append(ReadEntry(READ_FIRST_ZONE + i, e[0], e[1], e[2], (e[3], e[4], e[5])))
    return entries


def states_from_read(entries: list[ReadEntry],
                     fallback: dict[str, ZoneState]) -> dict[str, ZoneState]:
    """Zone states from a read; what a read cannot tell comes from `fallback`.

    The cycle variants of the meteor effects share their code with the plain
    ones (the cycle is a global switch), so the fallback decides between them.
    Unknown effect codes or out-of-range values keep the fallback state.
    """
    by_code = {e.zone_code: e for e in entries}
    plain = {e.code: e for e in EFFECTS if not e.cycle}
    states = dict(fallback)
    for z in ZONES:
        e = by_code.get(z.code)
        if e is None or e.effect_code not in plain:
            continue
        if not (SPEED_RANGE[0] <= e.speed <= SPEED_RANGE[1]
                and BRIGHTNESS_RANGE[0] <= e.brightness <= BRIGHTNESS_RANGE[1]):
            continue
        effect = plain[e.effect_code]
        if fallback[z.key].effect.cycle and fallback[z.key].effect.code == effect.code:
            effect = fallback[z.key].effect
        states[z.key] = ZoneState(effect, e.speed, e.brightness, e.rgb)
    return states


def vantage_default() -> dict[str, ZoneState]:
    """The state seen at the start of the first capture (ambient static, fans rainbow)."""
    color = (0x00, 0xD3, 0xFE)
    states = {z.key: ZoneState(EFFECTS_BY_KEY["rainbow"], 2, 3, color) for z in ZONES}
    states["ambient"] = ZoneState(EFFECTS_BY_KEY["static"], 2, 4, color)
    return states


def hexdump(packet: bytes) -> str:
    """Compact hex, trailing zeros elided, for previews and logs."""
    end = len(packet.rstrip(b"\x00")) or 1
    body = " ".join(f"{b:02x}" for b in packet[:end])
    return body + (f"  (+{len(packet) - end} zero bytes)" if end < len(packet) else "")
