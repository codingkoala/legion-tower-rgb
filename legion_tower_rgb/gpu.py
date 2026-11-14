"""Lighting of Lenovo OEM GeForce RTX 40 cards, over the GPU's I2C bus.

See docs/GPU.md. The controller sits at 0x49 on the DDC side of the GPU's
first I2C port, which the NVIDIA driver exposes as "NVIDIA i2c adapter 1"
(/dev/i2c-N). Every transfer is a register byte plus data; the controller
auto-increments. Builders only return bytes, so they are safe to test.
"""

from __future__ import annotations

import fcntl
import os
import time
from dataclasses import dataclass
from pathlib import Path

ADDRESS = 0x49
ADAPTER_NAME = "NVIDIA i2c adapter 1"
I2C_SLAVE = 0x0703
TRANSFER_GAP_S = 0.010  # Vantage waits 10 ms after each transfer
LENOVO_PCI_SUBVENDOR = "0x17aa"

REG_BEGIN, REG_EFFECT, REG_BRIGHTNESS, REG_CONST, REG_TIMING = 0x30, 0x15, 0x17, 0x1B, 0x20
REG_COMMIT, REG_APPLY, REG_WORDMARK = 0x31, 0x32, 0x50
BEGIN, COMMIT, APPLY = 0xB0, 0xB1, 0xB2
CONST = (0x00, 0xC8, 0xFF)

SPEED_RANGE = (1, 4)
BRIGHTNESS_RANGE = (1, 4)


@dataclass(frozen=True)
class GpuEffect:
    key: str
    title: str
    code: int
    uses_color: bool
    uses_speed: bool


EFFECTS = [
    GpuEffect("off", "Off", 0x00, False, False),
    GpuEffect("static", "Static", 0x01, True, False),
    GpuEffect("flicker", "Flicker", 0x02, True, True),
    GpuEffect("breathing", "Breathing", 0x03, True, True),
    GpuEffect("rainbow", "Rainbow", 0x04, False, True),
]
EFFECTS_BY_KEY = {e.key: e for e in EFFECTS}

# Flicker / breathing period in ms, and rainbow step, per speed 1..4.
_PERIOD_MS = {1: 2000, 2: 1500, 3: 1000, 4: 500}
_RAINBOW_STEP = {1: 0xF0, 2: 0xCB, 3: 0xA0, 4: 0x78}

Transfer = tuple[int, bytes]  # (register, data)


@dataclass
class GpuState:
    effect: GpuEffect
    speed: int
    brightness: int
    rgb: tuple[int, int, int]
    wordmark: bool


def _check(name: str, value: int, bounds: tuple[int, int]) -> None:
    if not bounds[0] <= value <= bounds[1]:
        raise ValueError(f"{name} must be between {bounds[0]} and {bounds[1]}, got {value}")


def build_strip(state: GpuState) -> list[Transfer]:
    e = state.effect
    _check("speed", state.speed, SPEED_RANGE)
    _check("brightness", state.brightness, BRIGHTNESS_RANGE)
    out: list[Transfer] = [(REG_BEGIN, bytes([BEGIN])), (REG_EFFECT, bytes([e.code]))]
    if e.key in ("static", "flicker", "breathing"):
        out.append((REG_BRIGHTNESS, bytes([state.brightness * 25, *state.rgb, *CONST])))
        if e.key != "static":
            ms = _PERIOD_MS[state.speed].to_bytes(2, "big")
            out.append((REG_TIMING, ms * 2))
    else:  # off, rainbow
        out.append((REG_CONST, bytes(CONST)))
        if e.key == "rainbow":
            out.append((REG_TIMING, bytes([0x00, _RAINBOW_STEP[state.speed]])))
    return out + [(REG_COMMIT, bytes([COMMIT])), (REG_APPLY, bytes([APPLY]))]


def build_wordmark(on: bool) -> list[Transfer]:
    return [(REG_BEGIN, bytes([BEGIN])), (REG_WORDMARK, bytes([0x01 if on else 0x00])),
            (REG_CONST, bytes(CONST)), (REG_COMMIT, bytes([COMMIT])), (REG_APPLY, bytes([APPLY]))]


def format_transfer(t: Transfer) -> str:
    return f"{t[0]:02x} <- {t[1].hex(' ')}"


class GpuError(Exception):
    pass


def find_adapter() -> str | None:
    """/dev/i2c-N of the Lenovo NVIDIA card's first I2C port (sysfs only, no bus access)."""
    for dev in sorted(Path("/sys/class/i2c-dev").glob("i2c-*")):
        try:
            name = (dev / "name").read_text().strip()
        except OSError:
            continue
        if not name.startswith(ADAPTER_NAME + " "):
            continue
        pci = (dev / "device").resolve().parent  # i2c-N -> PCI device of the GPU
        try:
            if (pci / "subsystem_vendor").read_text().strip() != LENOVO_PCI_SUBVENDOR:
                continue
        except OSError:
            continue
        return f"/dev/{dev.name}"
    return None


def send(transfers: list[Transfer], adapter: str | None = None) -> None:
    adapter = adapter or find_adapter()
    if adapter is None:
        raise GpuError("No Lenovo NVIDIA GPU I2C adapter found")
    try:
        fd = os.open(adapter, os.O_RDWR)
    except PermissionError as exc:
        raise GpuError(f"No permission on {adapter}: install the udev rule (sudo ./install-udev.sh)") from exc
    try:
        fcntl.ioctl(fd, I2C_SLAVE, ADDRESS)
        for reg, data in transfers:
            os.write(fd, bytes([reg]) + data)
            time.sleep(TRANSFER_GAP_S)
    except OSError as exc:
        raise GpuError(f"{adapter}: {exc}") from exc
    finally:
        os.close(fd)


def default_state() -> GpuState:
    """Vantage's default (style_1 in its GPU profile): rainbow, speed 2, brightness 3."""
    return GpuState(EFFECTS_BY_KEY["rainbow"], 2, 3, (0x00, 0xD3, 0xFE), True)


def build_all(state: GpuState) -> list[Transfer]:
    return build_strip(state) + build_wordmark(state.wordmark)
