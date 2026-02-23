import asyncio
from bleak import BleakScanner
from ilumi_sdk import IlumiSDK, ILUMI_SERVICE_UUID
import config
import random

async def main():
    print("Scanning for Ilumi bulbs in the area (5 seconds)...")
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
    
    ilumi_devices = []
    # discover(return_adv=True) returns a dict of {mac_address: (BLEDevice, AdvertisementData)}
    for mac, (device, adv_data) in devices.items():
        # Check if it advertises the Ilumi Service UUID or has 'ilumi' in the name
        uuids = [u.lower() for u in adv_data.service_uuids]
        if ILUMI_SERVICE_UUID.lower() in uuids or (device.name and "ilumi" in device.name.lower()):
            # Filter out devices avoiding duplicates from BLE scanner bounce
            if device.address not in [b.address for b in ilumi_devices]:
                ilumi_devices.append(device)

    if not ilumi_devices:
        print("No Ilumi bulbs found.")
        return

    print(f"Found {len(ilumi_devices)} potential Ilumi bulb(s).")
    
    # Ensure a global mesh network key exists or create one
    network_key = config.get_config("network_key")
    if not network_key:
        network_key = random.randint(1000, 999999)
        config.update_config("network_key", network_key)
        print(f"Generated new global Mesh Network Key: {network_key}")
    else:
        print(f"Using existing global Mesh Network Key: {network_key}")

    existing_bulbs = config.get_all_bulbs()

    for idx, device in enumerate(ilumi_devices):
        mac = device.address
        print(f"\n--- Bulb {idx+1}/{len(ilumi_devices)}: {mac} ---")
        
        if mac in existing_bulbs:
            existing_data = existing_bulbs[mac]
            print(f"Already enrolled as '{existing_data.get('name')}' in group '{existing_data.get('group')}'.")
            re_enroll = input("Do you want to re-enroll and rename this bulb? (y/N): ").strip().lower()
            if re_enroll != 'y':
                print("Skipping.")
                continue
            
        print("Connecting to bulb to identify it...")
        sdk = IlumiSDK(mac)
        try:
            async with sdk:
                print("Flashing bulb GREEN for identification...")
                # Flash Green at max brightness so it's very obvious
                await sdk.set_color_fast(0, 255, 0, 0, 255)
                
                name = input(f"Enter a name for this bulb (e.g. 'kitchen') [Leave blank to skip]: ").strip()
                if not name:
                    print("Skipping.")
                    await sdk.set_color_fast(0, 0, 0, 0, 0)
                    continue
                    
                group = input(f"Enter a group for this bulb (e.g. 'lounge') [Leave blank for none]: ").strip()
                
                print(f"Setting up bulb '{name}'...")
                # Save config and get the new generated node_id
                node_id = config.add_bulb(mac, name, group)
                
                # Commission the bulb into our network mesh
                success = await sdk.commission(network_key, 1, node_id)
                if success:
                    print(f"Successfully commissioned '{name}'!")
                    # Flash blue to indicate success, then turn off
                    await sdk.set_color_fast(0, 100, 255, 0, 255)
                    await asyncio.sleep(0.5)
                    await sdk.set_color_fast(0, 0, 0, 0, 0)
                else:
                    print(f"Failed to commission '{name}' (SDK commission returned false).")
        except Exception as e:
            print(f"Could not connect to {mac}: {e}")

    print("\nEnrollment phase complete. You can now use the wrapper scripts with --name or --group.")

if __name__ == "__main__":
    asyncio.run(main())
