import argparse
import asyncio
import json
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
    
    args = parser.parse_args()

    if not args.profile:
        print(json.dumps(list(PROFILES.keys())))
        return
        
    profile_name = args.profile.lower().replace(" ", "_")

    if profile_name not in PROFILES:
        print(f"Error: Profile '{profile_name}' not found.")
        print(f"Valid profiles: {json.dumps(list(PROFILES.keys()))}")
        return

    r, g, b, w = PROFILES[profile_name]
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    async def _set_profile(sdk):
        print(f"[{sdk.mac_address}] Setting profile '{profile_name}'...")
        async with sdk:
            if profile_name in ["candle_light", "core_breach"]:
                await sdk.set_candle_mode(r, g, b, w, args.brightness)
            else:
                await sdk.set_color(r, g, b, w, args.brightness)

    await execute_on_targets(targets, _set_profile)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
