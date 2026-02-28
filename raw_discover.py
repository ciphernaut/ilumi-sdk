import asyncio
import os
from bumble_sdk import get_shared_device, shutdown_bumble

async def main():
    transport_spec = os.environ.get("ILUMI_BT_TRANSPORT", "usb:0")
    device = await get_shared_device(transport_spec)
    print(f"Scanning for all BLE devices on {transport_spec}...")
    
    found = []

    def on_advertisement(adv):
        addr = str(adv.address)
        name = adv.data.get(0x09) or ""
        if isinstance(name, bytes):
            name = name.decode('utf-8', errors='ignore')
        
        rssi = adv.rssi
        if addr == "FD:66:EE:0A:7B:67" or "ilumi" in name.lower() or name.startswith("L0"):
            if not any(b["address"] == addr for b in found):
                found.append({"name": name, "address": addr, "rssi": rssi})
                print(f"Found: {name} [{addr}] RSSI: {rssi}")

    device.on('advertisement', on_advertisement)
    await device.start_scanning()
    await asyncio.sleep(10.0)
    await device.stop_scanning()
    
    print(f"\nScan complete. Found {len(found)} devices.")
    await shutdown_bumble()

if __name__ == "__main__":
    asyncio.run(main())
