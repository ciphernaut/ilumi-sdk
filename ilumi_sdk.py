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

    async def _send_command(self, payload, client=None):
        if not self.mac_address:
            raise ValueError("No MAC address specified or enrolled.")
            
        if client:
            print(f"Sending chunk with existing client: {payload.hex()}")
            await client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            return
        
        print(f"Connecting to {self.mac_address} to send payload {payload.hex()}...")
        async with BleakClient(self.mac_address, timeout=10.0) as new_client:
            if not new_client.is_connected:
                raise Exception("Failed to connect to bulb.")
            
            def notification_handler(sender, data):
                print(f"Notification from {sender}: {data.hex()}")

            await new_client.start_notify(ILUMI_API_CHAR_UUID, notification_handler)
            
            # Write to the characteristic
            await new_client.write_gatt_char(ILUMI_API_CHAR_UUID, payload, response=True)
            print(f"Sent command to {self.mac_address}: {payload.hex()}")
            
            # Wait for response notification
            await asyncio.sleep(1.0)
            await new_client.stop_notify(ILUMI_API_CHAR_UUID)

    async def _send_chunked_command(self, data: bytes):
        """
        Android `IlumiSDK.java` splits payloads > 20 bytes into 10-byte fragments
        using `ILUMI_API_CMD_DATA_CHUNK`. Each chunk gets its own GATT header and sequence number.
        """
        data_length = len(data)
        if data_length <= 20:
            await self._send_command(data)
            return

        async with BleakClient(self.mac_address) as client:
            print(f"Connecting to {self.mac_address} for chunked payload upload...")
            
            def notification_handler(sender, data):
                print(f"Notification from {sender}: {data.hex()}")

            await client.start_notify(ILUMI_API_CHAR_UUID, notification_handler)
            
            for offset in range(0, data_length, 10):
                chunk_size = min(10, data_length - offset)
                # Create a 10-byte padded array for the chunk
                chunk_payload = bytearray(10)
                chunk_payload[0:chunk_size] = data[offset:offset+chunk_size]
    
                # gatt_ilumi_data_chunk_t bytes:
                # - total_byte_size (U16)
                # - byte_offset (U16)
                # - payload (U8[10])
                chunk_struct = struct.pack("<H H 10s", data_length, offset, bytes(chunk_payload))
                
                # Pack the GATT header explicitly for this chunk with advancing seqnum
                cmd_header = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_DATA_CHUNK)
                
                print(f"Sending chunk {offset}/{data_length}")
                await self._send_command(cmd_header + chunk_struct, client=client)
                
                # Add a small delay so we do not overwhelm the bulb's BLE queue
                await asyncio.sleep(0.1)

            # Keep connection open for a moment to receive any final notifications
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
            # NOTE: Android effects JSON sends 'brightness' as 0-255, we pass it down cleanly.
            color = struct.pack("<B B B B B B", f.get('r', 0), f.get('g', 0), f.get('b', 0), f.get('w', 0), f.get('brightness', 255), 0)
            
            # The remaining fields of internal_color_scheme:
            # sustain_time_msed(U32) -> 4 bytes
            # transit_time_msed(U32) -> 4 bytes
            # sustain_effect(U8) -> 1 byte
            # transit_effect(U8) -> 1 byte
            # loopback_index(U8) -> 1 byte
            # loopback_times(U8) -> 1 byte
            # Total timings: 12 bytes
            timings = struct.pack("<I I B B B B", f.get('sustain_ms', 500), f.get('transit_ms', 100), 0, 0, 0, 0)
            frame_bytes.extend(color + timings)

        # Base struct payload size (gatt_ilumi_set_scene_t fields are 7 bytes)
        # Note: Android's `size()` includes gatt_api_base (6 bytes)! The payload size field
        # MUST include the 6 base header bytes even though they are technically a different struct level.
        total_struct_size = 13 + len(frame_bytes) 
        array_size = len(frames)
        
        scene_header = struct.pack("<H B B B B B", total_struct_size, scene_idx, array_size, repeatable, scene_idx, start_now)
        
        # We append a dummy 0-byte header since `_send_chunked_command` will overwrite the nested header.
        # Wait, if `cmd` was generated by `_pack_header(41)`, it already incremented the seqnum!
        # We should just pass `cmd` directly down.
        full_payload = cmd + scene_header + frame_bytes
        
        await self._send_chunked_command(full_payload)

    async def start_color_pattern(self, scene_idx):
        cmd = self._pack_header(IlumiApiCmdType.ILUMI_API_CMD_START_COLOR_PATTERN)
        # gatt_ilumi_start_scene_t: scene_idx(U8)
        payload = struct.pack("<B", scene_idx)
        await self._send_command(cmd + payload)

