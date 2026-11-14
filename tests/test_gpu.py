import unittest

from legion_tower_rgb import gpu


def frames(transfers):
    return [f"{reg:02x}:{data.hex()}" for reg, data in transfers]


class GpuSequenceTest(unittest.TestCase):
    # Each expected sequence was sent from Linux and checked by eye on a
    # Lenovo OEM RTX 4070 SUPER (17aa:e138).

    def test_wordmark(self):
        self.assertEqual(frames(gpu.build_wordmark(False)), ["30:b0", "50:00", "1b:00c8ff", "31:b1", "32:b2"])
        self.assertEqual(frames(gpu.build_wordmark(True))[1], "50:01")

    def test_static_red(self):
        s = gpu.GpuState(gpu.EFFECTS_BY_KEY["static"], 2, 4, (255, 0, 0), True)
        self.assertEqual(frames(gpu.build_strip(s)), ["30:b0", "15:01", "17:64ff000000c8ff", "31:b1", "32:b2"])

    def test_breathing_timing_is_big_endian(self):
        s = gpu.GpuState(gpu.EFFECTS_BY_KEY["breathing"], 4, 4, (0, 0, 255), True)
        self.assertEqual(frames(gpu.build_strip(s))[3], "20:01f401f4")  # 500 ms
        s.speed = 1
        self.assertEqual(frames(gpu.build_strip(s))[3], "20:07d007d0")  # 2000 ms

    def test_rainbow(self):
        s = gpu.GpuState(gpu.EFFECTS_BY_KEY["rainbow"], 2, 4, (0, 0, 0), True)
        self.assertEqual(frames(gpu.build_strip(s)), ["30:b0", "15:04", "1b:00c8ff", "20:00cb", "31:b1", "32:b2"])
        s.speed = 4
        self.assertEqual(frames(gpu.build_strip(s))[3], "20:0078")

    def test_off(self):
        s = gpu.GpuState(gpu.EFFECTS_BY_KEY["off"], 2, 4, (0, 0, 0), True)
        self.assertEqual(frames(gpu.build_strip(s)), ["30:b0", "15:00", "1b:00c8ff", "31:b1", "32:b2"])


if __name__ == "__main__":
    unittest.main()
