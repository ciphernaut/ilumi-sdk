import argparse
import asyncio
from ilumi_sdk import execute_on_targets
import config

async def _turn_off(sdk):
    print(f"Turning off bulb {sdk.mac_address}...")
    async with sdk:
        await sdk.turn_off()

async def main():
    parser = argparse.ArgumentParser(description="Turn off Ilumi bulb(s)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    args = parser.parse_args()
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        return
        
    await execute_on_targets(targets, _turn_off)

if __name__ == "__main__":
    asyncio.run(main())
