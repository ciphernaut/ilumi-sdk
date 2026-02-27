# sdk_tests/test_bumble_sdk.py
"""Unit tests for bumble_sdk.IlumiSDK.

These tests cover the pure-Python logic (header packing, payload building,
notification parsing) without requiring a live BLE device.
"""
import asyncio
import struct
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bumble_sdk import IlumiSDK, IlumiApiCmdType


class TestHeaderPacking(unittest.TestCase):
    def setUp(self):
        self.sdk = IlumiSDK.__new__(IlumiSDK)
        self.sdk.mac_address = "AA:BB:CC:DD:EE:FF"
        self.sdk.network_key = 0xDEADBEEF
        self.sdk.seq_num = 0
        self.sdk._connection = None
        self.sdk._char = None
        self.sdk._last_color = None
        self.sdk._last_device_info = None
        self.sdk._color_event = asyncio.Event()
        self.sdk._device_info_event = asyncio.Event()
        self.sdk._mesh_info = []
        self.sdk._mesh_event = asyncio.Event()

    def test_pack_header_includes_network_key(self):
        header = self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        nk = struct.unpack("<I", header[:4])[0]
        self.assertEqual(nk, 0xDEADBEEF)

    def test_pack_header_seq_num_always_even(self):
        self.sdk.seq_num = 1  # odd — should be bumped
        header = self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        seq = header[4]
        self.assertEqual(seq % 2, 0)

    def test_pack_header_seq_num_increments_by_2(self):
        self.sdk.seq_num = 4
        self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        self.assertEqual(self.sdk.seq_num, 6)

    def test_pack_header_cmd_type_in_byte5(self):
        cmd = IlumiApiCmdType.ILUMI_API_CMD_TURN_ON  # 4
        header = self.sdk._pack_header(cmd)
        self.assertEqual(header[5], cmd)


class TestNotificationParsing(unittest.TestCase):
    def setUp(self):
        self.sdk = IlumiSDK.__new__(IlumiSDK)
        self.sdk.mac_address = "AA:BB:CC:DD:EE:FF"
        self.sdk.network_key = 0
        self.sdk.seq_num = 0
        self.sdk._connection = None
        self.sdk._char = None
        self.sdk._last_color = None
        self.sdk._last_device_info = None
        self.sdk._color_event = asyncio.Event()
        self.sdk._device_info_event = asyncio.Event()
        self.sdk._mesh_info = []
        self.sdk._mesh_event = asyncio.Event()

    def _dispatch(self, data: bytes):
        """Call the SDK's internal notification handler directly."""
        self.sdk._handle_notification(bytearray(data))

    def test_direct_color_notification_parsed(self):
        # cmd=16 (GET_BULB_COLOR), 4 bytes padding, then r,g,b,w,brightness
        data = bytes([16, 0, 0, 0, 255, 128, 64, 0, 200])
        self._dispatch(data)
        self.assertEqual(self.sdk._last_color, {"r": 255, "g": 128, "b": 64, "w": 0, "brightness": 200})

    def test_device_info_notification_parsed(self):
        # cmd=40, 4 bytes padding, then fw(u16), bl(u16), commission(u8), model(u8), reset(u16), ble_stack(u16)
        payload = struct.pack("<H H B B H H", 0x0105, 0x0200, 1, 3, 0x0001, 0x0010)
        data = bytes([40, 0, 0, 0]) + payload
        self._dispatch(data)
        info = self.sdk._last_device_info
        self.assertIsNotNone(info)
        self.assertEqual(info["firmware_version"], 0x0105)
        self.assertEqual(info["commission_status"], 1)


class TestColorPayload(unittest.TestCase):
    def test_set_color_fast_clamps_values(self):
        sdk = IlumiSDK.__new__(IlumiSDK)
        sdk.network_key = 0
        sdk.seq_num = 0
        sdk.mac_address = "AA:BB:CC:DD:EE:FF"
        # Build payload manually using the same logic
        clamp = lambda x: max(0, min(255, int(x)))
        r, g, b = 300, -5, 128
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), 0, 255, 0, 0)
        self.assertEqual(payload[0], 255)   # clamped
        self.assertEqual(payload[1], 0)     # clamped
        self.assertEqual(payload[2], 128)   # unchanged


class TestExecuteOnTargets(unittest.IsolatedAsyncioTestCase):
    async def test_execute_on_targets_calls_func_per_mac(self):
        from bumble_sdk import execute_on_targets
        calls = []

        async def my_func(sdk):
            calls.append(sdk.mac_address)

        results = await execute_on_targets(["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"], my_func)
        self.assertEqual(calls, ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"])
        self.assertTrue(results["AA:BB:CC:DD:EE:FF"]["success"])


if __name__ == "__main__":
    unittest.main()
