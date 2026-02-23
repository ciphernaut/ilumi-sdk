import asyncio
import sys
import struct
from ilumi_sdk import IlumiSDK, ILUMI_SERVICE_UUID

# Command ID for QUERY_ROUTING found in IlumiApiCmdType.java (31/0x1F)
QUERY_ROUTING = 31

async def probe_mesh(mac):
    # In the current SDK, IlumiSDK(mac) creates a connection to that specific mac
    sdk = IlumiSDK(mac)
    
    print(f"Connecting to {mac}...")
    try:
        async with sdk:
            print(f"Connected. Sending QUERY_ROUTING (ID {QUERY_ROUTING})...")
            
            # The SDK handles notifications internally, but we want to catch the raw data for this probe.
            # We can hijack the client's notification handler if needed, 
            # or just use the SDK's existing mechanisms if we can.
            
            # For QUERY_ROUTING, let's see if we can get the raw response.
            # We'll add a temporary characteristic listener here.
            
            def notification_handler(sender, data):
                print(f"Notification from {sender}: {data.hex()}")
                # Parse neighbor entries (8 bytes each: 6 mac, 1 hop, 1 rssi)
                if len(data) >= 5:
                     # Skip header (approx 4-5 bytes depending on protocol version)
                     # Based on IlumiDef.java: [api_type, status, payload_size(2)]
                     api_type = data[0]
                     status = data[1]
                     payload_size = struct.unpack('<H', data[2:4])[0] if len(data) >= 4 else 0
                     print(f"Parsed Header - Type: {api_type}, Status: {status}, Size: {payload_size}")
                     
                     payload_content = data[4:]
                     entry_size = 8
                     num_entries = len(payload_content) // entry_size
                     for i in range(num_entries):
                         entry = payload_content[i*entry_size : (i+1)*entry_size]
                         if len(entry) < 8: continue
                         mac_bytes = entry[0:6]
                         hops = entry[6]
                         rssi = struct.unpack('b', entry[7:8])[0]
                         mac_str = ":".join(f"{b:02X}" for b in mac_bytes[::-1])
                         print(f"  Neighbor: {mac_str}, Hops: {hops}, RSSI: {rssi} dBm")

            # Notification UUID is f000f0c1-0451-4000-b000-000000000000 according to ilumi_sdk.py outline
            # Actually, let's check the outline again.
            # ILUMI_API_CHAR_UUID = "f000f0c1-0451-4000-b000-000000000000"
            CHAR_UUID = "f000f0c1-0451-4000-b000-000000000000"
            
            # Stop the SDK's default handler temporarily
            await sdk.client.stop_notify(CHAR_UUID)
            await sdk.client.start_notify(CHAR_UUID, notification_handler)

            # Build the command packet: [CMD_ID]
            payload = bytearray([QUERY_ROUTING])
            
            # Use SDK's internal packing method
            data_to_send = sdk._pack_header(QUERY_ROUTING) # This likely includes net_key and seq
            
            print(f"Sending command... (Data: {data_to_send.hex()})")
            await sdk.client.write_gatt_char(CHAR_UUID, data_to_send, response=True)

            print("Waiting for response...")
            await asyncio.sleep(5)
            
            await sdk.client.stop_notify(CHAR_UUID)

    except Exception as e:
        print(f"Error during probe: {e}")
    finally:
        # sdk.__aexit__ handles disconnect
        pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 probe_mesh.py <MAC_ADDRESS>")
    else:
        asyncio.run(probe_mesh(sys.argv[1]))
