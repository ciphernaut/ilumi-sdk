import asyncio
import struct
import time
import logging
import sys
from typing import List, Optional, Dict, Any, Callable
from bleak import BleakClient, BleakScanner
import config

# Configure logging to stderr to avoid corrupting stdout (used for JSON output)
logger = logging.getLogger("ilumi_sdk")
_handler = logging.StreamHandler(sys.stderr)
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_handler.setFormatter(_formatter)
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

ILUMI_SERVICE_UUID = "f000f0c0-0451-4000-b000-000000000000"
ILUMI_API_CHAR_UUID = "f000f0c1-0451-4000-b000-000000000000"

class IlumiConnectionError(Exception):
    """Raised when failing to connect to an Ilumi bulb."""
    pass

class IlumiProtocolError(Exception):
    """Raised when encountering unexpected data from the Ilumi protocol."""
    pass

class IlumiApiCmdType:
    """Mapping of Ilumi GATT API command IDs."""
    ILUMI_API_CMD_SET_COLOR = 0
    ILUMI_API_CMD_SET_DEAULT_COLOR = 1
    ILUMI_API_CMD_TURN_ON = 4
    ILUMI_API_CMD_TURN_OFF = 5
    ILUMI_API_CMD_SET_COLOR_PATTERN = 7
    ILUMI_API_CMD_SET_DAILY_ALARM = 9
    ILUMI_API_CMD_START_COLOR_PATTERN = 8 # Added from Java analysis
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
    """Mapping of commands within the ILUMI_API_CMD_CONFIG type."""
    ILUMI_CONFIG_ENTER_BOOTLOADER = 2

