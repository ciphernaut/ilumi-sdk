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
    ILUMI_API_CMD_SET_COLOR_NEED_RESP = 54
    ILUMI_API_CMD_COMMISSION_WITH_ID = 58
    ILUMI_API_CMD_SET_CANDL_MODE = 35
    ILUMI_API_CMD_START_COLOR_PATTERN = 40
    ILUMI_API_CMD_SET_COLOR_PATTERN = 41

class IlumiSDK:
    def __init__(self, mac_address=None):
        self.mac_address = mac_address or config.get_config("mac_address")
        self.network_key = config.get_config("network_key", 0)
        self.seq_num = config.get_config("seq_num", 0)

    def _pack_header(self, cmd_type):
        """
        Packs the 6-byte GATT header:
        - 4-byte network key (LE) [0:4]
        - 1-byte seq_num [4]
        - 1-byte cmd type [5]
        Based on gatt_api_base struct in IlumiPacking.java.
        """
        # The C struct equivalent ofjavolution gatt_api_base is packed in the order the fields are 
        # instantiated in its constructor:
        # [0:4] Unsigned32 network_key
        # [4]   Unsigned8 seq_num
        # [5]   Enum8 message_type
        header = struct.pack("<I B B", self.network_key, self.seq_num, cmd_type)
        self.seq_num = (self.seq_num + 2) & 0xFE
        config.update_config("seq_num", self.seq_num)
        # Android adds the network key and seqnum manually in insertNetworkKey_SeqnumForNodeMac
        return header

    async def _send_command(self, payload):
        if not self.mac_address:
            raise ValueError("No MAC address specified or enrolled.")
        
        print(f"Connecting to {self.mac_address} to send payload {payload.hex()}...")
        async with BleakClient(self.mac_address, timeout=10.0) as client:
            if not client.is_connected:
                raise Exception("Failed to connect to bulb.")
            
            def notification_handler(sender, data):
                print(f"Notification from {sender}: {data.hex()}")

            await client.start_notify(ILUMI_API_CHAR_UUID, notification_handler)
            
            # Write to the characteristic
            await client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            print(f"Sent command to {self.mac_address}: {payload.hex()}")
            
            # Wait for response notification
            await asyncio.sleep(1.0)
            await client.stop_notify(ILUMI_API_CHAR_UUID)

    async def commission(self, new_network_key, group_id, node_id):
        self.network_key = new_network_key
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_COMMISSION_WITH_ID)
        # gatt_ilumi_commission_with_id_t in IlumiPacking.java:
        # new_network_key: Unsigned32, node_id: Unsigned16, group_id: Unsigned16 (All Little Endian)
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
        # gatt_ilumi_turnonoff_t: turn_onoff_after_delay_in_second (U16), turn_onoff_transit_period_in_second (U16)
        payload = struct.pack("<H H", delay, transit)
        await self._send_command(cmd + payload)

    async def turn_off(self, delay=0, transit=0):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_TURN_OFF)
        payload = struct.pack("<H H", delay, transit)
        await self._send_command(cmd + payload)

    async def set_color(self, r, g, b, w=0, brightness=255):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
        # gatt_ilumi_set_color_t: Red(1), Green(1), Blue(1), White(1), Brightness(1), Reserved(1), ColorType(1)
        # IlumiDefaultColorType = DEFAULT_COLOR_DAY (0)
        payload = struct.pack("<B B B B B B B", r, g, b, w, brightness, 0, 0)
        await self._send_command(cmd + payload)

    async def set_candle_mode(self, r, g, b, w=0, brightness=255):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_CANDL_MODE)
        # gatt_ilumi_set_color_t structure is identical, just passed with CANDL_MODE
        payload = struct.pack("<B B B B B B B", r, g, b, w, brightness, 0, 0)
        await self._send_command(cmd + payload)

    async def set_color_pattern(self, scene_idx, frames, repeatable=1, start_now=1):
        """
        Uploads a color animation pattern to the bulb.
        `frames` should be a list of dicts with:
        {'r': int, 'g': int, 'b': int, 'w': int, 'brightness': int, 'sustain_ms': int, 'transit_ms': int}
        """
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN)
        
        # Build the gatt_ilumi_set_scene_t structure
        # payload_size(U16), scene_idx(U8), array_size(U8), repeatable(U8), next_idx(U8), start_now(U8)
        
        # Build the frame data array from internal_color_scheme
        frame_bytes = bytearray()
        for f in frames:
            # IlumiColorInternal: Red(1), Green(1), Blue(1), White(1), Brightness(1), Reserved(1) -> 6 bytes
            color = struct.pack("<B B B B B B", f.get('r', 0), f.get('g', 0), f.get('b', 0), f.get('w', 0), f.get('brightness', 255), 0)
            # sustain_time_msed(U32), transit_time_msed(U32), sustain_effect(1), transit_effect(1), loopback_index(1), loopback_times(1)
            timings = struct.pack("<I I B B B B", f.get('sustain_ms', 500), f.get('transit_ms', 100), 0, 0, 0, 0)
            frame_bytes.extend(color + timings)

        # Base struct payload size
        total_struct_size = 7 + len(frame_bytes) 
        array_size = len(frames)
        
        scene_header = struct.pack("<H B B B B B", total_struct_size, scene_idx, array_size, repeatable, scene_idx, start_now)
        await self._send_command(cmd + scene_header + frame_bytes)

    async def start_color_pattern(self, scene_idx):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_START_COLOR_PATTERN)
        # gatt_ilumi_start_scene_t: scene_idx(U8)
        payload = struct.pack("<B", scene_idx)
        await self._send_command(cmd + payload)

