import asyncio
import struct
from ilumi_sdk import IlumiSDK, IlumiApiCmdType, IlumiConfigCmdType

def test_device_info_packet():
    sdk = IlumiSDK("AA:BB:CC:DD:EE:FF")
    sdk.network_key = 0x12345678
    sdk.seq_num = 0x10
    
    header = sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_GET_DEVICE_INFO)
    # 4-byte key (LE), 1-byte seq, 1-byte cmd
    expected_header = struct.pack("<I B B", 0x12345678, 0x10, 40)
    
    assert header == expected_header
    print("Device Info Header OK.")

def test_dfu_packet():
    sdk = IlumiSDK("AA:BB:CC:DD:EE:FF")
    sdk.network_key = 0x12345678
    sdk.seq_num = 0x20
    sdk.dfu_key = 0xAABBCCDD
    
    header = sdk._pack_header(IlumiApiCmdType.ILUMI_API_CMD_CONFIG)
    payload = struct.pack("<B 4B", IlumiConfigCmdType.ILUMI_CONFIG_ENTER_BOOTLOADER, 
                          0xDD, 0xCC, 0xBB, 0xAA)
    
    expected_full = struct.pack("<I B B", 0x12345678, 0x20, 65) + payload
    
    # In my SDK implementation:
    # payload = struct.pack("<B 4B", IlumiConfigCmdType.ILUMI_CONFIG_ENTER_BOOTLOADER, 
    #                       self.dfu_key & 0xFF, (self.dfu_key >> 8) & 0xFF, 
    #                       (self.dfu_key >> 16) & 0xFF, (self.dfu_key >> 24) & 0xFF)
    
    # Let's verify our manual construction matches
    assert expected_full == header + payload
    print("DFU Packet OK.")

if __name__ == "__main__":
    test_device_info_packet()
    test_dfu_packet()
