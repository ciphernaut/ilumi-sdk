import asyncio
import sys
from ilumi_sdk import IlumiSDK

async def main():
    if len(sys.argv) < 4:
        print("Usage: python3 color.py <R> <G> <B> [W]")
        sys.exit(1)
        
    r, g, b = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    w = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    
    sdk = IlumiSDK()
    print(f"Setting color for bulb at {sdk.mac_address} to R:{r} G:{g} B:{b} W:{w}...")
    await sdk.set_color(r, g, b, w)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
