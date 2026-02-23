import asyncio
from ilumi_sdk import IlumiSDK
import config
import os

async def main():
    comp_mac = config.resolve_targets(target_name="computer")[0]
    four_mac = config.resolve_targets(target_name="four")[0]
    
    # 1. connect to computer and send mesh proxy to four
    print(f"Connecting to computer ({comp_mac}) to send proxy TURN ON to four...")
    sdk_comp = IlumiSDK(comp_mac)
    
    async with sdk_comp:
        print(f"Sending proxy turn_on command -> proxying through {comp_mac} to {four_mac}")
        # Note: We send to targets=[four_mac]. We avoid sending to comp_mac itself.
        await sdk_comp.turn_on(targets=[four_mac])
        # Wait for the mesh to forward the packet over GATT -> BLE Mesh
        await asyncio.sleep(2.0)
        
    os.system('sg video -c "fswebcam --no-banner /projects/antigravity/ilumi/tests/webcam_snapshot_test.jpg"')
    print("Check webcam_snapshot_test.jpg")
    
if __name__ == "__main__":
    asyncio.run(main())
