import asyncio
from ilumi_sdk import IlumiSDK

async def main():
    sdk = IlumiSDK() # Uses MAC and network key from config
    print(f"Turning ON bulb at {sdk.mac_address}...")
    await sdk.turn_on()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
