import asyncio
import os
import sys
import time
from ilumi_sdk import IlumiSDK

async def take_snapshot(label: str):
    filename = f"verify_{label}_{int(time.time())}.jpg"
    filepath = f"/projects/antigravity/ilumi/tests/{filename}"
    print(f"Capturing snapshot: {filepath}")
    # Using sg video -c "fswebcam ..." as per workflow
    os.system(f'sg video -c "fswebcam --no-banner {filepath}"')
    return filepath

async def verify():
    # Use 'computer' bulb as specified in ilumi_config.json
    target_mac = "FD:66:EE:0A:7B:67" # Computer bulb
    
    print(f"Starting verification on {target_mac}...")
    
    async with IlumiSDK(target_mac) as sdk:
        # 1. Baseline: Red
        print("Setting baseline: RED")
        await sdk.set_color(255, 0, 0)
        await asyncio.sleep(2)
        await take_snapshot("baseline_red")
        
        # 2. Random Color
        print("Triggering SET_RANDOM_COLOR")
        await sdk.set_random_color()
        await asyncio.sleep(2)
        await take_snapshot("random_color_1")
        
        # 3. Random Color again (should be different)
        print("Triggering SET_RANDOM_COLOR again")
        await sdk.set_random_color()
        await asyncio.sleep(2)
        await take_snapshot("random_color_2")
        
        # 4. Random Sequence
        print("Triggering RANDOM_COLOR_SEQUENCE")
        await sdk.random_color_sequence()
        await asyncio.sleep(2)
        await take_snapshot("random_sequence_start")
        await asyncio.sleep(5)
        await take_snapshot("random_sequence_running")
        
        # 5. Pattern Deletion (Side effect check)
        print("Testing delete_all_color_patterns")
        await sdk.delete_all_color_patterns()
        await asyncio.sleep(1)
        
        # Return to white for finish
        print("Returning to WHITE")
        await sdk.set_color(255, 255, 255)
        
    print("Verification script finished.")

if __name__ == "__main__":
    asyncio.run(verify())
