import asyncio
import os
from bumble_sdk import get_shared_device, shutdown_bumble

async def main():
    transport_spec = os.environ.get("ILUMI_BT_TRANSPORT", "usb:0")
    try:
        device = await get_shared_device(transport_spec)
        print(f"Scanning for ALL BLE devices on {transport_spec}...")
        
        found = set()

        def on_advertisement(adv):
            addr = str(adv.address)
            if addr not in found:
                found.add(addr)
                name = adv.data.get(0x09) or ""
                if isinstance(name, bytes):
                    name = name.decode('utf-8', errors='ignore')
                print(f"Device: {addr} | Name: {name} | RSSI: {adv.rssi}")

        device.on('advertisement', on_advertisement)
        await device.start_scanning()
        await asyncio.sleep(20.0)
        await device.stop_scanning()
        
        print(f"\nScan complete. Found {len(found)} unique devices.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await shutdown_bumble()

if __name__ == "__main__":
    asyncio.run(main())
