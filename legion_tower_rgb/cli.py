"""Command line interface. Dry run unless --write is given."""

from __future__ import annotations

import argparse
import sys

from . import config, device, gpu, protocol


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


def cmd_status(_args) -> int:
    states, source = device.current_state()
    print(f"State ({'read from the controller' if source == 'device' else 'last saved, controller not readable'}):")
    for z in protocol.ZONES:
        s = states[z.key]
        color = " #%02x%02x%02x" % s.rgb if s.effect.uses_color and z.key != "ambient" else ""
        print(f"  {z.title:17} {s.effect.title:21} speed {s.speed}  brightness {s.brightness}{color}")
    return 0


def cmd_gpu(args) -> int:
    state = config.load_gpu()
    if args.effect:
        state.effect = gpu.EFFECTS_BY_KEY[args.effect]
    for field in ("speed", "brightness"):
        if getattr(args, field) is not None:
            setattr(state, field, getattr(args, field))
    if args.color is not None:
        state.rgb = args.color
    if args.wordmark is not None:
        state.wordmark = args.wordmark == "on"
    try:
        transfers = gpu.build_all(state)
        if args.write:
            gpu.send(transfers)
            config.save_gpu(state)
        else:
            print("Dry run (nothing is sent; add --write to send):")
    except (gpu.GpuError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for t in transfers:
        print(f"  {gpu.format_transfer(t)}")
    return 0


def cmd_report(_args) -> int:
    """Hardware facts for a new-model report. Reads sysfs only: no device is opened."""
    from pathlib import Path

    from . import __version__, hidraw

    def read(path: str) -> str:
        try:
            return Path(path).read_text().strip()
        except OSError:
            return "?"

    print(f"legion-tower-rgb {__version__}")
    print("== System")
    for f in ("sys_vendor", "product_name", "product_version", "board_name", "bios_version"):
        print(f"{f}: {read('/sys/class/dmi/id/' + f)}")
    print("== Lenovo / ITE HID devices")
    for i in hidraw.list_hidraw():
        if i.vendor_id in (0x17EF, 0x048D):
            reports = ", ".join(f"0x{r:02x} ({n} B)" for r, n in hidraw.feature_reports(i.descriptor).items())
            print(f"{i.path} {i.vendor_id:04x}:{i.product_id:04x} {i.name}")
            print(f"  feature reports: {reports or 'none'}")
            print(f"  report descriptor: {i.descriptor.hex()}")
    print("== GPUs")
    for dev in sorted(Path("/sys/bus/pci/devices").iterdir()):
        if read(str(dev / "class")).startswith("0x03"):
            ids = [read(str(dev / f))[2:] for f in ("vendor", "device", "subsystem_vendor", "subsystem_device")]
            print(f"{dev.name} {ids[0]}:{ids[1]} subsystem {ids[2]}:{ids[3]}")
    adapter = gpu.find_adapter()
    print(f"Lenovo NVIDIA I2C adapter: {adapter or 'none'}")
    return 0


def _target(key: str) -> protocol.Panel:
    """A panel, or a single zone wrapped as a one-zone panel."""
    if key in protocol.PANELS_BY_KEY:
        return protocol.PANELS_BY_KEY[key]
    zone = protocol.ZONES_BY_KEY[key]
    return protocol.Panel(zone.key, zone.title, (zone.key,), zone.key != "ambient")


def cmd_set(args) -> int:
    if args.from_default:
        previous = protocol.vantage_default()
    elif args.write:
        previous = device.current_state()[0]
    else:
        previous = config.load_state()  # a dry run does not touch the device at all
    targets = protocol.PANELS if args.target == "all" else [_target(args.target)]
    effect = protocol.EFFECTS_BY_KEY[args.effect] if args.effect else None
    states = previous
    try:
        for panel in targets:
            if args.target == "all" and effect and effect not in protocol.effects_for(panel):
                continue  # e.g. ambient has no wave
            states = protocol.set_panel(states, panel, effect=effect, speed=args.speed,
                                        brightness=args.brightness, rgb=args.color)
        if not args.write:
            print("Dry run (nothing is sent; add --write to send):")
        packets = device.apply(states, previous=previous, allow_write=args.write)
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
    sub.add_parser("status", help="read the current state from the controller").set_defaults(func=cmd_status)
    sub.add_parser("report", help="hardware facts for a new-model report (reads sysfs only)").set_defaults(
        func=cmd_report)

    targets = [p.key for p in protocol.PANELS] + [z.key for z in protocol.ZONES
                                                  if z.key not in protocol.PANELS_BY_KEY] + ["all"]
    p = sub.add_parser("set", help="change a light (panel or single zone) and send the full state")
    p.add_argument("target", choices=targets)
    p.add_argument("effect", nargs="?", choices=list(protocol.EFFECTS_BY_KEY))
    p.add_argument("--color", type=_rgb, help="RRGGBB")
    p.add_argument("--speed", type=int)
    p.add_argument("--brightness", type=int)
    p.add_argument("--from-default", action="store_true",
                   help="start from the state seen in the Vantage capture, not the saved one")
    p.add_argument("--write", action="store_true", help="really send the packets to the hardware")
    p.set_defaults(func=cmd_set)

    g = sub.add_parser("gpu", help="GPU strip and wordmark (Lenovo OEM GeForce RTX 40)")
    g.add_argument("effect", nargs="?", choices=list(gpu.EFFECTS_BY_KEY))
    g.add_argument("--color", type=_rgb, help="RRGGBB")
    g.add_argument("--speed", type=int)
    g.add_argument("--brightness", type=int)
    g.add_argument("--wordmark", choices=["on", "off"])
    g.add_argument("--write", action="store_true", help="really send the transfers to the GPU")
    g.set_defaults(func=cmd_gpu)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
