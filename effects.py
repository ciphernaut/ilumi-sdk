import asyncio
import sys
import argparse
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
    
    # Store this pattern in the bulb's scene index 3 (Matches its sortingIndex in the app)
    scene_idx = 3
    print("Uploading Fireworks pattern to the bulb...")
    await sdk.set_color_pattern(scene_idx, frames, repeatable=1, start_now=1)
    
    # Even though start_now=1 is passed, the Android app explicitly calls start_color_pattern as well
    print("Starting Fireworks pattern...")
    await sdk.start_color_pattern(scene_idx)
    print("Fireworks started! Kaboom!")

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
        print(f"Failed to play effect: {e}")

if __name__ == "__main__":
    asyncio.run(main())
