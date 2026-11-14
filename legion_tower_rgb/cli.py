"""Command line interface. Dry run unless --write is given."""

from __future__ import annotations

import argparse
import sys

from . import device, protocol


def _rgb(text: str) -> tuple[int, int, int]:
    text = text.lstrip("#")
    if len(text) != 6:
        raise argparse.ArgumentTypeError("color must be RRGGBB")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def cmd_detect(_args) -> int:
    found = device.find_controllers()
    if not found:
        print("No Legion Tower lighting controller (17ef:c955) found.")
        return 1
    for c in found:
        reports = ", ".join(f"0x{rid:02x} ({size} B)" for rid, size in c.feature_reports.items())
        print(f"{c.info.path}  {c.info.name}  feature reports: {reports}")
    return 0


def cmd_set(args) -> int:
    zones = list(protocol.Zone) if args.zone == "all" else [protocol.Zone[args.zone.upper().replace("-", "_")]]
    effect = protocol.EFFECTS_BY_KEY[args.effect]
    if not args.write:
        print("Dry run (nothing is sent; add --write to send):")
    try:
        for zone in zones:
            packets = device.set_mode(zone, effect, args.speed, args.brightness, args.color,
                                      allow_write=args.write)
            for p in packets:
                print(f"  {protocol.ZONE_TITLES[zone]:9} {protocol.hexdump(p)}")
    except (device.DeviceError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legion-tower-rgb-cli",
                                     description="Lenovo Legion Tower lighting control")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("detect", help="find the controller (reads sysfs only)").set_defaults(func=cmd_detect)

    p = sub.add_parser("set", help="set a zone's effect")
    p.add_argument("zone", choices=["cpu-fan", "rear-fan", "all"])
    p.add_argument("effect", choices=list(protocol.EFFECTS_BY_KEY))
    p.add_argument("--color", type=_rgb, default=(255, 0, 0), help="RRGGBB (default ff0000)")
    p.add_argument("--speed", type=int, default=protocol.SPEED_RANGE[0])
    p.add_argument("--brightness", type=int, default=protocol.BRIGHTNESS_RANGE[1])
    p.add_argument("--write", action="store_true", help="really send the packets to the hardware")
    p.set_defaults(func=cmd_set)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
