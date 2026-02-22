import sys
import asyncio
from ilumi_sdk import IlumiSDK

PROFILES = {
    "cool white": (0, 68, 111, 255),
    "daylight": (0, 69, 83, 255),
    "incandescent": (0, 32, 33, 255),
    "natural white": (22, 0, 17, 255),
    "early morning": (83, 75, 0, 255),
    "sunrise": (107, 0, 0, 255),
    "sunlight": (107, 0, 0, 255),
    "edison bulb": (175, 180, 0, 63),
    "bug lighting": (255, 30, 0, 0),
    "sleep": (190, 0, 0, 0),
    "relax": (190, 0, 63, 0),
    "beauty": (0, 0, 255, 0),
    "think": (75, 0, 255, 0),
    "focus": (77, 77, 255, 0),
    "energize": (0, 153, 255, 0),
    "witches brew": (255, 0, 0, 0),
    "candle light": (255, 190, 0, 29), # Special Mode
    "core breach": (255, 150, 0, 100)  # Meltdown Mode
}

async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 whites.py \"<profile_name>\" [brightness]")
        print("Available profiles:")
        for profile in PROFILES:
            print(f"  - {profile}")
        sys.exit(1)
        
    profile_name = sys.argv[1].lower()
    brightness = int(sys.argv[2]) if len(sys.argv) > 2 else 255

    if profile_name not in PROFILES:
        print(f"Error: Profile '{profile_name}' not found.")
        sys.exit(1)

    r, g, b, w = PROFILES[profile_name]
    
    sdk = IlumiSDK()
    print(f"Setting profile '{profile_name}' for bulb at {sdk.mac_address} at brightness {brightness}...")
    
    if profile_name in ["candle light", "core breach"]:
        await sdk.set_candle_mode(r, g, b, w, brightness)
    else:
        await sdk.set_color(r, g, b, w, brightness)
        
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
