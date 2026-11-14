# Feasibility study

Done 2026-11-14 on a Legion T5 26ARA8 (MT 90UY, board 3768, BIOS O5SKT33A,
Ubuntu 26.04, kernel 7.0, Secure Boot on with kernel lockdown). Read-only:
nothing was written to the hardware.

## Findings

- **Lighting controller:** USB HID `17ef:c955`, "ITE Tech. Inc. ITE Device(8297)",
  vendor usage page `0xFF89`. Its report descriptor declares two feature reports:
  `0x5A` (16 bytes) and `0xCC` (63 bytes).
- **OpenRGB** has `LenovoMotherboardController` for exactly this VID/PID and usage
  page: report `0xCC`, two single-color zones (CPU fan `0x12`, rear fan `0x11`),
  seven effects, speed and brightness 1-4. It never reads state and ignores `0x5A`.
- **WMI:** about 20 Lenovo WMI GUIDs, most without a Linux driver. On the sibling
  T5 28IMB05 the logo and strip zones are reported to go through WMI
  ([OpenRGB #2999](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2999)).
- **Secure Boot lockdown** blocks `acpi_call`-style experiments; a WMI driver would
  need a signed module or upstreaming.

## Assessment

| Part | Feasibility | Risk |
|---|---|---|
| Fans (ITE over USB HID) | high | low: plain feature reports, no firmware update path used |
| Reading state / report `0x5A` | medium | very low |
| Front fans and logo | medium | low: possibly more zones on the same controller |
| Ambient strip (WMI) | medium-low | medium: Lenovo WMI also drives fans and power |

## Rules for experiments

1. No command is sent unless its meaning is known (from OpenRGB, Vantage analysis
   or captures). No fuzzing.
2. Every first write on new hardware needs the owner's explicit approval.
3. WMI methods are only called after their arguments are understood from the MOF/ACPI.
