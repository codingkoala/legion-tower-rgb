import unittest

from legion_tower_rgb import hidraw, protocol
from legion_tower_rgb.protocol import EFFECTS_BY_KEY, PANELS_BY_KEY, ZONES_BY_KEY, ZoneState

# Report descriptor read from /sys on a Legion T5 26ARA8 (17ef:c955).
T5_26ARA8_DESCRIPTOR = bytes.fromhex(
    "0689ff0910a101855a0901150026ff0075089510b100c0"
    "0689ff09cca10185cc0901150026ff007508953fb100c0")

# Meaningful bytes of the packets Lenovo Vantage sent in the first update of
# the capture (Vantage leaves stale memory after them; we send zeros instead).
VANTAGE_FIRST_UPDATE = [
    "cc1801020400d3fe", "cc1309020300d3fe", "cc1109020300d3fe", "cc1009020300d3fe",
    "cc1409020300d3fe", "cc1209020300d3fe", "cc1509020300d3fe", "cc1709020300d3fe",
    "cc2dffff00", "cc5e",
]


class DescriptorTest(unittest.TestCase):
    def test_feature_reports(self):
        self.assertEqual(hidraw.feature_reports(T5_26ARA8_DESCRIPTOR), {0x5A: 16, 0xCC: 63})

    def test_lighting_report_fits_packet(self):
        size = hidraw.feature_reports(T5_26ARA8_DESCRIPTOR)[protocol.REPORT_ID]
        self.assertEqual(size + 1, protocol.PACKET_LENGTH)


class PacketTest(unittest.TestCase):
    def test_matches_vantage_capture(self):
        packets = protocol.build_apply(protocol.vantage_default())
        self.assertEqual(len(packets), len(VANTAGE_FIRST_UPDATE))
        for packet, expected in zip(packets, VANTAGE_FIRST_UPDATE):
            head = bytes.fromhex(expected)
            self.assertEqual(len(packet), 64)
            self.assertEqual(packet[:len(head)], head)
            self.assertEqual(packet[len(head):], bytes(64 - len(head)))

    def test_ambient_breathing(self):
        p = protocol.build_zone(ZONES_BY_KEY["ambient"],
                                ZoneState(EFFECTS_BY_KEY["breathing"], 2, 4, (0, 0xD3, 0xFE)))
        self.assertEqual(p[:8].hex(), "cc1803020400d3fe")

    def test_meteor_cycle_matches_capture(self):
        # lights_fx capture: CPU fan meteor cycle, then back to rainbow.
        default = protocol.vantage_default()
        cycle = protocol.set_panel(default, PANELS_BY_KEY["cpu-fan"], effect=EFFECTS_BY_KEY["meteor-cycle"])
        heads = [p.rstrip(b"\x00").hex() for p in protocol.build_apply(cycle, default)]
        self.assertEqual(heads[1][:8], "cc130b02")
        self.assertEqual(heads[8:], ["cc41ff", "cc4201", "cc2dffff", "cc5e"])
        back = protocol.set_panel(cycle, PANELS_BY_KEY["cpu-fan"], effect=EFFECTS_BY_KEY["rainbow"])
        heads = [p.rstrip(b"\x00").hex() for p in protocol.build_apply(back, cycle)]
        self.assertEqual(heads[0], "cc42")
        self.assertEqual(heads[2][:8], "cc130902")
        self.assertEqual(heads[-2:], ["cc2dffff", "cc5e"])

    def test_sync_effect_spreads_except_ambient(self):
        states = protocol.set_panel(protocol.vantage_default(), PANELS_BY_KEY["cpu-fan"],
                                    effect=EFFECTS_BY_KEY["wave"])
        self.assertEqual(states["ambient"].effect.key, "static")
        self.assertTrue(all(states[z.key].effect.key == "wave" for z in protocol.ZONES if z.key != "ambient"))

    def test_ambient_has_basic_effects_only(self):
        with self.assertRaises(ValueError):
            protocol.set_panel(protocol.vantage_default(), PANELS_BY_KEY["ambient"], effect=EFFECTS_BY_KEY["wave"])

    def test_parse_read_reply(self):
        # Reply captured on the T5 26ARA8 after setting ambient static, brightness 1, ff0000.
        reply = bytes.fromhex(
            "cc0109000009020300d3fe09020300d3fe09020300d3fe09020300d3fe09020300d3fe"
            "09020300d3fe090104000000090203ff0000010201ff00000000000000")
        entries = protocol.parse_read(reply)
        self.assertEqual([e.zone_code for e in entries], list(range(0x10, 0x19)))
        states = protocol.states_from_read(entries, protocol.vantage_default())
        amb = states["ambient"]
        self.assertEqual((amb.effect.key, amb.speed, amb.brightness, amb.rgb), ("static", 2, 1, (0xFF, 0, 0)))
        self.assertEqual(states["logo"].rgb, (0xFF, 0, 0))
        self.assertEqual(states["cpu-fan"].effect.key, "rainbow")

    def test_read_keeps_cycle_variant_from_fallback(self):
        fallback = protocol.set_panel(protocol.vantage_default(), PANELS_BY_KEY["cpu-fan"],
                                      effect=EFFECTS_BY_KEY["meteor-cycle"])
        reply = bytearray(64)
        reply[:5] = bytes([0xCC, 0x01, 0x09, 0, 0])
        for i in range(9):
            reply[5 + i * 6:11 + i * 6] = bytes([0x09, 2, 3, 0, 0, 0])
        reply[5 + 3 * 6] = 0x0B  # zone 0x13 = CPU fan
        states = protocol.states_from_read(protocol.parse_read(bytes(reply)), fallback)
        self.assertEqual(states["cpu-fan"].effect.key, "meteor-cycle")

    def test_parse_read_rejects_stale_buffer(self):
        # What a GET_REPORT returns without a preceding read command.
        stale = bytes.fromhex("cc01cc03000040005a0901150026ff0075089510b100c00689ff09cca10185cc09")
        with self.assertRaises(ValueError):
            protocol.parse_read(stale)

    def test_requires_every_zone(self):
        states = protocol.vantage_default()
        del states["logo"]
        with self.assertRaises(ValueError):
            protocol.build_apply(states)

    def test_rejects_out_of_range(self):
        zone = ZONES_BY_KEY["cpu-fan"]
        with self.assertRaises(ValueError):
            protocol.build_zone(zone, ZoneState(EFFECTS_BY_KEY["static"], 5, 4, (0, 0, 0)))
        with self.assertRaises(ValueError):
            protocol.build_zone(zone, ZoneState(EFFECTS_BY_KEY["static"], 1, 0, (0, 0, 0)))

    def test_hidraw_ioctl_numbers(self):
        # Same values as the C macros for a 64-byte buffer.
        self.assertEqual(hidraw.HIDIOCSFEATURE(64), 0xC0404806)
        self.assertEqual(hidraw.HIDIOCGFEATURE(64), 0xC0404807)


if __name__ == "__main__":
    unittest.main()
