"""
bumble_sdk.py — Ilumi BLE SDK backed by Google Bumble (direct HCI).

Drop-in replacement for ilumi_sdk.IlumiSDK.
Requires a dedicated Bluetooth adapter accessible via Bumble transport.
Set ILUMI_BT_TRANSPORT env var (e.g. "usb:0") or pass transport= to IlumiSDK().
"""

import asyncio
import os
import struct
import logging
import sys
from typing import List, Optional, Dict, Any

from bumble.device import Device, Peer
from bumble.transport import open_transport
import config

logger = logging.getLogger("bumble_sdk")
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

ILUMI_SERVICE_UUID    = "f000f0c0-0451-4000-b000-000000000000"
ILUMI_API_CHAR_UUID   = "f000f0c1-0451-4000-b000-000000000000"

# Shared per-process device — all IlumiSDK instances share one HCI adapter
_shared_device: Optional[Device] = None
_shared_transport = None
_device_lock = asyncio.Lock()


class IlumiConnectionError(Exception):
    pass


class IlumiProtocolError(Exception):
    pass


class IlumiApiCmdType:
    ILUMI_API_CMD_SET_COLOR         = 0
    ILUMI_API_CMD_SET_DEAULT_COLOR  = 1
    ILUMI_API_CMD_TURN_ON           = 4
    ILUMI_API_CMD_TURN_OFF          = 5
    ILUMI_API_CMD_SET_COLOR_PATTERN = 7
    ILUMI_API_CMD_START_COLOR_PATTERN = 8
    ILUMI_API_CMD_SET_DAILY_ALARM   = 9
    ILUMI_API_GET_BULB_COLOR        = 16
    ILUMI_API_CMD_PROXY_MSG         = 28
    ILUMI_API_CMD_QUERY_ROUTING     = 31
    ILUMI_API_CMD_SET_CANDL_MODE    = 35
    ILUMI_API_CMD_SET_COLOR_SMOOTH  = 37
    ILUMI_API_CMD_GET_DEVICE_INFO   = 40
    ILUMI_API_CMD_ADD_ACTION        = 50
    ILUMI_API_CMD_DATA_CHUNK        = 52
    ILUMI_API_CMD_SET_COLOR_NEED_RESP = 54
    ILUMI_API_CMD_COMMISSION_WITH_ID  = 58
    ILUMI_API_CMD_CONFIG              = 65
    ILUMI_API_CMD_TREE_MESH_PROXY     = 68


class IlumiConfigCmdType:
    ILUMI_CONFIG_ENTER_BOOTLOADER = 2


async def get_shared_device(transport_spec: str) -> Device:
    """Return (creating if needed) the process-wide Bumble Device."""
    global _shared_device, _shared_transport
    async with _device_lock:
        if _shared_device is not None:
            return _shared_device
        logger.info(f"Opening HCI transport: {transport_spec}")
        _shared_transport = await open_transport(transport_spec)
        _shared_device = Device.with_hci(
            "IlumiHost",
            "F0:F1:F2:F3:F4:F5",
            _shared_transport.source,
            _shared_transport.sink,
        )
        await _shared_device.power_on()
        logger.info("Bumble device ready")
        return _shared_device


