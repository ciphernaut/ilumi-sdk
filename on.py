import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets
import config

async def _turn_on(sdk):
    print(f"Turning on bulb {sdk.mac_address}...")
    async with sdk:
        await sdk.turn_on()

async def main():
    parser = argparse.ArgumentParser(description="Turn on Ilumi bulb(s)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    args = parser.parse_args()
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return
        
    if args.json:
        with open(os.devnull, 'w') as f, redirect_stdout(f):
            results = await execute_on_targets(targets, _turn_on)
        print(json.dumps({"command": "turn_on", "targets": targets, "results": results}))
    else:
        await execute_on_targets(targets, _turn_on)

if __name__ == "__main__":
    asyncio.run(main())
