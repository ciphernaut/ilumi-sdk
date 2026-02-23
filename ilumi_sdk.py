import asyncio
from bleak import BleakClient
import struct
import time
import config

ILUMI_SERVICE_UUID = "f000f0c0-0451-4000-b000-000000000000"
ILUMI_API_CHAR_UUID = "f000f0c1-0451-4000-b000-000000000000"

class IlumiApiCmdType:
    ILUMI_API_CMD_SET_COLOR = 0
    ILUMI_API_CMD_TURN_ON = 4
    ILUMI_API_CMD_TURN_OFF = 5
    ILUMI_API_CMD_SET_COLOR_PATTERN = 7
    ILUMI_API_CMD_START_COLOR_PATTERN = 8
    ILUMI_API_CMD_ADD_ACTION = 50
    ILUMI_API_CMD_DATA_CHUNK = 52
    ILUMI_API_CMD_SET_COLOR_NEED_RESP = 54
    ILUMI_API_CMD_SET_CANDL_MODE = 35
    ILUMI_API_CMD_COMMISSION_WITH_ID = 58
    ILUMI_API_CMD_GET_DEVICE_INFO = 40
    ILUMI_API_CMD_CONFIG = 65

class IlumiConfigCmdType:
    ILUMI_CONFIG_ENTER_BOOTLOADER = 2

