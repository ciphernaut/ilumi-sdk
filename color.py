import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets
import config

async def main():
    parser = argparse.ArgumentParser(description="Set Ilumi bulb(s) color")
    parser.add_argument("r", type=int, help="Red (0-255)")
    parser.add_argument("g", type=int, help="Green (0-255)")
    parser.add_argument("b", type=int, help="Blue (0-255)")
    parser.add_argument("w", type=int, nargs="?", default=0, help="White (0-255)")
    parser.add_argument("brightness", type=int, nargs="?", default=255, help="Brightness (0-255)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    parser.add_argument("--fade", type=int, default=500, help="Fade duration in milliseconds (default: 500)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fading (instant color change)")
    
    args = parser.parse_args()
    
    if args.no_fade:
        args.fade = 0
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    async def _set_color(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Setting color R:{args.r} G:{args.g} B:{args.b} W:{args.w} Bri:{args.brightness} (Fade: {args.fade}ms)...")
        async with sdk:
            if args.fade > 0:
                await sdk.set_color_smooth(args.r, args.g, args.b, args.w, args.brightness, duration_ms=args.fade)
            else:
                await sdk.set_color(args.r, args.g, args.b, args.w, args.brightness)

    if args.json:
        with open(os.devnull, 'w') as f, redirect_stdout(f):
            results = await execute_on_targets(targets, _set_color)
        print(json.dumps({"command": "set_color", "targets": targets, "fade_ms": args.fade, "results": results}))
    else:
        await execute_on_targets(targets, _set_color)
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
