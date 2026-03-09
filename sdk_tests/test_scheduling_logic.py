import asyncio
import struct
from ilumi_sdk import IlumiSDK, IlumiApiCmdType
from unittest.mock import AsyncMock, patch

async def test_logic():
    sdk = IlumiSDK.__new__(IlumiSDK)
    sdk.mac_address = "AA:BB:CC:DD:EE:FF"
    sdk.network_key = 0x12345678
    sdk.seq_num = 0

    print("Testing bin_to_bcd...")
    assert sdk._bin_to_bcd(12) == 0x12
    assert sdk._bin_to_bcd(59) == 0x59

    print("Testing set_daily_alarm...")
    with patch.object(sdk, '_send_command', new_callable=AsyncMock) as mock_send:
        await sdk.set_daily_alarm(1, 14, 30, 127, 10)
        call_args = mock_send.call_args[0][0]
        assert len(call_args) == 11
        assert call_args[5] == IlumiApiCmdType.ILUMI_API_CMD_SET_DAILY_ALARM
        assert call_args[6] == 1      # alarmIdx
        assert call_args[7] == 10     # actionIdx
        assert call_args[8] == 0x14   # hour BCD
        assert call_args[9] == 0x30   # min BCD
        assert call_args[10] == 127   # weekDays

    print("Testing add_action...")
    cmd_payload = bytes([0x00, 0x00, 0xFF, 0x00, 0xFF])
    with patch.object(sdk, '_send_chunked_command', new_callable=AsyncMock) as mock_send:
        await sdk.add_action(5, cmd_payload, next_action_idx=0xFF, delay_ms=500)
        call_args = mock_send.call_args[0][0]
        assert len(call_args) == 19
        assert call_args[5] == IlumiApiCmdType.ILUMI_API_CMD_ADD_ACTION
        action_hdr = call_args[6:14]
        u = struct.unpack("<B B H B B H", action_hdr)
        assert u[0] == 5
        assert u[1] == 0xFF
        assert u[2] == 500
        assert u[3] == 0
        assert u[5] == 5

    print("Testing set_calendar_event...")
    with patch.object(sdk, '_send_command', new_callable=AsyncMock) as mock_send:
        # year=2024, month=12, day=25, hour=10, min=0
        await sdk.set_calendar_event(2, 2024, 12, 25, 10, 0, 15)
        call_args = mock_send.call_args[0][0]
        assert len(call_args) == 13
        assert call_args[5] == IlumiApiCmdType.ILUMI_API_CMD_SET_CALENDAR_EVENT
        assert call_args[6] == 2      # alarmIdx
        assert call_args[7] == 15     # actionIdx
        assert call_args[8] == 0x24   # year BCD
        assert call_args[9] == 0x12   # month BCD
        assert call_args[10] == 0x25  # day BCD
        assert call_args[11] == 0x10  # hour BCD
        assert call_args[12] == 0x00  # min BCD

    print("\nALL LOGIC TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_logic())
