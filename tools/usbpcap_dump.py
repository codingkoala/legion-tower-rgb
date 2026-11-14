#!/usr/bin/env python3
"""Dump USB control transfers from a USBPcap capture (pcapng, linktype 249).

Usage: usbpcap_dump.py CAPTURE.pcapng [BUS DEVICE] [--reports]

Without --reports, prints one line per packet. With --reports, prints only
HID SET_REPORT / GET_REPORT feature transfers as "time  SET|GET  payload",
with a "----" line between bursts, which is what protocol work needs.
No third-party dependencies; reads the file only.
"""

from __future__ import annotations

import struct
import sys


def _blocks(data: bytes):
    off, le = 0, "<"
    while off + 12 <= len(data):
        if data[off:off + 4] == b"\x0a\x0d\x0d\x0a":  # section header: byte order
            le = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
        btype, blen = struct.unpack_from(le + "II", data, off)
        if blen < 12:
            break
        yield btype, data[off + 8:off + blen - 4], le
        off += blen


def packets(path: str):
    """(time_s, header_dict, payload) for every USBPcap packet."""
    links = []
    for btype, body, le in _blocks(open(path, "rb").read()):
        if btype == 1:  # interface description
            links.append(struct.unpack_from(le + "H", body, 0)[0])
        elif btype == 6:  # enhanced packet
            iface, th, tl, caplen, _ = struct.unpack_from(le + "IIIII", body, 0)
            if links[iface] != 249:
                continue
            p = body[20:20 + caplen]
            hlen, _irp, status, _func, info, bus, dev, ep, xfer, dlen = struct.unpack_from("<HQIHBHHBBI", p, 0)
            hdr = dict(status=status, inbound=bool(info & 1), bus=bus, dev=dev, ep=ep, xfer=xfer,
                       stage=p[27] if xfer == 2 and hlen >= 28 else None)
            yield ((th << 32) | tl) / 1e6, hdr, p[hlen:hlen + dlen]


def main(argv: list[str]) -> int:
    reports = "--reports" in argv
    args = [a for a in argv if a != "--reports"]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    bus = int(args[1]) if len(args) > 2 else None
    dev = int(args[2]) if len(args) > 2 else None
    t0 = last = None
    pending_get = None
    for ts, h, payload in packets(args[0]):
        if bus is not None and (h["bus"], h["dev"]) != (bus, dev):
            continue
        t0 = ts if t0 is None else t0
        t = ts - t0
        if not reports:
            print(f"{t:9.3f} {'IN ' if h['inbound'] else 'OUT'} {h['bus']}.{h['dev']} ep={h['ep']:02x} "
                  f"x={h['xfer']} stage={h['stage']} len={len(payload):3d} {payload.hex()}")
            continue
        line = None
        if not h["inbound"] and len(payload) >= 8 and payload[0] == 0x21 and payload[1] == 0x09:
            line = f"SET {payload[8:].hex()}"
        elif not h["inbound"] and len(payload) >= 8 and payload[0] == 0xA1 and payload[1] == 0x01:
            pending_get = payload[2:4].hex()
        elif h["inbound"] and pending_get is not None and payload:
            line = f"GET {payload.hex()}"
            pending_get = None
        if line:
            if last is not None and t - last > 0.5:
                print("----")
            last = t
            print(f"{t:9.3f} {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
