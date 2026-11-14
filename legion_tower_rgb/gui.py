"""GTK4 / libadwaita front end.

Starts in preview mode: Apply only shows the packets. Sending them to the
hardware needs the "Hardware writes" switch, which asks for confirmation.
"""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from . import device, protocol  # noqa: E402

APP_ID = "io.github.codingkoala.LegionTowerRGB"


class ZoneGroup(Adw.PreferencesGroup):
    def __init__(self, zone: protocol.Zone):
        super().__init__(title=protocol.ZONE_TITLES[zone])
        self.zone = zone

        self.effect_row = Adw.ComboRow(title="Effect",
                                       model=Gtk.StringList.new([e.title for e in protocol.EFFECTS]))
        self.effect_row.connect("notify::selected", lambda *_: self._sync_sensitivity())
        self.add(self.effect_row)

        self.color_button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False),
                                                  valign=Gtk.Align.CENTER)
        red = Gdk.RGBA()
        red.parse("#ff0000")
        self.color_button.set_rgba(red)
        self.color_row = Adw.ActionRow(title="Color")
        self.color_row.add_suffix(self.color_button)
        self.add(self.color_row)

        self.speed_row, self.speed = self._scale_row("Speed", protocol.SPEED_RANGE, protocol.SPEED_RANGE[0])
        _row, self.brightness = self._scale_row("Brightness", protocol.BRIGHTNESS_RANGE,
                                                protocol.BRIGHTNESS_RANGE[1])
        self._sync_sensitivity()

    def _scale_row(self, title: str, bounds: tuple[int, int], value: int) -> tuple[Adw.ActionRow, Gtk.Scale]:
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, bounds[0], bounds[1], 1)
        scale.set_value(value)
        scale.set_digits(0)
        scale.set_draw_value(True)
        scale.set_hexpand(True)
        for mark in range(bounds[0], bounds[1] + 1):
            scale.add_mark(mark, Gtk.PositionType.BOTTOM, None)
        row = Adw.ActionRow(title=title)
        row.add_suffix(scale)
        scale.set_size_request(220, -1)
        self.add(row)
        return row, scale

    @property
    def effect(self) -> protocol.Effect:
        return protocol.EFFECTS[self.effect_row.get_selected()]

    def _sync_sensitivity(self) -> None:
        self.color_row.set_sensitive(self.effect.uses_color)
        self.speed_row.set_sensitive(self.effect.uses_speed)

    @property
    def rgb(self) -> tuple[int, int, int]:
        c = self.color_button.get_rgba()
        return tuple(round(v * 255) for v in (c.red, c.green, c.blue))  # type: ignore[return-value]


class Window(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Legion Tower RGB", default_width=560, default_height=760)
        self.toasts = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)

        page = Adw.PreferencesPage()
        toolbar.set_content(page)

        status = Adw.PreferencesGroup(title="Controller")
        self.status_row = Adw.ActionRow()
        status.add(self.status_row)
        self.write_switch = Adw.SwitchRow(
            title="Hardware writes",
            subtitle="Off: Apply only shows the packets. The protocol is not yet verified on every model.")
        self.write_switch.connect("notify::active", self._on_write_toggled)
        status.add(self.write_switch)
        page.add(status)

        self.zones = [ZoneGroup(z) for z in protocol.Zone]
        for g in self.zones:
            page.add(g)

        preview = Adw.PreferencesGroup(title="Packets")
        self.preview = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["monospace", "dim-label"])
        preview.add(self.preview)
        apply = Gtk.Button(label="Apply", css_classes=["suggested-action", "pill"],
                           halign=Gtk.Align.CENTER, margin_top=12)
        apply.connect("clicked", self._on_apply)
        preview.add(apply)
        page.add(preview)

        self._refresh_status()

    def _refresh_status(self) -> None:
        found = device.find_controllers()
        if found:
            self.status_row.set_title(found[0].info.name)
            self.status_row.set_subtitle(f"{found[0].info.path} · 17ef:c955")
        else:
            self.status_row.set_title("Controller not found")
            self.status_row.set_subtitle("Preview mode only")
            self.write_switch.set_sensitive(False)

    def _on_write_toggled(self, row, _pspec) -> None:
        if not row.get_active():
            return
        dialog = Adw.AlertDialog(
            heading="Enable hardware writes?",
            body="Lighting commands will be sent to the controller. The protocol comes from "
                 "OpenRGB and has not been verified on every Legion Tower model.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("enable", "Enable")
        dialog.set_response_appearance("enable", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda _d, r: r == "enable" or row.set_active(False))
        dialog.present(self)

    def _on_apply(self, _button) -> None:
        write = self.write_switch.get_active()
        lines = []
        try:
            for g in self.zones:
                packets = device.set_mode(g.zone, g.effect, int(g.speed.get_value()),
                                          int(g.brightness.get_value()), g.rgb, allow_write=write)
                lines += [f"{protocol.ZONE_TITLES[g.zone]}: {protocol.hexdump(p)}" for p in packets]
        except (device.DeviceError, ValueError) as exc:
            self.toasts.add_toast(Adw.Toast(title=str(exc)))
            return
        self.preview.set_label("\n".join(lines))
        self.toasts.add_toast(Adw.Toast(title="Sent to the controller" if write else "Preview only: nothing sent"))


def main() -> int:
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
