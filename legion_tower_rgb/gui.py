"""GTK4 / libadwaita front end.

Starts in preview mode: Apply only shows the packets. Sending them to the
hardware needs the "Hardware writes" switch, which asks for confirmation.
One group per light as Vantage shows it (front and top fans are two zones each).
"""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from . import config, device, protocol  # noqa: E402
from .preview import CasePreview  # noqa: E402

APP_ID = "io.github.codingkoala.LegionTowerRGB"


class PanelGroup(Adw.PreferencesGroup):
    def __init__(self, panel: protocol.Panel, state: protocol.ZoneState, on_change):
        super().__init__(title=panel.title)
        self.panel = panel
        self.effects = protocol.effects_for(panel)

        self.effect_row = Adw.ComboRow(title="Effect",
                                       model=Gtk.StringList.new([e.title for e in self.effects]))
        if state.effect in self.effects:
            self.effect_row.set_selected(self.effects.index(state.effect))
        self.effect_row.connect("notify::selected", lambda *_: (self._sync_sensitivity(), on_change()))
        self.add(self.effect_row)

        self.color_button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False),
                                                  valign=Gtk.Align.CENTER)
        color = Gdk.RGBA()
        color.parse("#%02x%02x%02x" % state.rgb)
        self.color_button.set_rgba(color)
        self.color_button.connect("notify::rgba", lambda *_: on_change())
        self.color_row = Adw.ActionRow(title="Color")
        self.color_row.add_suffix(self.color_button)
        self.color_row.set_visible(panel.has_color)
        self.add(self.color_row)

        self.speed_row, self.speed = self._scale_row("Speed", protocol.SPEED_RANGE, state.speed)
        _row, self.brightness = self._scale_row("Brightness", protocol.BRIGHTNESS_RANGE, state.brightness)
        for scale in (self.speed, self.brightness):
            scale.connect("value-changed", lambda *_: on_change())
        self._sync_sensitivity()

    def _scale_row(self, title: str, bounds: tuple[int, int], value: int) -> tuple[Adw.ActionRow, Gtk.Scale]:
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, bounds[0], bounds[1], 1)
        scale.set_value(value)
        scale.set_digits(0)
        scale.set_draw_value(True)
        scale.set_hexpand(True)
        scale.set_size_request(220, -1)
        for mark in range(bounds[0], bounds[1] + 1):
            scale.add_mark(mark, Gtk.PositionType.BOTTOM, None)
        row = Adw.ActionRow(title=title)
        row.add_suffix(scale)
        self.add(row)
        return row, scale

    @property
    def effect(self) -> protocol.Effect:
        return self.effects[self.effect_row.get_selected()]

    def _sync_sensitivity(self) -> None:
        self.color_row.set_sensitive(self.effect.uses_color)
        self.speed_row.set_sensitive(self.effect.uses_speed)

    @property
    def rgb(self) -> tuple[int, int, int]:
        c = self.color_button.get_rgba()
        return tuple(round(v * 255) for v in (c.red, c.green, c.blue))  # type: ignore[return-value]

    def apply_to(self, states: dict[str, protocol.ZoneState]) -> dict[str, protocol.ZoneState]:
        return protocol.set_panel(states, self.panel, effect=self.effect, speed=int(self.speed.get_value()),
                                  brightness=int(self.brightness.get_value()), rgb=self.rgb)


class Window(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Legion Tower RGB", default_width=1100, default_height=820)
        self.toasts = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)

        # Left: controller, case preview, Apply. Right: one group per light.
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toolbar.set_content(columns)
        page = Adw.PreferencesPage()
        page.set_size_request(440, -1)
        zones_page = Adw.PreferencesPage(hexpand=True)
        columns.append(page)
        columns.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        columns.append(zones_page)

        status = Adw.PreferencesGroup(title="Controller")
        self.status_row = Adw.ActionRow()
        status.add(self.status_row)
        self.write_switch = Adw.SwitchRow(
            title="Hardware writes",
            subtitle="Off: Apply only shows the packets.")
        self.write_switch.connect("notify::active", self._on_write_toggled)
        status.add(self.write_switch)
        page.add(status)

        self.states, self.state_source = device.current_state()
        preview_group = Adw.PreferencesGroup(title="Preview",
                                             description="Approximation of the chosen settings")
        self.case = CasePreview()
        preview_group.add(self.case)
        page.add(preview_group)

        apply = Gtk.Button(label="Apply", css_classes=["suggested-action", "pill"],
                           halign=Gtk.Align.CENTER, margin_top=12)
        apply.connect("clicked", self._on_apply)
        preview_group.add(apply)

        self.groups = [PanelGroup(p, self.states[p.zones[0]], self._on_controls_changed)
                       for p in protocol.PANELS]
        for g in self.groups:
            zones_page.add(g)

        preview = Adw.PreferencesGroup(title="Packets")
        self.preview = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["monospace", "dim-label"])
        preview.add(self.preview)
        page.add(preview)

        self._refresh_status()
        self._on_controls_changed()

    def _states_from_controls(self) -> dict[str, protocol.ZoneState]:
        states = dict(self.states)
        # Sync effects (wave, spectrum) spread to every zone: apply them last
        # so the other groups do not overwrite them.
        for g in sorted(self.groups, key=lambda g: g.effect.sync):
            states = g.apply_to(states)
        return states

    def _on_controls_changed(self) -> None:
        if not hasattr(self, "groups") or len(self.groups) < len(protocol.PANELS):
            return  # still building the window
        try:
            self.case.set_states(self._states_from_controls())
        except ValueError:
            pass

    def _refresh_status(self) -> None:
        found = device.find_controllers()
        if found:
            self.status_row.set_title(found[0].info.name)
            source = "state read from the controller" if self.state_source == "device" else "last saved state"
            self.status_row.set_subtitle(f"{found[0].info.path} · 17ef:c955 · {source}")
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
                 "USB captures of Lenovo Vantage on a Legion T5 26ARA8.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("enable", "Enable")
        dialog.set_response_appearance("enable", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda _d, r: r == "enable" or row.set_active(False))
        dialog.present(self)

    def _on_apply(self, _button) -> None:
        write = self.write_switch.get_active()
        try:
            states = self._states_from_controls()
            packets = device.apply(states, previous=self.states, allow_write=write)
        except (device.DeviceError, ValueError) as exc:
            self.toasts.add_toast(Adw.Toast(title=str(exc)))
            return
        if write:
            config.save_state(states)
            self.states = states
        self.preview.set_label("\n".join(protocol.hexdump(p) for p in packets))
        self.toasts.add_toast(Adw.Toast(title="Sent to the controller" if write else "Preview only: nothing sent"))


def main() -> int:
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
