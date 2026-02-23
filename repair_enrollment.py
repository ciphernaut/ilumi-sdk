import asyncio
from ilumi_sdk import IlumiSDK
import config

async def main():
    mac = "FD:66:EE:0A:7B:67"
    name = "computer"
    node_id = 6
    network_key = config.get_config("network_key")
    
    print(f"Re-enrolling {name} ({mac}) with Node ID {node_id}...")
    
    config.add_bulb(mac, name, "office, test", node_id)
    
    sdk = IlumiSDK(mac)
    async with sdk:
        success = await sdk.commission(network_key, 1, node_id)
        if success:
            print("Successfully re-enrolled!")
        else:
            print("Failed to commission.")

if __name__ == "__main__":
    asyncio.run(main())
