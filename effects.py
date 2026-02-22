import asyncio
import sys
import json
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

async def main():
    available_effects = list(EFFECTS_DATA.keys())
    
    if len(sys.argv) < 2:
        # Machine-parsable JSON output of available effects
        print(json.dumps(available_effects))
        sys.exit(0)
        
    effect_name = sys.argv[1].lower().replace(" ", "_")
    
    if effect_name not in EFFECTS_DATA:
        print(f"Error: Effect '{effect_name}' not found.")
        print(f"Valid effects: {json.dumps(available_effects)}")
        sys.exit(1)
    
    try:
        sdk = IlumiSDK()
    except Exception as e:
        print(f"Error initializing SDK. Have you run enroll.py yet? {e}")
        return
        
    print(f"Applying effect '{effect_name}'...")
    
    try:
        await play_dynamic_effect(sdk, effect_name)
    except Exception as e:
        print("Failed to play effect:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
