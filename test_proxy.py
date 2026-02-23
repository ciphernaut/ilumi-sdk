import asyncio
import struct
import config
from ilumi_sdk import IlumiSDK, IlumiApiCmdType

async def test_proxy():
    network_key = config.get_config("network_key", 0)
    all_bulbs = config.get_config("bulbs", {})
    if len(all_bulbs) < 2:
        print("Need at least 2 bulbs to test proxy.")
        return

    mac_list = list(all_bulbs.keys())
    connected_mac = mac_list[0]
    target_macs = mac_list[:2]
    
    r, g, b_val, w, brightness = 0, 0, 255, 0, 255
    inner_cmd = struct.pack("<B I", IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP, network_key)
    
    sdk = IlumiSDK(connected_mac)
    inner_cmd_full = sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_NEED_RESP)
    inner_payload = struct.pack("<B B B B B B B", r, g, b_val, w, brightness, 0, 0)
    full_inner_msg = inner_cmd_full + inner_payload

    service_type_ttl = 15 # Default TTL
    addr_amount = len(target_macs)
    proxy_data_len = (addr_amount * 6) + len(full_inner_msg)

    proxy_cmd = sdk._pack_header(33) # ILUMI_API_CMD_PROXY_MSG = 33
    
    proxy_header = struct.pack("<B B H", service_type_ttl, addr_amount, proxy_data_len)
    
    mac_bytes = bytearray()
    for mac in target_macs:
        # Standard order
        mac_parts = [int(x, 16) for x in mac.split(':')]
        mac_bytes.extend(bytes(mac_parts))
        
    final_payload = proxy_cmd + proxy_header + mac_bytes + full_inner_msg
    
    print(f"Connecting to {connected_mac}...")
    async with sdk:
        print(f"Sending proxy message to targets: {target_macs}")
        print(f"Payload: {final_payload.hex()}")
        # Proxy packets are large, so use chunked command
        await sdk._send_chunked_command(final_payload)
        
    print("Done")

if __name__ == "__main__":
    asyncio.run(test_proxy())
