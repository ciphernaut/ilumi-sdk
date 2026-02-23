import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets
import config

PROFILES = {
    "cool_white": (0, 68, 111, 255),
    "daylight": (0, 69, 83, 255),
    "incandescent": (0, 32, 33, 255),
    "natural_white": (22, 0, 17, 255),
    "early_morning": (83, 75, 0, 255),
    "sunrise": (107, 0, 0, 255),
    "sunlight": (107, 0, 0, 255),
    "edison_bulb": (175, 180, 0, 63),
    "bug_lighting": (255, 30, 0, 0),
    "sleep": (190, 0, 0, 0),
    "relax": (190, 0, 63, 0),
    "beauty": (0, 0, 255, 0),
    "think": (75, 0, 255, 0),
    "focus": (77, 77, 255, 0),
    "energize": (0, 153, 255, 0),
    "witches_brew": (255, 0, 0, 0),
    "candle_light": (255, 190, 0, 29), # Special Mode
    "core_breach": (255, 150, 0, 100)  # Meltdown Mode
}

async def main():
    parser = argparse.ArgumentParser(description="Set white profiles for Ilumi bulb(s)")
    parser.add_argument("profile", type=str, nargs="?", help="Profile name (leave empty to list)")
    parser.add_argument("brightness", type=int, nargs="?", default=255, help="Brightness (0-255)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    parser.add_argument("--fade", type=int, default=None, help="Fade duration in milliseconds (default: 500 for single/mesh, 0 for sequential)")
    parser.add_argument("--no-fade", action="store_true", help="Disable fading (instant color change)")
    parser.add_argument("--mesh", action="store_true", help="Use mesh routing via a single bulb connection")
    parser.add_argument("--retries", type=int, default=3, help="Number of times to send mesh commands to ensure delivery (default: 3)")
    
    args = parser.parse_args()

    if not args.profile:
        print(json.dumps(list(PROFILES.keys())))
        return
        
    profile_name = args.profile.lower().replace(" ", "_")

    if profile_name not in PROFILES:
        if args.json:
            print(json.dumps({"error": f"Profile '{profile_name}' not found", "available": list(PROFILES.keys())}))
        else:
            print(f"Error: Profile '{profile_name}' not found.")
            print(f"Valid profiles: {json.dumps(list(PROFILES.keys()))}")
        return

    r, g, b, w = PROFILES[profile_name]
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    if args.no_fade:
        args.fade = 0
    elif args.fade is None:
        if args.mesh or len(targets) <= 1:
            args.fade = 500
        else:
            args.fade = 0

    async def _set_profile(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Setting profile '{profile_name}' (Fade: {args.fade}ms)...")
        async with sdk:
            if profile_name in ["candle_light", "core_breach"]:
                await sdk.set_candle_mode(r, g, b, w, args.brightness)
            else:
                if args.fade > 0:
                    await sdk.set_color_smooth(r, g, b, w, args.brightness, duration_ms=args.fade)
                else:
                    await sdk.set_color(r, g, b, w, args.brightness)

    async def _mesh_set_profile(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy profile '{profile_name}' to {len(targets)} targets (Fade: {args.fade}ms, Retries: {args.retries})...")
        async with sdk:
            for i in range(args.retries):
                if profile_name in ["candle_light", "core_breach"]:
                    await sdk.set_candle_mode(r, g, b, w, args.brightness, targets=targets)
                else:
                    if args.fade > 0:
                        await sdk.set_color_smooth(r, g, b, w, args.brightness, duration_ms=args.fade, targets=targets)
                    else:
                        await sdk.set_color(r, g, b, w, args.brightness, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)

    if args.mesh and len(targets) > 1:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets([targets[0]], _mesh_set_profile)
            print(json.dumps({"command": "set_white_profile", "profile": profile_name, "targets": targets, "mesh": True, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets([targets[0]], _mesh_set_profile)
            print("Done.")
    else:
        if args.json:
            with open(os.devnull, 'w') as f, redirect_stdout(f):
                results = await execute_on_targets(targets, _set_profile)
            print(json.dumps({"command": "set_white_profile", "profile": profile_name, "targets": targets, "mesh": False, "fade_ms": args.fade, "results": results}))
        else:
            await execute_on_targets(targets, _set_profile)
            print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
