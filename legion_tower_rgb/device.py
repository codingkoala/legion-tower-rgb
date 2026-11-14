"""The Legion Tower lighting controller, with writes locked by default.

Nothing in this project sends data to the hardware unless the caller passes
allow_write=True. Until the protocol is verified on a given machine, every
front end (CLI and GUI) defaults to a dry run that only shows the packets.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import hidraw, protocol
from .protocol import Effect, Zone


class DeviceError(Exception):
    pass


class DeviceNotFound(DeviceError):
    pass


class DevicePermissionError(DeviceError):
    pass


class WriteLocked(DeviceError):
    pass


@dataclass(frozen=True)
class Controller:
    info: hidraw.HidrawInfo

    @property
    def feature_reports(self) -> dict[int, int]:
        return hidraw.feature_reports(self.info.descriptor)

    @property
    def supports_lighting_report(self) -> bool:
        size = self.feature_reports.get(protocol.REPORT_ID)
        return size is not None and size + 1 >= protocol.PACKET_LENGTH


def find_controllers() -> list[Controller]:
    """Matching controllers, discovered through sysfs only (no device is opened)."""
    return [Controller(i) for i in hidraw.list_hidraw()
            if (i.vendor_id, i.product_id) == (protocol.VENDOR_ID, protocol.PRODUCT_ID)
            and protocol.REPORT_ID in hidraw.feature_reports(i.descriptor)]


def set_mode(zone: Zone, effect: Effect, speed: int, brightness: int,
             rgb: tuple[int, int, int], *, allow_write: bool = False,
             controller: Controller | None = None) -> list[bytes]:
    """Build the packets for a zone and, only if allow_write, send them.

    Returns the packets either way, so front ends can show what would be sent.
    """
    packets = protocol.build_set_mode(zone, effect, speed, brightness, rgb)
    if not allow_write:
        return packets
    if controller is None:
        found = find_controllers()
        if not found:
            raise DeviceNotFound("No Legion Tower lighting controller (17ef:c955) found")
        controller = found[0]
    try:
        with hidraw.Hidraw(controller.info.path) as dev:
            for p in packets:
                dev.send_feature(p)
    except PermissionError as exc:
        raise DevicePermissionError(
            f"No permission on {controller.info.path}: install the udev rule "
            "(sudo ./install-udev.sh)") from exc
    except OSError as exc:
        raise DeviceError(f"{controller.info.path}: {exc}") from exc
    return packets
