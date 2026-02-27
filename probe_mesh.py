import asyncio
import sys
import struct
from ilumi_sdk import IlumiSDK, ILUMI_SERVICE_UUID

# Command ID for QUERY_ROUTING found in IlumiApiCmdType.java (31/0x1F)
QUERY_ROUTING = 31

async def probe_mesh(mac):
    sdk = IlumiSDK(mac)
    print(f"Connecting to {mac}...")
    try:
        async with sdk:
            print("Connected. Querying mesh info via SDK...")
            mesh_info = await sdk.get_mesh_info()
            if not mesh_info:
                print("No mesh routing info returned.")
            else:
                print(f"Discovered {len(mesh_info)} neighbors:")
                for entry in mesh_info:
                    print(f"  Neighbor: {entry['address']}, Hops: {entry['hops']}, RSSI: {entry['rssi']} dBm")
    except Exception as e:
        print(f"Error during probe: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 probe_mesh.py <MAC_ADDRESS>")
    else:
        asyncio.run(probe_mesh(sys.argv[1]))
