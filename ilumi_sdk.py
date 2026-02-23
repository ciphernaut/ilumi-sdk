import asyncio
from bleak import BleakClient
import struct
import time
import config

ILUMI_SERVICE_UUID = "f000f0c0-0451-4000-b000-000000000000"
ILUMI_API_CHAR_UUID = "f000f0c1-0451-4000-b000-000000000000"

class IlumiApiCmdType:
    ILUMI_API_CMD_SET_COLOR = 0
    ILUMI_API_CMD_SET_DEAULT_COLOR = 1
    ILUMI_API_CMD_TURN_ON = 4
    ILUMI_API_CMD_TURN_OFF = 5
    ILUMI_API_CMD_SET_COLOR_PATTERN = 11  # CHECKED: line 12-1 is line 11? No, line 12 is index 7. Wait.
    # Re-evaluating indices based on line number in IlumiApiCmdType.java:
    # 5: 0
    # 12: 7 (PATTERN)
    # 13: 8 (START_PATTERN)
    # 33: 28 (PROXY_MSG)
    # 40: 35 (CANDLE)
    # 42: 37 (SMOOTH)
    # 45: 40 (DEVICE_INFO)
    # 57: 52 (DATA_CHUNK)
    # 63: 58 (COMMISSION)
    # 73: 68 (TREE_MESH_PROXY)
    
    ILUMI_API_CMD_SET_COLOR_PATTERN = 7
    ILUMI_API_CMD_SET_DAILY_ALARM = 9
    ILUMI_API_GET_BULB_COLOR = 16
    ILUMI_API_CMD_SET_CANDL_MODE = 35
    ILUMI_API_CMD_SET_COLOR_SMOOTH = 37
    ILUMI_API_CMD_GET_DEVICE_INFO = 40
    ILUMI_API_CMD_PROXY_MSG = 28
    ILUMI_API_CMD_TREE_MESH_PROXY = 68
    ILUMI_API_CMD_DATA_CHUNK = 52
    ILUMI_API_CMD_COMMISSION_WITH_ID = 58
    ILUMI_API_CMD_ADD_ACTION = 50
    ILUMI_API_CMD_SET_COLOR_NEED_RESP = 54
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
            if len(data) >= 2:
                cmd_type = data[0]
                
                if cmd_type == IlumiApiCmdType.ILUMI_API_CMD_PROXY_MSG:
                    if len(data) >= 10:
                        inner_len = struct.unpack("<H", data[8:10])[0]
                        if inner_len > 0:
                            inner_payload = data[10:10+inner_len]
                            inner_type = inner_payload[0]
                            if inner_type == IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR:
                                if len(inner_payload) >= 6:
                                    # R, G, B, W, Bri (after type byte)
                                    self._last_color = {
                                        "r": inner_payload[1],
                                        "g": inner_payload[2],
                                        "b": inner_payload[3],
                                        "w": inner_payload[4],
                                        "brightness": inner_payload[5]
                                    }
                                    self._color_event.set()
                
                elif cmd_type == IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO:
                    if len(data) >= 14: # 4 header + 10 data
                        try:
                            # Payload starts at data[4]
                            unpacked = struct.unpack("<H H B B H H", data[4:14])
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
                
                elif cmd_type == IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR:
                    if len(data) >= 9: # 4 header + 5 data
                        self._last_color = {
                            "r": data[4],
                            "g": data[5],
                            "b": data[6],
                            "w": data[7],
                            "brightness": data[8]
                        }
                        self._color_event.set()

            # print(f"Notification from {sender}: {data.hex()}")
        
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

    def _pack_header(self, message_type):
        """Common Ilumi SDK header: 4-byte network_key, 1-byte seq_num, 1-byte message type."""
        network_id_bytes = struct.pack("<I", self.network_key)
        
        # Ensure seq_num is even and wrap at 256
        if self.seq_num % 2 != 0:
            self.seq_num = (self.seq_num + 1) % 256
            
        header = network_id_bytes + struct.pack("B B", self.seq_num, message_type)
        
        # Increment seq_num for next command
        self.seq_num = (self.seq_num + 2) % 256
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

    async def send_proxy_message(self, target_macs, inner_payload):
        """Routes an inner API payload to a list of target MAC addresses via the mesh."""
        for target_mac in target_macs:
            mac_parts = [int(x, 16) for x in target_mac.split(':')]
            mac_parts.reverse() # Little-endian order for BLE
            mac_bytes = bytes(mac_parts)
            
            # Use standard PROXY format (28) - more reliable than tree mesh
            # Use TTL 47 for short payloads as seen in apiProxyByMAC
            service_type_ttl = 47 if len(inner_payload) <= 17 else 15
            addr_amount = 1
            # proxy_data_len = (addr_amount * 6) + len(inner_payload)
            proxy_data_len = 6 + len(inner_payload)
            
            proxy_cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_PROXY_MSG)
            proxy_header = struct.pack("<B B H", service_type_ttl, addr_amount, proxy_data_len)
            
            # Combine: [Outer Header (6)] + [Proxy Header (4)] + [MAC (6)] + [Inner Payload]
            final_payload = proxy_cmd + proxy_header + mac_bytes + inner_payload
                
            await self._send_chunked_command(final_payload)
            await asyncio.sleep(0.1) # Small delay between proxy commands
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

    async def turn_on(self, delay=0, transit=0, targets=None):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_ON)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def turn_off(self, delay=0, transit=0, targets=None):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_OFF)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color(self, r, g, b, w=0, brightness=255, targets=None):
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_smooth(self, r, g, b, w=0, brightness=255, duration_ms=500, delay_sec=0, targets=None):
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_SMOOTH)
        
        # Determine whether to use milliseconds or seconds. Max ms interval is ~65s.
        if duration_ms < 65535:
            time_val = int(duration_ms)
            time_unit = 0  # TIME_UNIT_MILLISECOND
        else:
            time_val = int(duration_ms / 1000)
            time_unit = 1  # TIME_UNIT_SECOND
            
        payload = struct.pack("<B B B B B B H B B", 
                              clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0,
                              time_val, time_unit, clamp(delay_sec))
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_fast(self, r, g, b, w=0, brightness=255, targets=None):
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command_fast(cmd + payload)

    async def set_candle_mode(self, r, g, b, w=0, brightness=255, targets=None):
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_CANDL_MODE)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_pattern(self, scene_idx, frames, repeatable=1, start_now=1):
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN)
        frame_bytes = bytearray()
        for f in frames:
            color = struct.pack("<B B B B B B", clamp(f.get('r', 0)), clamp(f.get('g', 0)), clamp(f.get('b', 0)), clamp(f.get('w', 0)), clamp(f.get('brightness', 255)), 0)
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

    async def get_bulb_color(self, targets=None):
        self._last_color = None
        self._color_event = asyncio.Event()
        header = self._pack_header(IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR)
        
        if targets:
            await self.send_proxy_message(targets, header)
        else:
            await self._send_command(header)
        
        try:
            await asyncio.wait_for(self._color_event.wait(), timeout=5.0)
            return self._last_color
        except asyncio.TimeoutError:
            print("Timeout waiting for color status.")
            return None

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