class IlumiSDK:
    """
    Ilumi BLE SDK backed by Google Bumble (direct HCI).
    Drop-in API-compatible replacement for ilumi_sdk.IlumiSDK.
    """

    def __init__(
        self,
        mac_address: Optional[str] = None,
        transport: Optional[str] = None,
    ):
        self.mac_address = mac_address or config.get_config("mac_address")
        self.network_key = config.get_config("network_key", 0)
        self.seq_num     = config.get_config("seq_num", 0)
        self.dfu_key     = config.get_config("dfu_key", 0x12345678)
        self._transport  = transport or os.environ.get("ILUMI_BT_TRANSPORT", "usb:0")

        self._device: Optional[Device] = None
        self._connection = None
        self._peer: Optional[Peer] = None
        self._char = None  # cached GATT characteristic

        self._last_color: Optional[Dict[str, int]] = None
        self._last_device_info: Optional[Dict[str, Any]] = None
        self._color_event       = asyncio.Event()
        self._device_info_event = asyncio.Event()
        self._mesh_info: List[Dict[str, Any]] = []
        self._mesh_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "IlumiSDK":
        if not self.mac_address:
            raise ValueError("No MAC address specified or enrolled.")
        self._device = await get_shared_device(self._transport)
        logger.info(f"Connecting to {self.mac_address}...")
        try:
            self._connection = await self._device.connect(self.mac_address)
        except Exception as e:
            raise IlumiConnectionError(f"Failed to connect to {self.mac_address}: {e}")

        self._peer = Peer(self._connection)
        await self._peer.discover_services()
        services = self._peer.get_services_by_uuid(ILUMI_SERVICE_UUID)
        if not services:
            raise IlumiConnectionError(f"Ilumi service not found on {self.mac_address}")
        chars = self._peer.get_characteristics_by_uuid(ILUMI_API_CHAR_UUID, service=services[0])
        if not chars:
            raise IlumiConnectionError(f"Ilumi API characteristic not found on {self.mac_address}")
        self._char = chars[0]
        await self._peer.subscribe(self._char, self._handle_notification)
        return self

    async def __aexit__(self, *_):
        if self._connection:
            logger.info(f"Disconnecting from {self.mac_address}...")
            try:
                await self._connection.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            self._connection = None
            self._peer = None
            self._char = None

    # ------------------------------------------------------------------
    # Notification handler (same logic as ilumi_sdk.py)
    # ------------------------------------------------------------------

    def _handle_notification(self, data: bytes) -> None:
        if len(data) < 2:
            return
        cmd_type = data[0]

        if cmd_type == IlumiApiCmdType.ILUMI_API_CMD_PROXY_MSG:
            if len(data) >= 10:
                inner_len = struct.unpack("<H", data[8:10])[0]
                if inner_len > 0:
                    inner = data[10:10+inner_len]
                    if inner[0] == IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR and len(inner) >= 6:
                        self._last_color = {
                            "r": inner[1], "g": inner[2], "b": inner[3],
                            "w": inner[4], "brightness": inner[5]
                        }
                        self._color_event.set()

        elif cmd_type == IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO:
            if len(data) >= 14:
                try:
                    u = struct.unpack("<H H B B H H", data[4:14])
                    self._last_device_info = {
                        "firmware_version":   u[0], "bootloader_version": u[1],
                        "commission_status":   u[2], "model_number":       u[3],
                        "reset_reason":        u[4], "ble_stack_version":  u[5],
                    }
                    self._device_info_event.set()
                except Exception as e:
                    logger.error(f"Failed to parse device info: {e}")

        elif cmd_type == IlumiApiCmdType.ILUMI_API_GET_BULB_COLOR:
            if len(data) >= 9:
                self._last_color = {
                    "r": data[4], "g": data[5], "b": data[6],
                    "w": data[7], "brightness": data[8]
                }
                self._color_event.set()

        elif cmd_type == IlumiApiCmdType.ILUMI_API_CMD_QUERY_ROUTING:
            if len(data) >= 4:
                payload_size = struct.unpack("<H", data[2:4])[0]
                payload = data[4:4+payload_size]
                for i in range(len(payload) // 8):
                    entry = payload[i*8:(i+1)*8]
                    if len(entry) < 8:
                        continue
                    mac_str = ":".join(f"{b:02X}" for b in entry[0:6][::-1])
                    hops    = entry[6]
                    rssi    = struct.unpack("b", entry[7:8])[0]
                    self._mesh_info.append({"address": mac_str, "hops": hops, "rssi": rssi})
                self._mesh_event.set()

    # ------------------------------------------------------------------
    # Internal send helpers
    # ------------------------------------------------------------------

    def _pack_header(self, message_type: int) -> bytes:
        """Packs the standard 6-byte Ilumi header."""
        if self.seq_num % 2 != 0:
            self.seq_num = (self.seq_num + 1) % 256
        header = struct.pack("<I", self.network_key) + struct.pack("B B", self.seq_num, message_type)
        self.seq_num = (self.seq_num + 2) % 256
        config.update_config("seq_num", self.seq_num)
        return header

    async def _write(self, payload: bytes, with_response: bool = True) -> None:
        """Write to the Ilumi characteristic."""
        if self._char is None:
            raise IlumiConnectionError("Not connected")
        await self._peer.write_value(self._char, payload, with_response=with_response)

    async def _send_command(self, payload: bytes) -> None:
        """Write with response + short delay."""
        await self._write(payload, with_response=True)
        await asyncio.sleep(0.1)

    async def _send_command_fast(self, payload: bytes) -> None:
        """Write without response (fire-and-forget)."""
        await self._write(payload, with_response=False)

    async def _send_chunked_command(self, data: bytes) -> None:
        """Splits payloads >20 bytes into 10-byte DATA_CHUNK fragments."""
        data_length = len(data)
        if data_length <= 20:
            await self._send_command(data)
            return
        for offset in range(0, data_length, 10):
            chunk_size = min(10, data_length - offset)
            chunk_payload = bytearray(10)
            chunk_payload[0:chunk_size] = data[offset:offset+chunk_size]
            chunk_struct    = struct.pack("<H H 10s", data_length, offset, bytes(chunk_payload))
            cmd_header      = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_DATA_CHUNK)
            await self._write(cmd_header + chunk_struct, with_response=True)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    async def discover(timeout: float = 5.0, transport: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans for Ilumi bulbs using Bumble."""
        transport_spec = transport or os.environ.get("ILUMI_BT_TRANSPORT", "usb:0")
        device = await get_shared_device(transport_spec)
        found = []

        loop = asyncio.get_event_loop()
        discovery_event = asyncio.Event()

        def on_advertisement(adv):
            name = adv.data.get(0x09) or ""  # Complete Local Name
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore')
            
            if name and ("ilumi" in name.lower() or name.startswith("L0")):
                addr = str(adv.address)
                if not any(b["address"] == addr for b in found):
                    found.append({"name": name, "address": addr, "rssi": adv.rssi})

        device.on('advertisement', on_advertisement)
        await device.start_scanning()
        await asyncio.sleep(timeout)
        await device.stop_scanning()
        device.remove_listener('advertisement', on_advertisement)
        
        return found

    # ------------------------------------------------------------------
    # Proxy messaging
    # ------------------------------------------------------------------

    async def send_proxy_message(self, target_macs: List[str], inner_payload: bytes) -> None:
        """Routes an inner API payload to target MACs via the mesh."""
        for target_mac in target_macs:
            mac_parts = [int(x, 16) for x in target_mac.split(':')]
            mac_parts.reverse()
            mac_bytes = bytes(mac_parts)
            service_type_ttl = 47 if len(inner_payload) <= 17 else 15
            proxy_data_len   = 6 + len(inner_payload)
            proxy_cmd    = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_PROXY_MSG)
            proxy_header = struct.pack("<B B H", service_type_ttl, 1, proxy_data_len)
            await self._send_chunked_command(proxy_cmd + proxy_header + mac_bytes + inner_payload)
            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # High-level commands (identical signatures to ilumi_sdk.IlumiSDK)
    # ------------------------------------------------------------------

    async def turn_on(self, delay: int = 0, transit: int = 0, targets: Optional[List[str]] = None) -> None:
        """Turns the bulb(s) on with optional fade (transit)."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_ON)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def turn_off(self, delay: int = 0, transit: int = 0, targets: Optional[List[str]] = None) -> None:
        """Turns the bulb(s) off with optional fade (transit)."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_OFF)
        payload = struct.pack("<H H", delay, transit)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255,
                        targets: Optional[List[str]] = None) -> None:
        """Sets an instant color."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_fast(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255,
                             targets: Optional[List[str]] = None) -> None:
        """Sets color without waiting for BLE acknowledgement."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command_fast(cmd + payload)

    async def set_color_smooth(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255,
                               duration_ms: int = 500, delay_sec: int = 0,
                               targets: Optional[List[str]] = None) -> None:
        """Fades to a color over a specific duration."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_SMOOTH)
        if duration_ms < 65535:
            time_val, time_unit = int(duration_ms), 0
        else:
            time_val, time_unit = int(duration_ms / 1000), 1
        payload = struct.pack("<H B B B B B B B B",
                               time_val, time_unit,
                               clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0,
                               clamp(delay_sec))
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_candle_mode(self, r: int, g: int, b: int, w: int = 0, brightness: int = 255,
                              targets: Optional[List[str]] = None) -> None:
        """Activates flickering candle mode."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_CANDL_MODE)
        payload = struct.pack("<B B B B B B B", clamp(r), clamp(g), clamp(b), clamp(w), clamp(brightness), 0, 0)
        if targets:
            await self.send_proxy_message(targets, cmd + payload)
        else:
            await self._send_command(cmd + payload)

    async def set_color_pattern(self, scene_idx: int, frames: List[Dict[str, int]],
                                repeatable: int = 1, start_now: int = 1) -> None:
        """Uploads and triggers an animation pattern."""
        clamp = lambda x: max(0, min(255, int(x)))
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN)
        frame_bytes = bytearray()
        for f in frames:
            frame_bytes.extend(
                struct.pack("<B B B B B B", clamp(f.get('r',0)), clamp(f.get('g',0)),
                            clamp(f.get('b',0)), clamp(f.get('w',0)), clamp(f.get('brightness',255)), 0) +
                struct.pack("<I I B B B B", f.get('sustain_ms',500), f.get('transit_ms',100), 0, 0, 0, 0)
            )
        total_struct_size = 13 + len(frame_bytes)
        scene_header = struct.pack("<H B B B B B", total_struct_size, scene_idx,
                                   len(frames), repeatable, scene_idx, start_now)
        await self._send_chunked_command(cmd + scene_header + frame_bytes)

    async def start_color_pattern(self, scene_idx: int) -> None:
        """Starts a previously uploaded animation scene."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_START_COLOR_PATTERN)
        await self._send_command(cmd + struct.pack("<B", scene_idx))

    async def get_bulb_color(self, targets: Optional[List[str]] = None) -> Optional[Dict[str, int]]:
        """Queries current bulb color status."""
        self._last_color = None
        self._color_event.clear()
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
        await self._send_command(self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO))
        try:
            await asyncio.wait_for(self._device_info_event.wait(), timeout=10.0)
            return self._last_device_info
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for device info.")
            return None

    async def commission(self, new_network_key: int, group_id: int, node_id: int) -> bool:
        """Assigns a network key and bulb ID. Returns success."""
        self.network_key = new_network_key
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_COMMISSION_WITH_ID)
        payload = struct.pack("<I H H", new_network_key, node_id, group_id)
        try:
            await self._send_command(cmd + payload)
            config.update_config("network_key", new_network_key)
            config.update_config("group_id", group_id)
            config.update_config("node_id", node_id)
            return True
        except Exception as e:
            logger.error(f"Failed to commission: {e}")
            return False

    async def enter_dfu_mode(self) -> None:
        """Triggers bootloader mode for firmware updates."""
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_CONFIG)
        dk = self.dfu_key
        payload = struct.pack("<B 4B", IlumiConfigCmdType.ILUMI_CONFIG_ENTER_BOOTLOADER,
                               dk & 0xFF, (dk >> 8) & 0xFF, (dk >> 16) & 0xFF, (dk >> 24) & 0xFF)
        await self._send_command(cmd + payload)

    async def get_mesh_info(self) -> List[Dict[str, Any]]:
        """Retrieves neighbour mesh routing info from the bulb."""
        self._mesh_info = []
        self._mesh_event.clear()
        await self._send_command(self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_QUERY_ROUTING))
        while True:
            try:
                await asyncio.wait_for(self._mesh_event.wait(), timeout=1.5)
                self._mesh_event.clear()
            except asyncio.TimeoutError:
                break
        return self._mesh_info

async def execute_on_targets(
    targets: List[str], coro_func
) -> Dict[str, Any]:
    """Helper to execute an SDK task across multiple bulbs (same API as ilumi_sdk)."""
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
