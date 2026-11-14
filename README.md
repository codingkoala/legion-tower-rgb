# Legion Tower RGB

Control the fan and ambient lighting of Lenovo Legion Tower desktops on Linux,
the part Lenovo Vantage handles on Windows. Python, GTK4/libadwaita GUI and CLI.

> **Status: early development.** The protocol comes from USB captures of
> Lenovo Vantage on a Legion T5 26ARA8 and is only partly mapped. Every front end runs in
> **preview mode by default**: it shows the packets it would send and sends
> nothing until you explicitly enable hardware writes.

## Supported hardware

| Model | Controller | Zones |
|---|---|---|
| Legion T5 26ARA8 (MT 90UY) | ITE IT8297, USB `17ef:c955` | ambient, logo, 6 fans (CPU, rear, 2 front, 2 top) mapped; GPU not yet (not on this controller) |

## Install

```sh
sudo apt install python3-gi gir1.2-adw-1
pip install --user .
sudo ./install-udev.sh   # only needed for hardware writes
```

## Usage

```sh
legion-tower-rgb                                         # GUI
legion-tower-rgb-cli detect                              # reads sysfs only
legion-tower-rgb-cli set all breathing --color 00aaff    # dry run
legion-tower-rgb-cli set cpu-fan static --write          # really sends
```

## Documentation

- [Feasibility study](docs/FEASIBILITY.md)
- [Protocol notes](docs/PROTOCOL.md)
- [Reverse-engineering plan](docs/REVERSE_ENGINEERING.md)

## Credits

Early protocol hints from [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB)'s
`LenovoMotherboardController` (GPL-2.0-or-later). This project reimplements
them; no OpenRGB code is copied.

## License

GPL-3.0-or-later. Not affiliated with or endorsed by Lenovo.
