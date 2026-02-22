import asyncio
from ilumi_sdk import IlumiSDK

async def main():
    sdk = IlumiSDK()
    print(f"Turning OFF bulb at {sdk.mac_address}...")
    await sdk.turn_off()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
