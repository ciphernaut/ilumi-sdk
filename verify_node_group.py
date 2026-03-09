import asyncio
import logging
from ilumi_sdk import IlumiSDK
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_node_group")

async def main():
    # Use the 'computer' bulb for verification
    sdk = IlumiSDK("FD:66:EE:0A:7B:67")
    print(f"Connecting to {sdk.mac_address}...")
    
    async with sdk:
        print("\n--- Node & Group Management Verification ---")
        
        # 1. Get Node ID
        node_id = await sdk.get_node_id()
        print(f"[GET_NODE_ID] Current Node ID: {node_id}")
        
        # 2. Get Group IDs (Baseline)
        groups = await sdk.get_group_ids()
        print(f"[GET_GROUP_IDS] Current Group IDs: {groups}")
        
        # 3. Add Group ID
        test_group_id = 0xCAFE
        print(f"[ADD_GROUP_ID] Adding group {hex(test_group_id)}...")
        await sdk.add_group_id(test_group_id)
        
        # 4. Verify Add
        groups_after_add = await sdk.get_group_ids()
        print(f"[GET_GROUP_IDS] Group IDs after add: {groups_after_add}")
        
        if test_group_id in groups_after_add:
            print("SUCCESS: Group added correctly.")
        else:
            print("FAILURE: Group not found after add.")
            
        # 5. Delete Group ID
        print(f"[DEL_GROUP_ID] Deleting group {hex(test_group_id)}...")
        await sdk.del_group_id(test_group_id)
        
        # 6. Verify Delete
        groups_after_del = await sdk.get_group_ids()
        print(f"[GET_GROUP_IDS] Group IDs after del: {groups_after_del}")
        
        if test_group_id not in groups_after_del:
            print("SUCCESS: Group deleted correctly.")
        else:
            print("FAILURE: Group still found after del.")
            
        # 7. Test Clear All (Optional/Caution)
        # We won't clear all unless we want to nukes everything. 
        # But let's test it if the list is small or if the user is okay.
        # For now, we'll skip clear_all_group_ids to avoid messing up existing configs.
        
        print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
