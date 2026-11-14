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
| EE effect | `00` off, `01` static, `02` flicker, `03` breathing **[verified]**; `09` rainbow wave (default on the fans) |
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

## OpenRGB's LenovoMotherboardController (sibling model, for reference)

Two packets per zone: `cc ZZ MM SS BB RR GG BB` and `cc 28 06 ...` with the same
fields at byte 33; zones `12` CPU fan and `11` rear fan; effects add `04` wave,
`06` specter, `0a` random. The `28 06` packet does not appear in the Vantage
capture on the 26ARA8.
