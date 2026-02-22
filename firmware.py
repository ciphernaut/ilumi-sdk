import asyncio
import argparse
import sys
import json
from ilumi_sdk import IlumiSDK
import ilumi_api

async def check_version(mac):
    async with IlumiSDK(mac) as sdk:
        print(f"Fetching device info for {mac}...")
        info = await sdk.get_device_info()
        if info:
            print("\nDevice Information:")
            print(json.dumps(info, indent=4))
            
            # Check for updates
            print("\nChecking for firmware updates...")
            latest = ilumi_api.get_latest_firmware(info['model_number'])
            if latest:
                latest_ver = latest.get("versionNumber")
                current_ver = info['firmware_version']
                
                print(f"Current version: {current_ver}")
                print(f"Latest version:  {latest_ver} ({latest.get('version')})")
                
                if latest_ver > current_ver:
                    print("\n[!] A NEW FIRMWARE VERSION IS AVAILABLE!")
                    print(f"Release Notes: {latest.get('releaseNotes', 'N/A')}")
                else:
                    print("\nFirmware is up to date.")
            else:
                print("Could not retrieve latest firmware info from server.")
                
            return info
        else:
            print("Failed to retrieve device information.")
            return None

async def trigger_dfu(mac):
    async with IlumiSDK(mac) as sdk:
        print(f"Fetching device info for {mac} to check platform...")
        info = await sdk.get_device_info()
        if not info:
            print("Failed to detect device platform. Aborting.")
            return

        is_nordic = info['model_number'] in [65, 81]
        print(f"Detected platform: {'Nordic (Gen2)' if is_nordic else 'Broadcom (Gen1)'}")

        print("WARNING: Entering DFU mode will make the bulb stop responding to normal commands.")
        print("The bulb will reboot into the bootloader and may use a different MAC address.")
        
        await sdk.enter_dfu_mode()
        print("\nCommand sent. Device should be in update mode now.")

async def update_firmware(mac, file_path):
    # This is a high-level routine that would perform the actual update
    async with IlumiSDK(mac) as sdk:
        info = await sdk.get_device_info()
        if not info:
            print("Could not retrieve device info.")
            return

        model = info['model_number']
        is_nordic = model in [65, 81]

        with open(file_path, "rb") as f:
            firmware_data = f.read()

        if is_nordic:
            print("Gen2 (Nordic) update required.")
            print("Step 1: Triggering DFU mode...")
            await sdk.enter_dfu_mode()
            print("Step 2: Flash the firmware using a Nordic DFU library.")
            print("Example: nrfutil dfu ble -pkg firmware.zip -address [mac]")
            print("Note: The MAC address in DFU mode is usually [original_mac] + 1.")
        else:
            print("Gen1 (Broadcom) update required.")
            print("Implementing custom Gen1 FOTA protocol...")
            # Gen1 protocol skeleton:
            # 1. Send Header (Offset 4-12 of firmware file)
            # 2. bulb.write_ftoa_header(firmware_data[4:12])
            # 3. Enter FOTA mode
            # 4. Send data in 16-byte blocks with 2-byte index prefix
            print("This protocol is complex and requires careful block-by-block handling.")
            print("Refer to Gen1FirmwareUpdater.java for the full state machine.")

def main():
    parser = argparse.ArgumentParser(description="Ilumi Firmware Utility")
    parser.add_argument("command", choices=["version", "dfu", "update"], help="Command to run")
    parser.add_argument("--mac", help="MAC address of the bulb (falls back to enrollment config)")
    parser.add_argument("--file", help="Path to firmware file (required for 'update')")
    parser.add_argument("--force", action="store_true", help="Force DFU trigger without confirmation")

    args = parser.parse_args()

    if args.command == "version":
        asyncio.run(check_version(args.mac))
    elif args.command == "dfu":
        if not args.force:
            print("Confirmation required for DFU. Use --force to proceed.")
            sys.exit(1)
        asyncio.run(trigger_dfu(args.mac))

if __name__ == "__main__":
    main()
