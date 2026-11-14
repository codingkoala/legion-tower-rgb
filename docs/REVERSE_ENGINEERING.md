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

## 3. Cross-check on Linux (read-only)

- `sudo cat /sys/bus/wmi/devices/05901221-D566-11D1-B2F0-00A0C9062910/bmof` and
  decode with `bmf2mof`: WMI class and method names as the firmware declares them.
- `sudo acpidump`: the ACPI methods behind each WMI GUID.

## Legal note

EU Directive 2009/24/EC art. 6 (Italy: L. 633/1941 art. 64-quater) allows
decompilation when needed to obtain the information for interoperability with
an independently created program. Keep the analysis to that purpose and do not
redistribute Lenovo binaries or decompiled code.
