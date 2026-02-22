import asyncio
import sys
from ilumi_sdk import IlumiSDK
import config

async def main():
    bulb_mac = "FD:66:EE:0A:7B:67"
    config.update_config("mac_address", bulb_mac)
    
    sdk = IlumiSDK(bulb_mac)
    print(f"Found bulb at {bulb_mac}. Attempting to enroll...")
    
    # 0 = network key, 1 = group ID, 1 = node ID
    # Note: during fresh commission, typical network key is generated.
    # We will pick a random network key or continue using current state if any.
    import random
    new_network_key = random.randint(1000, 999999)
    success = await sdk.commission(new_network_key, 1, 1)
    
    if success:
        print("Enrollment successful. Run 'python3 on.py' to test.")
    else:
        print("Enrollment failed.")

if __name__ == "__main__":
    asyncio.run(main())    
