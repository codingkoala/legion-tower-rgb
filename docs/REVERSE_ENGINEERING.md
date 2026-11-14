# Reverse-engineering plan

Goal: learn the commands Lenovo Vantage sends, document them, and reimplement
them clean-room. Decompiled Lenovo code is never committed to this repository;
only protocol descriptions written in our own words.

## 1. Static analysis of Vantage (Windows binaries)

- Vantage is a Microsoft Store app plus the Lenovo System Interface Foundation /
  ImController service, which loads feature plugins. Lighting lives in one of them.
- Most plugins are .NET assemblies: decompile with ILSpy (or dnSpyEx). Look for
  the HID VID/PID `17EF`/`C955`, report ID `0xCC`, and WMI class or method names.
- Native DLLs (C/C++) go to Ghidra. Look for `HidD_SetFeature` / `HidD_GetFeature`
  calls and the buffers built before them.

## 2. Dynamic analysis on Windows

- USBPcap + Wireshark while changing every Vantage lighting setting one at a time:
  gives the exact `0xCC` packets, including zones not exposed by OpenRGB.
- WMI: WMI Explorer / `Get-CimClass -Namespace root\WMI` to list the Lenovo
  lighting classes and their methods.

## Prior art: Lenovo Legion Toolkit (GPL-3.0, laptops)

[LLT](https://github.com/LenovoLegionToolkit-Team/LenovoLegionToolkit) drives
simple lights (panel logo, rear ports, white keyboard) through two WMI classes
in `root\WMI`, which are good candidates for the tower's ambient strip and logo:

- `LENOVO_LIGHTING_DATA`: one row per light, with `Lighting_ID`,
  `Control_Interface`, `Lighting_Type`.
- `LENOVO_LIGHTING_METHOD`: `Get_Lighting_Current_Status(Lighting_ID)` returns
  `Current_State_Type`, `Current_Brightness_Level`;
  `Set_Lighting_Current_Status(Lighting_ID, Current_State_Type, Current_Brightness_Level)`.

LLT's laptop IDs (ID, interface, type): panel logo (3, 1, 0), rear ports
(5, 1, 0), white keyboard (0, 0, 1). The tower's IDs are unknown: listing
`LENOVO_LIGHTING_DATA` on Windows (read-only) answers that directly:

```powershell
Get-CimInstance -Namespace root\WMI -ClassName LENOVO_LIGHTING_DATA
Get-CimClass -Namespace root\WMI -ClassName LENOVO_LIGHTING_METHOD | Select-Object -Expand CimClassMethods
```

## 3. Cross-check on Linux (read-only)

- `sudo cat /sys/bus/wmi/devices/05901221-D566-11D1-B2F0-00A0C9062910/bmof` and
  decode with `bmf2mof`: WMI class and method names as the firmware declares them.
- `sudo acpidump`: the ACPI methods behind each WMI GUID.

## Legal note

EU Directive 2009/24/EC art. 6 (Italy: L. 633/1941 art. 64-quater) allows
decompilation when needed to obtain the information for interoperability with
an independently created program. Keep the analysis to that purpose and do not
redistribute Lenovo binaries or decompiled code.
