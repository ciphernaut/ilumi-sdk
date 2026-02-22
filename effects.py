import asyncio
import sys
import argparse
import traceback
from ilumi_sdk import IlumiSDK
from effects_data import EFFECTS_DATA

async def play_dynamic_effect(sdk, effect_name):
    frames = EFFECTS_DATA[effect_name]
    
    # Use a fixed scene index for custom effects
    scene_idx = 4
    print(f"Uploading {effect_name} pattern to the bulb...")
    # Using repeatable=255 for infinite loops, and start_now=1 to auto-start it.
    await sdk.set_color_pattern(scene_idx, frames, repeatable=255, start_now=1)
    
    # Explicitly start the pattern as well, just in case start_now=1 isn't enough
    print(f"Triggering StartColorPattern for {effect_name} index {scene_idx}...")
    await sdk.start_color_pattern(scene_idx)
    
    print(f"{effect_name.capitalize()} uploaded and started!")
    
    # Keep alive for 10 seconds to allow for observations/captures
    print("Waiting 10 seconds for observation...")
    await asyncio.sleep(10)

def make_effect_func(effect_name):
    async def _play(sdk):
        await play_dynamic_effect(sdk, effect_name)
    return _play

EFFECTS = {
    name: make_effect_func(name) for name in EFFECTS_DATA.keys()
}


async def main():
    parser = argparse.ArgumentParser(description="Apply an animated effect to an Ilumi bulb.")
    parser.add_argument("effect", choices=list(EFFECTS.keys()), help="The name of the effect to play.")
    args = parser.parse_args()
    
    effect_name = args.effect
    
    try:
        sdk = IlumiSDK()
    except Exception as e:
        print(f"Error initializing SDK. Have you run enroll.py yet? {e}")
        return
        
    print(f"Applying effect '{effect_name}'...")
    
    try:
        effect_func = EFFECTS[effect_name]
        await effect_func(sdk)
    except Exception as e:
        print("Failed to play effect:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
