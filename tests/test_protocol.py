import unittest

from legion_tower_rgb import hidraw, protocol

# Report descriptor read from /sys on a Legion T5 26ARA8 (17ef:c955).
T5_26ARA8_DESCRIPTOR = bytes.fromhex(
    "0689ff0910a101855a0901150026ff0075089510b100c0"
    "0689ff09cca10185cc0901150026ff007508953fb100c0")


class DescriptorTest(unittest.TestCase):
    def test_feature_reports(self):
        self.assertEqual(hidraw.feature_reports(T5_26ARA8_DESCRIPTOR), {0x5A: 16, 0xCC: 63})

    def test_lighting_report_fits_packet(self):
        size = hidraw.feature_reports(T5_26ARA8_DESCRIPTOR)[protocol.REPORT_ID]
        self.assertEqual(size + 1, protocol.PACKET_LENGTH)


class PacketTest(unittest.TestCase):
    def test_static_red_cpu_fan(self):
        first, second = protocol.build_set_mode(
            protocol.Zone.CPU_FAN, protocol.EFFECTS_BY_KEY["static"], 1, 4, (255, 0, 0))
        self.assertEqual(len(first), 64)
        self.assertEqual(len(second), 64)
        self.assertEqual(first[:8], bytes([0xCC, 0x12, 0x01, 1, 4, 255, 0, 0]))
        self.assertEqual(first[8:], bytes(56))
        self.assertEqual(second[:3], bytes([0xCC, 0x28, 0x06]))
        self.assertEqual(second[3:33], bytes(30))
        self.assertEqual(second[33:40], bytes([0x12, 0x01, 1, 4, 255, 0, 0]))

    def test_rejects_out_of_range(self):
        static = protocol.EFFECTS_BY_KEY["static"]
        with self.assertRaises(ValueError):
            protocol.build_set_mode(protocol.Zone.REAR_FAN, static, 5, 4, (0, 0, 0))
        with self.assertRaises(ValueError):
            protocol.build_set_mode(protocol.Zone.REAR_FAN, static, 1, 0, (0, 0, 0))

    def test_hidraw_ioctl_numbers(self):
        # Same values as the C macros for a 64-byte buffer.
        self.assertEqual(hidraw.HIDIOCSFEATURE(64), 0xC0404806)
        self.assertEqual(hidraw.HIDIOCGFEATURE(64), 0xC0404807)


if __name__ == "__main__":
    unittest.main()
