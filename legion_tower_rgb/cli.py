"""Command line interface. Dry run unless --write is given."""

from __future__ import annotations

import argparse
import dataclasses
import sys

from . import config, device, protocol


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
    states = protocol.vantage_default() if args.from_default else config.load_state()
    keys = [z.key for z in protocol.ZONES] if args.zone == "all" else [args.zone]
    for key in keys:
        s = states[key]
        states[key] = dataclasses.replace(
            s,
            effect=protocol.EFFECTS_BY_KEY[args.effect] if args.effect else s.effect,
            speed=args.speed if args.speed is not None else s.speed,
            brightness=args.brightness if args.brightness is not None else s.brightness,
            rgb=args.color if args.color is not None else s.rgb)
    if not args.write:
        print("Dry run (nothing is sent; add --write to send):")
    try:
        packets = device.apply(states, allow_write=args.write)
    except (device.DeviceError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.write:
        config.save_state(states)
    for p in packets:
        print(f"  {protocol.hexdump(p)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legion-tower-rgb-cli",
                                     description="Lenovo Legion Tower lighting control")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("detect", help="find the controller (reads sysfs only)").set_defaults(func=cmd_detect)

    p = sub.add_parser("set", help="change one zone (or all) and send the full state")
    p.add_argument("zone", choices=[z.key for z in protocol.ZONES] + ["all"])
    p.add_argument("effect", nargs="?", choices=list(protocol.EFFECTS_BY_KEY))
    p.add_argument("--color", type=_rgb, help="RRGGBB")
    p.add_argument("--speed", type=int)
    p.add_argument("--brightness", type=int)
    p.add_argument("--from-default", action="store_true",
                   help="start from the state seen in the Vantage capture, not the saved one")
    p.add_argument("--write", action="store_true", help="really send the packets to the hardware")
    p.set_defaults(func=cmd_set)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
