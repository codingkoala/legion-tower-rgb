# Protocol notes

Status legend: **[OpenRGB]** taken from OpenRGB, unverified here;
**[verified]** confirmed on real hardware; **[unknown]** to be found.

## Controller

USB `17ef:c955`, ITE IT8297, one HID interface, usage page `0xFF89`.

Report descriptor (Legion T5 26ARA8):

```
06 89 ff  09 10  a1 01  85 5a  09 01 15 00 26 ff 00 75 08 95 10  b1 00  c0
06 89 ff  09 cc  a1 01  85 cc  09 01 15 00 26 ff 00 75 08 95 3f  b1 00  c0
```

- Feature report `0x5A`, 16 bytes payload, usage `0x10`. **[unknown]**
- Feature report `0xCC`, 63 bytes payload, usage `0xCC`: lighting commands.

## Update sequence [capture]

From a USBPcap capture of Lenovo Vantage (Legion T5 26ARA8). Every change in
Vantage sends the **whole state**: one packet per zone, ~65 ms apart, then two
commit packets. All are `SET_REPORT` (bmRequestType `0x21`, bRequest `0x09`,
wValue `0x03CC`, wLength 64). Vantage never reads anything back and never uses
report `0x5A`.

```
cc ZZ EE SS BB RR GG BB ...   x 8 zones, order 18 13 11 10 14 12 15 17
cc 2d ff ff 00 ...            commit
cc 5e ...                     save (?)
```

Vantage does not clear its buffer: after the meaningful bytes the packets carry
stale memory (heap pointers, ASCII fragments), which the firmware presumably
ignores. This project sends zeros there.

| Field | Values |
|---|---|
| ZZ zone | `18` ambient, `13` CPU fan, `11` rear fan, `10` front fan upper, `14` front fan lower, `12` top fan front, `15` top fan rear, `17` logo **[verified]** (OpenRGB's `12` = CPU fan does not hold here) |
| EE effect | see *Effects* below **[verified]** |
| SS speed | 1-4, Vantage's slider value as is **[verified]** |
| BB brightness | 1-4, Vantage's slider value as is **[verified]** |
| RR GG BB | color in R, G, B order (logo static `ff 00 00` shows red) **[verified]** |

Replayed from Linux with zeroed padding (2026-11-14, T5 26ARA8): the full
update switches ambient from breathing to static, and ambient brightness 1 dims
the strip to its minimum **[verified]**. The stale bytes Vantage sends are not needed.
Zone IDs were then mapped by switching one zone off at a time (effect `00`) and
noting which light went dark. The GPU lighting Vantage offers is not on this
controller: no zone ID reaches it (candidates: WMI `LENOVO_GAMEZONE_GPU_LED_DATA`,
or the graphics card's own controller).

Captured sequence (zone, field: values) and matching bytes:

- ambient brightness 4 3 2 1 2 3 4: `cc 18 01 02 0N`
- ambient effect off, static, flicker, breathing: `cc 18 00/01/02/03`
- CPU fan brightness 4 3 2 1 2 3 4: `cc 13 09 02 0N`
- CPU fan speed 1 2 3 4 3 2: `cc 13 09 0N 04`

## Effects [capture]

From `lights_fx.pcapng` (CPU fan, every effect Vantage offers, in order):

| Vantage name | EE | Notes |
|---|---|---|
| Off | `00` | |
| Static | `01` | |
| Flicker | `02` | |
| Breath | `03` | |
| Wave | `04` | Vantage sets it on every zone except ambient |
| Spectrum | `06` | same as wave |
| CPU temperature | `01` | not a firmware effect: Vantage sends static with a color it computes from the CPU temperature (`00a0ff`, `00ffff`, `00ffa0`, ... seen) on every zone except ambient |
| Rainbow | `09` | |
| Random | `0a` | |
| Meteor | `0b` | |
| Meteor rainbow | `0c` | |
| Meteor cycle | `0b` | plus `cc 41 ff 00 00` and `cc 42 01` before the apply packet |
| Meteor rainbow cycle | `0c` | same extra packets |

Leaving a cycle effect, Vantage sends `cc 42 00` before the zone packets.
Ambient only offers off, static, flicker and breath.

## WMI: LENOVO_LIGHTING_INFO_LIST [firmware]

Read on Windows with `Get-CimInstance -Namespace root\WMI`. One instance per
zone; `type 1` rows are the zones of this controller (zoneid in decimal):

| panelid | zoneid | zone | IsSupportRGB | mode mask |
|---|---|---|---|---|
| 2 | 24 (`0x18`) | ambient | 1 | `0x10000007` |
| 3 | 19 (`0x13`) | CPU fan | 2 | `0x1007832f` |
| 4 | 17 (`0x11`) | rear fan | 2 | `0x1007832f` |
| 7 | 16, 20 (`0x10`, `0x14`) | front fans | 2 | `0x1007832f` |
| 8 | 18, 21 (`0x12`, `0x15`) | top fans | 2 | `0x1007832f` |
| 13 | 23 (`0x17`) | logo | 2 | `0x1007832f` |
| 15 | 1, type 3 | GPU wordmark (on/off) | 1 | `0x10000001` |
| 16 | 1, type 3 | GPU RGB | 2 | `0x10000107` |

Every type 1 row lists `applycmd` 45 (`0x2D`), `Savecmd` 94 (`0x5E`),
`Readcmd` 96 (`0x60`), matching the captured apply/save packets. A read
command `0x60` exists but Vantage never used it in the captures (no
GET_REPORT at all). Mode mask: bit *n* (n < 15) = effect code *n*+1, bits
15-18 = the four meteor entries, bit 28 = off (matches every list above).

## Reading the state [verified]

`cc 60 18` (SET_REPORT), then GET_REPORT `0xCC` (64 bytes) returns:

```
cc 01 NN 00 00 | EE SS BB RR GG BB  x NN
```

`NN` = 9 entries, for zone codes `0x10` to `0x18` in order (`0x16` has no light
on this model and reads `09 01 04 000000`). Verified on the T5 26ARA8: after
writing ambient static / brightness 1 / `ff0000`, the read returns
`01 02 01 ff0000` for `0x18`, and every other zone matches the last write.
The zone byte after `0x60` seems ignored (all zones come back).

Without the `cc 60` first, GET_REPORT returns the controller's stale USB
buffer (an echo of the request plus a piece of its HID descriptor); report
`0x5A` reads all zeros.

The firmware stores a color for the ambient zone, but the strip is white only
(seen by eye; WMI `IsSupportRGB` = 1 for it, 2 for the RGB zones).

The GPU (type 3) does not appear on USB: changing it in Vantage only re-sends
the unchanged zone packets. It goes through ACPI/WMI; on Linux that needs a
kernel driver.

## OpenRGB's LenovoMotherboardController (sibling model, for reference)

Two packets per zone: `cc ZZ MM SS BB RR GG BB` and `cc 28 06 ...` with the same
fields at byte 33; zones `12` CPU fan and `11` rear fan; effects add `04` wave,
`06` specter, `0a` random. The `28 06` packet does not appear in the Vantage
capture on the 26ARA8.
