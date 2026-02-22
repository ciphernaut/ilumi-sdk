import asyncio
import sys
import argparse
import traceback
from ilumi_sdk import IlumiSDK

async def play_fireworks(sdk):
    # Fireworks loop from effects_1.json
    # 6 frames: Red, Green, Blue, Orange, Yellow, Purple
    # 500ms sustain, 100ms transit time per frame
    frames = [
        {'r': 255, 'g': 0, 'b': 0, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100},
        {'r': 0, 'g': 255, 'b': 0, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100},
        {'r': 0, 'g': 0, 'b': 255, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100},
        {'r': 255, 'g': 165, 'b': 0, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100},
        {'r': 255, 'g': 255, 'b': 0, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100},
        {'r': 128, 'g': 0, 'b': 128, 'w': 0, 'brightness': 255, 'sustain_ms': 500, 'transit_ms': 100}
    ]
    
    # Store this pattern in the bulb's scene index 4 (Matches its sortingIndex in the app + 1)
    scene_idx = 4
    print("Uploading Fireworks pattern to the bulb...")
    # Using repeatable=255 for infinite loops, and start_now=1 to auto-start it.
    await sdk.set_color_pattern(scene_idx, frames, repeatable=255, start_now=1)
    print("Fireworks uploaded and auto-started! Kaboom!")

EFFECTS = {
    "fireworks": play_fireworks
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
