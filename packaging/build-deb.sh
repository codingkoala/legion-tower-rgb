#!/bin/sh
# Builds dist/legion-tower-rgb_<version>_all.deb with dpkg-deb only.
# The package installs the udev rule, so no separate install-udev.sh step.
set -e
umask 022
cd "$(dirname "$0")/.."
VERSION=$(python3 -c 'import legion_tower_rgb; print(legion_tower_rgb.__version__)')
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
chmod 755 "$ROOT"

install -d "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/python3/dist-packages/legion_tower_rgb" \
    "$ROOT/usr/lib/udev/rules.d" "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/doc/legion-tower-rgb"
install -m 644 legion_tower_rgb/*.py "$ROOT/usr/lib/python3/dist-packages/legion_tower_rgb/"
install -m 644 udev/70-legion-tower-rgb.rules "$ROOT/usr/lib/udev/rules.d/"
install -m 644 data/io.github.codingkoala.LegionTowerRGB.desktop "$ROOT/usr/share/applications/"
install -m 644 README.md "$ROOT/usr/share/doc/legion-tower-rgb/"
install -m 644 LICENSE "$ROOT/usr/share/doc/legion-tower-rgb/copyright"

cat > "$ROOT/usr/bin/legion-tower-rgb" <<'SH'
#!/usr/bin/python3
import sys
from legion_tower_rgb.gui import main
sys.exit(main())
SH
cat > "$ROOT/usr/bin/legion-tower-rgb-cli" <<'SH'
#!/usr/bin/python3
import sys
from legion_tower_rgb.cli import main
sys.exit(main())
SH
chmod 755 "$ROOT/usr/bin/legion-tower-rgb" "$ROOT/usr/bin/legion-tower-rgb-cli"

cat > "$ROOT/DEBIAN/control" <<CTRL
Package: legion-tower-rgb
Version: $VERSION
Architecture: all
Maintainer: wizy_1337 <908299+codingkoala@users.noreply.github.com>
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1
Section: utils
Priority: optional
Homepage: https://github.com/codingkoala/legion-tower-rgb
Description: RGB lighting control for Lenovo Legion Tower desktops
 Controls the fan, ambient, logo and GPU lighting of Lenovo Legion Tower
 desktops (ITE 17ef:c955 controller and Lenovo OEM GeForce cards), the part
 Lenovo Vantage handles on Windows. GTK4/libadwaita GUI and CLI.
CTRL

for script in postinst postrm; do
cat > "$ROOT/DEBIAN/$script" <<'SH'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=hidraw --subsystem-match=i2c-dev || true
fi
SH
chmod 755 "$ROOT/DEBIAN/$script"
done

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "dist/legion-tower-rgb_${VERSION}_all.deb"
