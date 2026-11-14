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

## Set mode [OpenRGB]

Two 64-byte feature reports per zone, sent back to back, no delay:

```
#1: cc ZZ MM SS BB RR GG BB 00 ...
#2: cc 28 06 00 ... (byte 33) ZZ MM SS BB RR GG BB 00 ...
```

| Field | Values |
|---|---|
| ZZ zone | `0x12` CPU fan, `0x11` rear fan |
| MM effect | `01` static, `02` sparkle, `03` breathing, `04` wave, `06` specter, `09` rainbow wave, `0a` random |
| SS speed | 1-4 (direction of the scale unknown) |
| BB brightness | 1-4 |

Open questions: meaning of `28 06`; whether settings persist across power cycles;
zones for the front fans, the logo and the strip; what `0x5A` returns.
