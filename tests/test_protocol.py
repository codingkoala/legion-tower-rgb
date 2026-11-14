import unittest

from legion_tower_rgb import hidraw, protocol
from legion_tower_rgb.protocol import EFFECTS_BY_KEY, ZONES_BY_KEY, ZoneState

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
