import asyncio
import argparse
from ilumi_sdk import IlumiSDK, IlumiApiCmdType
import config

async def main():
    parser = argparse.ArgumentParser(description="Get bulb color")
    parser.add_argument("name", type=str, help="Bulb name to query")
    parser.add_argument("--proxy", type=str, help="Proxy bulb name or MAC")
    args = parser.parse_args()
    
    target_macs = config.resolve_targets(target_name=args.name, target_mac=args.name)
    if not target_macs:
        print("No targets found.")
        return
    target = target_macs[0]
    
    if args.proxy:
        proxy_macs = config.resolve_targets(target_name=args.proxy, target_mac=args.proxy)
        if not proxy_macs:
            print(f"Could not resolve proxy: {args.proxy}")
            return
        connection_mac = proxy_macs[0]
        mesh_targets = [target]
    else:
        connection_mac = target
        mesh_targets = None
        
    sdk = IlumiSDK(connection_mac)
    async with sdk:
        res = await sdk.get_bulb_color(targets=mesh_targets)
    if res:
        print(f"Color: {res}")
        
if __name__ == "__main__":
    asyncio.run(main())
