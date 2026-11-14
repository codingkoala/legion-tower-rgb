"""Minimal hidraw access: sysfs discovery (read-only) and feature-report ioctls."""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass
from pathlib import Path

SYSFS_HIDRAW = Path("/sys/class/hidraw")

# linux/hidraw.h: HIDIOCSFEATURE(len) = _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, len)
_IOC_WRITE, _IOC_READ = 1, 2


def _ioc(direction: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


def HIDIOCSFEATURE(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, 0x06, size)


def HIDIOCGFEATURE(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, 0x07, size)


@dataclass(frozen=True)
class HidrawInfo:
    path: str          # /dev/hidrawN
    name: str
    vendor_id: int
    product_id: int
    descriptor: bytes


def _parse_uevent(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def list_hidraw() -> list[HidrawInfo]:
    """All hidraw nodes, from sysfs only: no device is opened."""
    found = []
    for node in sorted(SYSFS_HIDRAW.glob("hidraw*")):
        try:
            ev = _parse_uevent((node / "device" / "uevent").read_text())
            descriptor = (node / "device" / "report_descriptor").read_bytes()
        except OSError:
            continue
        try:
            _bus, vid, pid = ev["HID_ID"].split(":")
        except (KeyError, ValueError):
            continue
        found.append(HidrawInfo(f"/dev/{node.name}", ev.get("HID_NAME", "?"),
                                int(vid, 16), int(pid, 16), descriptor))
    return found


def feature_reports(descriptor: bytes) -> dict[int, int]:
    """Feature report IDs -> payload size in bytes, from a HID report descriptor.

    Handles the short items a vendor descriptor typically uses; enough to
    check that a device exposes the report we expect before talking to it.
    """
    reports: dict[int, int] = {}
    report_id = 0
    report_size = report_count = 0
    i = 0
    while i < len(descriptor):
        prefix = descriptor[i]
        if prefix == 0xFE:  # long item
            i += 3 + descriptor[i + 1]
            continue
        size = (0, 1, 2, 4)[prefix & 0x03]
        data = int.from_bytes(descriptor[i + 1:i + 1 + size], "little")
        tag = prefix & 0xFC
        if tag == 0x84:
            report_id = data
        elif tag == 0x74:
            report_size = data
        elif tag == 0x94:
            report_count = data
        elif tag == 0xB0:  # Feature main item
            bits = reports.get(report_id, 0) * 8 + report_size * report_count
            reports[report_id] = bits // 8
        i += 1 + size
    return reports


class Hidraw:
    """An opened hidraw node. Opening needs read/write permission on the node."""

    def __init__(self, path: str):
        self.path = path
        self._fd = os.open(path, os.O_RDWR)

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> "Hidraw":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def send_feature(self, packet: bytes) -> None:
        buf = bytearray(packet)
        fcntl.ioctl(self._fd, HIDIOCSFEATURE(len(buf)), buf)

    def get_feature(self, report_id: int, length: int) -> bytes:
        buf = bytearray(length)
        buf[0] = report_id
        fcntl.ioctl(self._fd, HIDIOCGFEATURE(len(buf)), buf)
        return bytes(buf)
