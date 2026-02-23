import argparse
import asyncio
import json
import traceback
from ilumi_sdk import execute_on_targets
from effects_data import EFFECTS_DATA

async def play_dynamic_effect(sdk, effect_name):
    frames = EFFECTS_DATA[effect_name]
    
    # Use a fixed scene index for custom effects
    scene_idx = 4
    print(f"[{sdk.mac_address}] Uploading {effect_name} pattern...")
    # Using repeatable=255 for infinite loops, and start_now=1 to auto-start it.
    await sdk.set_color_pattern(scene_idx, frames, repeatable=255, start_now=1)
    
    # Explicitly start the pattern as well, just in case start_now=1 isn't enough
    await sdk.start_color_pattern(scene_idx)
    print(f"[{sdk.mac_address}] Effect started!")

async def main():
    available_effects = list(EFFECTS_DATA.keys())
    
    parser = argparse.ArgumentParser(description="Play dynamic effects on Ilumi bulb(s)")
    parser.add_argument("effect", type=str, nargs="?", help="Effect name (leave empty to list)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    
    args = parser.parse_args()

    if not args.effect:
        # Machine-parsable JSON output of available effects
        print(json.dumps(available_effects))
        return
        
    effect_name = args.effect.lower().replace(" ", "_")
    
    if effect_name not in EFFECTS_DATA:
        print(f"Error: Effect '{effect_name}' not found.")
        print(f"Valid effects: {json.dumps(available_effects)}")
        return
    
    # Import config late so that --help isn't blocked by missing config file
    import config
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    async def _play(sdk):
        async with sdk:
            try:
                await play_dynamic_effect(sdk, effect_name)
            except Exception as e:
                print(f"[{sdk.mac_address}] Failed to play effect:")
                traceback.print_exc()

    await execute_on_targets(targets, _play)

if __name__ == "__main__":
    asyncio.run(main())
