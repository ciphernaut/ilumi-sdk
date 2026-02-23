import asyncio
import sys
import json
from ilumi_sdk import IlumiSDK

async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mesh_viz.py <MAC_ADDRESS>")
        return

    mac = sys.argv[1]
    sdk = IlumiSDK(mac)
    
    print(f"Connecting to {mac} to retrieve mesh diagnostics...")
    try:
        async with sdk:
            neighbors = await sdk.get_mesh_info()
            
            if not neighbors:
                print("No neighbor information retrieved. The bulb might not have any active peers or the command is not supported by this firmware version.")
                return

            print(f"\nMesh Neighbors for {mac}:")
            print("-" * 60)
            print(f"{'Address':<20} | {'Hops':<5} | {'RSSI':<8}")
            print("-" * 60)
            
            # Sort by RSSI
            neighbors.sort(key=lambda x: x['rssi'], reverse=True)
            
            for n in neighbors:
                print(f"{n['address']:<20} | {n['hops']:<5} | {n['rssi']:>4} dBm")
            
            print("-" * 60)
            print(f"Total Neighbors: {len(neighbors)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
