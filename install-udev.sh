#!/bin/sh
# Installs the udev rule that gives the desktop user access to the lighting controller.
set -e
if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi
install -m 644 "$(dirname "$0")/udev/70-legion-tower-rgb.rules" /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw --subsystem-match=i2c-dev
echo "udev rule installed."
