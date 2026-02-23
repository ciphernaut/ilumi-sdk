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
    parser.add_argument("--fade", type=int, default=None, help="Fade duration in milliseconds (default: 500 for single/mesh, 0 for sequential)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fading (instant color change)")
    parser.add_argument("--mesh", action="store_true", help="Use mesh routing via a single bulb connection")
    parser.add_argument("--stream", action="store_true", help="Connect to all bulbs concurrently for simultaneous shared fading")
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
        if args.mesh or getattr(args, 'stream', False) or len(targets) <= 1:
            args.fade = 500
        else:
            args.fade = 0

    async def _set_color(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Setting color R:{args.r} G:{args.g} B:{args.b} W:{args.w} Bri:{args.brightness} (Fade: {args.fade}ms)...")
        async with sdk:
            if args.fade > 0:
                await sdk.set_color_smooth(args.r, args.g, args.b, args.w, args.brightness, duration_ms=args.fade)
            else:
                await sdk.set_color(args.r, args.g, args.b, args.w, args.brightness)

    async def _mesh_set_color(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy color change to {len(targets)} targets (Fade: {args.fade}ms, Retries: {args.retries})...")
        async with sdk:
            for i in range(args.retries):
                if args.fade > 0:
                    await sdk.set_color_smooth(args.r, args.g, args.b, args.w, args.brightness, duration_ms=args.fade, targets=targets)
                else:
                    await sdk.set_color(args.r, args.g, args.b, args.w, args.brightness, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)

    async def _stream_set_color():
        if not args.json:
            print(f"Streaming set_color to {len(targets)} targets (Fade: {args.fade}ms)...")
        from ilumi_sdk import IlumiSDK
        sdks = [IlumiSDK(mac) for mac in targets]
        results = {}
        active_sdks = []
        try:
            for sdk in sdks:
                try:
                    await sdk.__aenter__()
                    active_sdks.append(sdk)
                except Exception as e:
                    results[sdk.mac_address] = {"success": False, "error": str(e)}
            
            if active_sdks:
                coros = []
                for sdk in active_sdks:
                    if args.fade > 0:
                        coros.append(sdk.set_color_smooth(args.r, args.g, args.b, args.w, args.brightness, duration_ms=args.fade))
                    else:
                        coros.append(sdk.set_color(args.r, args.g, args.b, args.w, args.brightness))
                
                outcomes = await asyncio.gather(*coros, return_exceptions=True)
                for sdk, outcome in zip(active_sdks, outcomes):
                    if isinstance(outcome, Exception):
                        results[sdk.mac_address] = {"success": False, "error": str(outcome)}
                    else:
                        results[sdk.mac_address] = {"success": True, "error": None}
        finally:
            for sdk in active_sdks:
                try:
                    await sdk.__aexit__(None, None, None)
                except:
                    pass
        return results

    if args.stream:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await _stream_set_color()
            print(json.dumps({"command": "set_color", "targets": targets, "stream": True, "fade_ms": args.fade, "results": results}))
        else:
            await _stream_set_color()
            print("Done.")
    elif args.mesh:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets([proxy_target], _mesh_set_color)
            print(json.dumps({"command": "set_color", "targets": targets, "mesh": True, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets([proxy_target], _mesh_set_color)
            print("Done.")
    else:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets(targets, _set_color)
            print(json.dumps({"command": "set_color", "targets": targets, "mesh": False, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets(targets, _set_color)
            print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