class IlumiSDK:
    def __init__(self, mac_address=None):
        self.mac_address = mac_address or config.get_config("mac_address")
        self.network_key = config.get_config("network_key", 0)
        self.seq_num = config.get_config("seq_num", 0)
        self.dfu_key = int(time.time()) & 0xFFFFFFFF  # Simple random-ish key
        self.client = None
        self._last_device_info = None
        self._device_info_event = asyncio.Event()

    async def __aenter__(self):
        """Context manager to maintain a persistent connection."""
        if not self.mac_address:
            raise ValueError("No MAC address specified or enrolled.")
        
        self.client = BleakClient(self.mac_address, timeout=10.0)
        print(f"Connecting to {self.mac_address}...")
        await self.client.connect()
        
        def notification_handler(sender, data):
            # Response Header is 4 bytes: [0: cmd, 1: status, 2:4: payload_size (LE)]
            if len(data) >= 4:
                cmd_type = data[0]
                status = data[1]
                payload_size = struct.unpack("<H", data[2:4])[0]
                payload = data[4:]
                
                if cmd_type == IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO:
                    if len(payload) >= 10:
                        try:
                            # <H H B B H H: firmware, bootloader, commission, model, reset, ble_stack
                            unpacked = struct.unpack("<H H B B H H", payload[:10])
                            self._last_device_info = {
                                "firmware_version": unpacked[0],
                                "bootloader_version": unpacked[1],
                                "commission_status": unpacked[2],
                                "model_number": unpacked[3],
                                "reset_reason": unpacked[4],
                                "ble_stack_version": unpacked[5]
                            }
                            self._device_info_event.set()
                        except Exception as e:
                            print(f"Failed to parse device info: {e}")

            print(f"Notification from {sender}: {data.hex()}")
        
        await self.client.start_notify(ILUMI_API_CHAR_UUID, notification_handler)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the persistent connection."""
        if self.client:
            print(f"Closing connection to {self.mac_address}...")
            try:
                await self.client.stop_notify(ILUMI_API_CHAR_UUID)
                await self.client.disconnect()
            except Exception as e:
                print(f"Error during disconnect: {e}")
            self.client = None

    def _pack_header(self, cmd_type):
        """
        Packs the 6-byte GATT header:
        - 4-byte network key (LE) [0:4]
        - 1-byte seq_num [4]
        - 1-byte cmd type [5]
        """
        header = struct.pack("<I B B", self.network_key, self.seq_num, cmd_type)
        self.seq_num = (self.seq_num + 2) & 0xFE
        config.update_config("seq_num", self.seq_num)
        return header

    async def _send_command(self, payload):
        """Sends a command using either the managed client or a temporary one."""
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            # Short sleep to let notifications arrive and avoid packet collision
            await asyncio.sleep(0.1)
            return

        # Fallback for simple scripts not using the context manager
        print(f"Opening temporary connection to {self.mac_address}...")
        async with self as managed_sdk:
            await managed_sdk.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            await asyncio.sleep(0.5)

    async def _send_command_fast(self, payload):
        """Sends a command without waiting for a BLE response (write command)."""
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=False)
            return

        # Fallback logic
        print(f"Opening temporary connection to {self.mac_address} for fast write...")
        async with self as managed_sdk:
            await managed_sdk.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=False)

        # Fallback for simple scripts not using the context manager
        print(f"Opening temporary connection to {self.mac_address}...")
        async with self as managed_sdk:
            await managed_sdk.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            await asyncio.sleep(0.5)

    async def _send_chunked_command(self, data: bytes):
        """
        Splits payloads > 20 bytes into 10-byte fragments using ILUMI_API_CMD_DATA_CHUNK.
        Reuses the active client if available.
        """
        data_length = len(data)
        if data_length <= 20:
            await self._send_command(data)
            return

        # Use an inner function to send chunks to avoid double context management if already managed
        async def _do_send(target_client):
            for offset in range(0, data_length, 10):
                chunk_size = min(10, data_length - offset)
                chunk_payload = bytearray(10)
                chunk_payload[0:chunk_size] = data[offset:offset+chunk_size]
    
                chunk_struct = struct.pack("<H H 10s", data_length, offset, bytes(chunk_payload))
                cmd_header = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_DATA_CHUNK)
                
                print(f"Sending chunk {offset}/{data_length}")
                await target_client.write_gatt_char(ILUMI_API_CHAR_UUID, cmd_header + chunk_struct, response=True)
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.5)

        if self.client and self.client.is_connected:
            await _do_send(self.client)
        else:
            print(f"Opening managed connection for chunked upload...")
            async with self as managed_sdk:
                await _do_send(managed_sdk.client)

    async def commission(self, new_network_key, group_id, node_id):
        self.network_key = new_network_key
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_COMMISSION_WITH_ID)
        payload = struct.pack("<I H H", new_network_key, node_id, group_id)
        
        try:
            await self._send_command(cmd + payload)
            print("Commissioning payload sent successfully.")
            config.update_config("network_key", new_network_key)
            config.update_config("group_id", group_id)
            config.update_config("node_id", node_id)
            return True
        except Exception as e:
            print(f"Failed to commission: {e}")
            return False

    async def turn_on(self, delay=0, transit=0):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_ON)
        payload = struct.pack("<H H", delay, transit)
        await self._send_command(cmd + payload)

    async def turn_off(self, delay=0, transit=0):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_OFF)
        payload = struct.pack("<H H", delay, transit)
        await self._send_command(cmd + payload)

    async def set_color(self, r, g, b, w=0, brightness=255):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
        payload = struct.pack("<B B B B B B B", r, g, b, w, brightness, 0, 0)
        await self._send_command(cmd + payload)

    async def set_color_fast(self, r, g, b, w=0, brightness=255):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        payload = struct.pack("<B B B B B B B", r, g, b, w, brightness, 0, 0)
        await self._send_command_fast(cmd + payload)

    async def set_candle_mode(self, r, g, b, w=0, brightness=255):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_CANDL_MODE)
        payload = struct.pack("<B B B B B B B", r, g, b, w, brightness, 0, 0)
        await self._send_command(cmd + payload)

    async def set_color_pattern(self, scene_idx, frames, repeatable=1, start_now=1):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN)
        frame_bytes = bytearray()
        for f in frames:
            color = struct.pack("<B B B B B B", f.get('r', 0), f.get('g', 0), f.get('b', 0), f.get('w', 0), f.get('brightness', 255), 0)
            timings = struct.pack("<I I B B B B", f.get('sustain_ms', 500), f.get('transit_ms', 100), 0, 0, 0, 0)
            frame_bytes.extend(color + timings)

        total_struct_size = 13 + len(frame_bytes) 
        array_size = len(frames)
        scene_header = struct.pack("<H B B B B B", total_struct_size, scene_idx, array_size, repeatable, scene_idx, start_now)
        full_payload = cmd + scene_header + frame_bytes
        await self._send_chunked_command(full_payload)

    async def start_color_pattern(self, scene_idx):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_START_COLOR_PATTERN)
        payload = struct.pack("<B", scene_idx)
        await self._send_command(cmd + payload)

    async def get_device_info(self):
        """Triggers and waits for a GET_DEVICE_INFO response."""
        self._device_info_event.clear()
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO)
        # Empty payload for get device info
        await self._send_command(cmd)
        
        try:
            # Wait up to 5 seconds for the response
            await asyncio.wait_for(self._device_info_event.wait(), timeout=5.0)
            return self._last_device_info
        except asyncio.TimeoutError:
            print("Timed out waiting for device info.")
            return None

    async def enter_dfu_mode(self):
        """Puts the device into Nordic DFU bootloader mode."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_CONFIG)
        # IlumiPacking.enterDFUMode(int dfuKey)
        # msgPayload.cmd_type.set(ILUMI_CONFIG_ENTER_BOOTLOADER)
        # msgPayload.parameter[0-3].set(dfuKey)
        payload = struct.pack("<B 4B", IlumiConfigCmdType.ILUMI_CONFIG_ENTER_BOOTLOADER, 
                              self.dfu_key & 0xFF, (self.dfu_key >> 8) & 0xFF, 
                              (self.dfu_key >> 16) & 0xFF, (self.dfu_key >> 24) & 0xFF)
        
        print(f"Sending DFU mode entry command with key: {hex(self.dfu_key)}")
        await self._send_command(cmd + payload)
        print("Device should be rebooting into DFU mode...")

async def execute_on_targets(targets, coro_func):
    """
    Executes a given asynchronous function sequentially across all target MAC addresses.
    Returns a dictionary mapping MAC address to an execution result object:
    { "AA:BB:..": {"success": True/False, "error": "Optional error string"} }
    """
    results = {}
    for mac in targets:
        sdk = IlumiSDK(mac)
        try:
            await coro_func(sdk)
            results[mac] = {"success": True, "error": None}
        except Exception as e:
            print(f"[{mac}] Error: {e}")
            results[mac] = {"success": False, "error": str(e)}
            
    return results