class IlumiSDK:
    """
    Main SDK class for interacting with Ilumi Smart Bulbs via BLE.
    Supports direct control, mesh proxying, and device management.
    """
    def __init__(self, mac_address: Optional[str] = None):
        """
        Initialize the SDK.
        :param mac_address: MAC address of the target bulb. If None, uses value from config.
        """
        self.mac_address = mac_address or config.get_config("mac_address")
        self.network_key = config.get_config("network_key", 0)
        self.seq_num = config.get_config("seq_num", 0)
        self.dfu_key = int(time.time()) & 0xFFFFFFFF
        self.client: Optional[BleakClient] = None
        self._last_device_info: Optional[Dict[str, Any]] = None
        self._last_color: Optional[Dict[str, int]] = None
        self._device_info_event = asyncio.Event()
        self._color_event = asyncio.Event()

    async def __aenter__(self):
        """Context manager to maintain a persistent connection."""
        if not self.mac_address:
            raise ValueError("No MAC address specified or enrolled.")
        
        self.client = BleakClient(self.mac_address, timeout=10.0)
        logger.info(f"Connecting to {self.mac_address}...")
        try:
            await self.client.connect()
        except Exception as e:
            raise IlumiConnectionError(f"Failed to connect to {self.mac_address}: {e}")
        
        def notification_handler(sender, data: bytearray):
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
                                    self._last_color = {
                                        "r": inner_payload[1],
                                        "g": inner_payload[2],
                                        "b": inner_payload[3],
                                        "w": inner_payload[4],
                                        "brightness": inner_payload[5]
                                    }
                                    self._color_event.set()
                
                elif cmd_type == IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO:
                    if len(data) >= 14:
                        try:
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
                            logger.error(f"Failed to parse device info: {e}")
                
                elif cmd_type == IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR:
                    if len(data) >= 9:
                        self._last_color = {
                            "r": data[4],
                            "g": data[5],
                            "b": data[6],
                            "w": data[7],
                            "brightness": data[8]
                        }
                        self._color_event.set()

        await self.client.start_notify(ILUMI_API_CHAR_UUID, notification_handler)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the persistent connection."""
        if self.client:
            logger.info(f"Closing connection to {self.mac_address}...")
            try:
                await self.client.stop_notify(ILUMI_API_CHAR_UUID)
                await self.client.disconnect()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            self.client = None

    @staticmethod
    async def discover(timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Scans for available Ilumi bulbs.
        :param timeout: How long to scan for.
        :return: List of discovered bulbs with name and address.
        """
        logger.info(f"Scanning for Ilumi bulbs ({timeout}s)...")
        devices = await BleakScanner.discover(timeout=timeout)
        ilumi_bulbs = []
        for d in devices:
            if d.name and ("ilumi" in d.name.lower() or d.name.startswith("L0")):
                ilumi_bulbs.append({"name": d.name, "address": d.address, "rssi": d.rssi})
        return ilumi_bulbs

    def _pack_header(self, message_type: int) -> bytes:
        """
        Packs the standard 6-byte Ilumi header.
        :param message_type: The IlumiApiCmdType ID.
        """
        network_id_bytes = struct.pack("<I", self.network_key)
        
        # Ensure seq_num is even as per protocol idiosyncrasy
        if self.seq_num % 2 != 0:
            self.seq_num = (self.seq_num + 1) % 256
            
        header = network_id_bytes + struct.pack("B B", self.seq_num, message_type)
        
        self.seq_num = (self.seq_num + 2) % 256
        config.update_config("seq_num", self.seq_num)
        
        return header

    async def _send_command(self, payload: bytes):
        """Sends a command with GATT write response expectation."""
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            await asyncio.sleep(0.1)
            return

        async with self as managed_sdk:
            await managed_sdk.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            await asyncio.sleep(0.5)

    async def _send_command_fast(self, payload: bytes):
        """Sends a command without waiting for GATT response (write command)."""
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=False)
            return

        async with self as managed_sdk:
            await managed_sdk.client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=False)

    async def _send_chunked_command(self, data: bytes):
        """Splits payloads > 20 bytes into 10-byte fragments for reliable BLE transfer."""
        data_length = len(data)
        if data_length <= 20:
            await self._send_command(data)
            return

        async def _do_send(target_client):
            for offset in range(0, data_length, 10):
                chunk_size = min(10, data_length - offset)
                chunk_payload = bytearray(10)
                chunk_payload[0:chunk_size] = data[offset:offset+chunk_size]
    
                chunk_struct = struct.pack("<H H 10s", data_length, offset, bytes(chunk_payload))
                cmd_header = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_DATA_CHUNK)
                logger.debug(f"Sending chunk {offset}/{data_length}")
                await target_client.write_gatt_char(ILUMI_API_CHAR_UUID, cmd_header + chunk_struct, response=True)
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.5)

        if self.client and self.client.is_connected:
            await _do_send(self.client)
        else:
            async with self as managed_sdk:
                await _do_send(managed_sdk.client)

    async def _send_raw_command(self, cmd_type: int, payload: bytes):
        """
        INTERNAL UNSAFE METHOD: Sends a raw command type and payload.
        > [!CAUTION]
        > **BRICKING RISK**: Sending invalid commands via CONFIG or COMMISSION types 
        > can permanently disable or lockout the bulb. Use with extreme caution.
        """
        header = self._pack_header(cmd_type)
        logger.warning(f"Sending RAW command type {cmd_type} with payload: {payload.hex()}")
        await self._send_chunked_command(header + payload)

    async def send_proxy_message(self, target_macs: List[str], inner_payload: bytes):
        """Routes an inner API payload to a list of target MAC addresses via the mesh."""
        for target_mac in target_macs:
            mac_parts = [int(x, 16) for x in target_mac.split(':')]
            mac_parts.reverse() 
            mac_bytes = bytes(mac_parts)
            
            service_type_ttl = 47 if len(inner_payload) <= 17 else 15
            addr_amount = 1
            proxy_data_len = 6 + len(inner_payload)
            
            proxy_cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_PROXY_MSG)
            proxy_header = struct.pack("<B B H", service_type_ttl, addr_amount, proxy_data_len)
            
            final_payload = proxy_cmd + proxy_header + mac_bytes + inner_payload
            await self._send_chunked_command(final_payload)
            await asyncio.sleep(0.1)

    async def commission(self, new_network_key: int, group_id: int, node_id: int) -> bool:
        """Assigns a network key and bulb ID. Returns success."""
        self.network_key = new_network_key
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_COMMISSION_WITH_ID)
        payload = struct.pack("<I H H", new_network_key, node_id, group_id)
        
        try:
            await self._send_command(cmd + payload)
            logger.info("Commissioning payload sent successfully.")
            config.update_config("network_key", new_network_key)
            config.update_config("group_id", group_id)
            config.update_config("node_id", node_id)
            return True
        except Exception as e:
            logger.error(f"Failed to commission: {e}")
            return False

    async def turn_on(self, delay: int = 0, transit: int = 0, targets: Optional[List[str]] = None):
        """Turns the bulb(s) on with optional fade (transit)."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_ON)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def turn_off(self, delay: int = 0, transit: int = 0, targets: Optional[List[str]] = None):
        """Turns the bulb(s) off with optional fade (transit)."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_OFF)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255, targets: Optional[List[str]] = None):
        """Sets an instant color. Clamp values to 0-255."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_smooth(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255, duration_ms: int = 500, delay_sec: int = 0, targets: Optional[List[str]] = None):
        """Fades to a color over a specific duration."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_SMOOTH)
        
        if duration_ms < 65535:
            time_val = int(duration_ms)
            time_unit = 0 
        else:
            time_val = int(duration_ms / 1000)
            time_unit = 1 
            
        payload = struct.pack("<H B B B B B B B B", 
                              time_val, time_unit,
                              clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0,
                              clamp(delay_sec))
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_fast(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255, targets: Optional[List[str]] = None):
        """Sets color without waiting for BLE acknowledgement."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command_fast(cmd + payload)

    async def set_candle_mode(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255, targets: Optional[List[str]] = None):
        """Activates flickering candle mode."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_CANDL_MODE)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_pattern(self, scene_idx: int, frames: List[Dict[str, int]], repeatable: int = 1, start_now: int = 1):
        """Uploads and triggers an animation pattern."""
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

    async def start_color_pattern(self, scene_idx: int):
        """Starts a previously uploaded animation scene."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_START_COLOR_PATTERN)
        payload = struct.pack("<B", scene_idx)
        await self._send_command(cmd + payload)

    async def get_bulb_color(self, targets: Optional[List[str]] = None) -> Optional[Dict[str, int]]:
        """Queries current bulb color status."""
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
            logger.error("Timeout waiting for color status.")
            return None

    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves hardware and firmware information."""
        self._device_info_event.clear()
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO)
        await self._send_command(cmd)
        
        try:
            await asyncio.wait_for(self._device_info_event.wait(), timeout=10.0)
            return self._last_device_info
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for device info.")
            return None

    async def enter_dfu_mode(self) -> None:
        """Triggers bootloader mode for firmware updates."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_CONFIG)
        payload = struct.pack("<B 4B", IlumiConfigCmdType.ILUMI_CONFIG_ENTER_BOOTLOADER, 
                              self.dfu_key & 0xFF, (self.dfu_key >> 8) & 0xFF, 
                              (self.dfu_key >> 16) & 0xFF, (self.dfu_key >> 24) & 0xFF)
        
        logger.info(f"Sending DFU mode entry command with key: {hex(self.dfu_key)}")
        await self._send_command(cmd + payload)

async def execute_on_targets(targets: List[str], coro_func: Callable) -> Dict[str, Any]:
    """Helper to execute an SDK task across multiple bulbs."""
    results = {}
    for mac in targets:
        sdk = IlumiSDK(mac)
        try:
            await coro_func(sdk)
            results[mac] = {"success": True, "error": None}
        except Exception as e:
            logger.error(f"[{mac}] Error: {e}")
            results[mac] = {"success": False, "error": str(e)}
    return results
