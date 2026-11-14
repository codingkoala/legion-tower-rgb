# Adding a new model

The protocol in this project was mapped on a Legion T5 26ARA8. Other Legion
Towers very likely use the same ITE controller (`17ef:c955`) with different
zone IDs and effects, and other Lenovo OEM GeForce cards the same GPU
controller. Here is what is needed to add one. Nothing below writes to the
hardware.

## 1. Hardware facts (Linux)

```sh
legion-tower-rgb-cli report
```

It reads sysfs only: model, BIOS, the Lenovo/ITE HID devices with their HID
report descriptors, the GPUs with their PCI subsystem IDs. Paste the output in
the issue.

## 2. WMI lighting table (Windows)

The firmware lists every light in the WMI class `LENOVO_LIGHTING_INFO_LIST`:
zone IDs, panel grouping, supported effects (`mode` bit mask) and the command
bytes. In PowerShell:

```powershell
Get-CimInstance -Namespace root\WMI -ClassName LENOVO_LIGHTING_INFO_LIST | Format-List *
```

## 3. USB captures of Lenovo Vantage (Windows)

This is what pins down the exact packets.

1. Install [USBPcap](https://desowin.org/usbpcap/) and
   [Wireshark](https://www.wireshark.org/), reboot.
2. Open Vantage on the lighting page.
3. Start a capture in Wireshark on the USBPcap interface of the root hub
   (capturing everything is fine; other devices such as the mouse are filtered
   out later).
4. Change **one setting at a time**, waiting a couple of seconds between
   changes, and write down each change in order, for example:
   ```
   AMBIENT brightness 4, 3, 2, 1, 2, 3, 4
   AMBIENT effect off, static, flicker, breath
   CPU FAN speed 1, 2, 3, 4, 3, 2
   FRONT FANS color red, green, blue
   ```
   One capture per light (or per group of tests) keeps things readable. Going
   through every effect once on one fan is very useful.
5. Stop and save as `.pcapng`. In Wireshark, the lighting controller is the
   device whose descriptor shows `idVendor 0x17ef`, `idProduct 0xc955` (note its
   number, e.g. `2.4`).

You can check a capture yourself with the reader in this repository:

```sh
python3 tools/usbpcap_dump.py lights.pcapng 2 4 --reports
```

It prints every `SET_REPORT` / `GET_REPORT` of that device, grouped in bursts.

## 4. GPU lighting

GPU lighting does not go over USB, so USB captures do not show it. If your
card is a Lenovo OEM GeForce (`report` shows subsystem `17aa:…`), say so in
the issue with the effects Vantage or Legion Space offers for it; see
[GPU.md](GPU.md) for how it works.

## 5. First tests

Once a mapping is proposed, the first writes on a new model are done one at a
time, with known values only, and checked by eye.
