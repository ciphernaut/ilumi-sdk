import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import struct
import os

# Set environment variable to enable Bumble during import if needed
os.environ['ILUMI_USE_BUMBLE'] = '1'

import bumble_sdk
from bumble_sdk import IlumiSDK, IlumiApiCmdType, IlumiConnectionError

class TestBumbleSDK(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch Bumble dependencies
        self.mock_device = MagicMock()
        self.mock_peer = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_char = MagicMock()
        
        # Setup sdk instance
        self.mac = "AA:BB:CC:DD:EE:FF"
        self.sdk = IlumiSDK(self.mac)
        
        # Inject mocks
        self.sdk._device = self.mock_device
        self.sdk._peer = self.mock_peer
        self.sdk._connection = self.mock_connection
        self.sdk._char = self.mock_char
        self.sdk._api_char = self.mock_char
        
        # Reset sequence number for predictable tests
        self.sdk.seq_num = 0
        self.sdk.network_key = 0xDEADC0DE

    def test_pack_header(self):
        """Verify the 6-byte Ilumi header packing."""
        header = self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        self.assertEqual(len(header), 6)
        
        # Key (4 bytes) + Seq (1 byte) + Cmd (1 byte)
        # 0xDEADC0DE in little endian is DE C0 AD DE
        expected_start = struct.pack("<I", 0xDEADC0DE)
        self.assertEqual(header[:4], expected_start)
        self.assertEqual(header[4], 0) # Seq
        self.assertEqual(header[5], IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        
        # Verify seq num increment
        header2 = self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        self.assertEqual(header2[4], 2)

    async def test_write_direct(self):
        """Verify direct write to peer characterstic."""
        self.mock_peer.write_value = AsyncMock()
        payload = b"\x01\x02\x03"
        
        await self.sdk._write(payload, with_response=True)
        self.mock_peer.write_value.assert_called_once_with(self.mock_char, payload, with_response=True)

    async def test_chunked_command_short(self):
        """Payload <= 20 bytes should not be chunked."""
        self.mock_peer.write_value = AsyncMock()
        # Header (6) + payload (10) = 16 bytes
        payload = b"A" * 10
        cmd_payload = self.sdk._pack_header(1) + payload
        
        await self.sdk._send_chunked_command(cmd_payload)
        
        # Should only call write_value once
        self.assertEqual(self.mock_peer.write_value.call_count, 1)

    async def test_chunked_command_long(self):
        """Payload > 20 bytes must be split into DATA_CHUNK fragments."""
        self.mock_peer.write_value = AsyncMock()
        # Header (6) + payload (25) = 31 bytes
        # Should result in 4 calls (chunks of 10 bytes)
        raw_payload = b"B" * 25
        cmd_payload = self.sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_ON) + raw_payload
        
        # We need to patch sleep to speed up tests
        with patch('asyncio.sleep', AsyncMock()):
            await self.sdk._send_chunked_command(cmd_payload)
        
        # Total bytes 31. Data chunks are 10 bytes each.
        # Chunks: 0-10, 10-20, 20-30, 30-31
        self.assertEqual(self.mock_peer.write_value.call_count, 4)
        
        # Verify first chunk header has DATA_CHUNK command (52)
        args, kwargs = self.mock_peer.write_value.call_args_list[0]
        sent_payload = args[1]
        self.assertEqual(sent_payload[5], IlumiApiCmdType.ILUMI_API_CMD_DATA_CHUNK)

    def test_is_connected(self):
        """Verify the is_connected property reflects SDK state."""
        self.assertTrue(self.sdk.is_connected)
        
        self.sdk._connection = None
        self.assertFalse(self.sdk.is_connected)

    async def test_handle_disconnection(self):
        """State must be cleared upon disconnection."""
        self.sdk._handle_disconnection("Test reason")
        self.assertIsNone(self.sdk._connection)
        self.assertIsNone(self.sdk._peer)
        self.assertFalse(self.sdk.is_connected)

if __name__ == '__main__':
    unittest.main()
