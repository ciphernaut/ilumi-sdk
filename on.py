import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets
import config

async def main():
    parser = argparse.ArgumentParser(description="Turn on Ilumi bulb(s)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    parser.add_argument("--fade", type=int, default=1000, help="Fade duration in milliseconds (default: 1000)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fading (instant on)")
    args = parser.parse_args()
    
    if args.no_fade:
        args.fade = 0
    fade_sec = int(args.fade / 1000)

    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    async def _turn_on(sdk):
        if not args.json:
            print(f"Turning on bulb {sdk.mac_address} (Fade: {fade_sec}s)...")
        async with sdk:
            await sdk.turn_on(transit=fade_sec)
        
    if args.json:
        with open(os.devnull, 'w') as f, redirect_stdout(f):
            results = await execute_on_targets(targets, _turn_on)
        print(json.dumps({"command": "turn_on", "targets": targets, "fade_ms": args.fade, "results": results}))
    else:
        await execute_on_targets(targets, _turn_on)

if __name__ == "__main__":
    asyncio.run(main())
