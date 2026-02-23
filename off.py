import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets
import config

async def main():
    parser = argparse.ArgumentParser(description="Turn off Ilumi bulb(s)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    parser.add_argument("--fade", type=int, default=None, help="Fade duration in milliseconds (default: 1000 for single/mesh, 0 for sequential)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fading (instant off)")
    parser.add_argument("--mesh", action="store_true", help="Use mesh routing via a single bulb connection")
    parser.add_argument("--proxy", type=str, help="Specify proxy bulb by name or MAC")
    parser.add_argument("--retries", type=int, default=3, help="Number of times to send mesh commands to ensure delivery (default: 3)")
    args = parser.parse_args()
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    if args.proxy:
        proxy_targets = config.resolve_targets(target_mac=args.proxy, target_name=args.proxy)
        proxy_target = proxy_targets[0] if proxy_targets else targets[0]
    else:
        proxy_target = targets[0]

    if args.no_fade:
        args.fade = 0
    elif args.fade is None:
        if args.mesh or len(targets) <= 1:
            args.fade = 1000
        else:
            args.fade = 0

    fade_sec = int(args.fade / 1000)



    async def _turn_off(sdk):
        if not args.json:
            print(f"Turning off bulb {sdk.mac_address} (Fade: {fade_sec}s)...")
        async with sdk:
            await sdk.turn_off(transit=fade_sec)

    async def _mesh_turn_off(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy turn_off to {len(targets)} targets (Fade: {fade_sec}s, Retries: {args.retries})...")
        async with sdk:
            for i in range(args.retries):
                await sdk.turn_off(transit=fade_sec, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)
        
    if args.mesh:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets([proxy_target], _mesh_turn_off)
            print(json.dumps({"command": "turn_off", "targets": targets, "mesh": True, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets([proxy_target], _mesh_turn_off)
    else:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets(targets, _turn_off)
            print(json.dumps({"command": "turn_off", "targets": targets, "mesh": False, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets(targets, _turn_off)

if __name__ == "__main__":
    asyncio.run(main())
