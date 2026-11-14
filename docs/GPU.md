# GPU lighting (Lenovo OEM GeForce RTX 40)

Status: **verified from Linux: wordmark on/off and every strip effect (off, static, flicker, breathing, rainbow).**

The graphics card in the Legion T5 26ARA8 (RTX 4070 SUPER, `10de:2783`,
subsystem `17aa:e138`) has its own lighting microcontroller: an RGB strip and
a white wordmark. It is not on the ITE USB controller and not on ACPI; Lenovo
Vantage reaches it through the GPU's I2C bus with NVIDIA's NvAPI.

Sources:

- Static analysis of Vantage's gaming add-in (its RTX 40 lighting class), done
  only to learn the bus parameters and register values; no Lenovo code is
  included here.
- [legion-gpu-rgb](https://github.com/violentbunny/legion-gpu-rgb) (GPL-2.0),
  which found the same controller on an RTX 5070 Ti from a Legion Tower 5 Gen 10
  by hooking Lenovo's service. Our findings agree with theirs on every register
  they document, and add the animated effects.

## Transport

`NvAPI_I2CWrite` with `NV_I2C_INFO_V3`:

| Field | Value |
|---|---|
| device address | `0x92` (8-bit) = **`0x49`** (7-bit) |
| `bIsDDCPort` | **1** (the DDC side of the port) |
| `portId` | 1, `bIsPortIdSet` = 1 |
| `regAddrSize` | 1 |
| `i2cSpeedKhz` | 4 (enum) |

Every transfer is one register byte followed by 1 to 7 data bytes (the
controller auto-increments). Vantage waits 10 ms after each transfer.

## Registers

| Reg | Meaning |
|---|---|
| `0x30` | write `b0`: begin frame |
| `0x15` | effect: `00` off, `01` static, `02` flicker, `03` breathing, `04` rainbow |
| `0x17` | brightness, percent (Vantage sends level × 25, levels 1-4) |
| `0x18 0x19 0x1a` | strip color R, G, B |
| `0x1b 0x1c 0x1d` | always `00 c8 ff` |
| `0x20`-`0x23` | timing for the animated effects (see below) |
| `0x31` | write `b1`: commit |
| `0x32` | write `b2`: apply |
| `0x50` | wordmark: `01` on, `00` off |

Effect ids other than these are reported to leave the controller in a fast
color cycle until a valid frame arrives (legion-gpu-rgb); never send them.

## Sequences (as Vantage sends them)

Notation: `reg <- bytes`, one transfer each.

Strip static / flicker / breathing:

```
30 <- b0
15 <- 01 | 02 | 03
17 <- BR R G B 00 c8 ff          BR = level * 25
20 <- T T                         flicker and breathing only, see table
31 <- b1
32 <- b2
```

`T T` for flicker and breathing is a 16-bit **big-endian** time in ms written
twice (4 bytes from `0x20`). Little-endian makes the controller read a period
of about a minute (verified):

| Speed | ms | bytes |
|---|---|---|
| 1 | 2000 | `07 d0 07 d0` |
| 2 | 1500 | `05 dc 05 dc` |
| 3 | 1000 | `03 e8 03 e8` |
| 4 | 500 | `01 f4 01 f4` |

Strip rainbow (no color, no brightness):

```
30 <- b0
15 <- 04
1b <- 00 c8 ff
20 <- 00 SS                       speed 1: f0, 2: cb, 3: a0, 4: 78
31 <- b1
32 <- b2
```

Strip off:

```
30 <- b0
15 <- 00
1b <- 00 c8 ff
31 <- b1
32 <- b2
```

Wordmark on / off:

```
30 <- b0
50 <- 01 | 00
1b <- 00 c8 ff
31 <- b1
32 <- b2
```

## On Linux

The NVIDIA driver registers the GPU's I2C ports as `/dev/i2c-N` adapters named
"NVIDIA i2c adapter 1" to "6". Which one is NvAPI's port 1 (DDC side) is still
to be found, with a single read at `0x49` per adapter. No kernel module is
needed: `i2c-dev` plus a udev rule for the user's access is enough.

Do not scan these buses: the DDC side also carries the monitor's EDID EEPROM at
`0x50`, which some monitors let you overwrite.
