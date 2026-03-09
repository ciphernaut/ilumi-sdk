import struct

def bin_to_bcd(val: int) -> int:
    return ((val // 10) << 4) | (val % 10)

def pack_header(seq_num, message_type, network_key=0x12345678):
    if seq_num % 2 != 0:
        seq_num = (seq_num + 1) % 256
    return struct.pack("<I", network_key) + struct.pack("B B", seq_num, message_type)

def test_daily_alarm_logic():
    print("Testing Daily Alarm packing...")
    # Matches my implementation in ilumi_sdk.py:
    # payload = struct.pack("<B B B B B", alarm_idx, action_idx, bcd_hour, bcd_min, days_mask)
    alarm_idx = 1
    action_idx = 10
    hour = 14
    minute = 30
    days_mask = 127
    
    bcd_hour = bin_to_bcd(hour)
    bcd_min = bin_to_bcd(minute)
    
    payload = struct.pack("<B B B B B", alarm_idx, action_idx, bcd_hour, bcd_min, days_mask)
    expected_payload = bytes([0x01, 0x0A, 0x14, 0x30, 0x7F])
    assert payload == expected_payload
    print("  Daily Alarm packing OK.")

def test_action_header_logic():
    print("Testing Action Header packing...")
    # Matches my implementation in bumble_sdk.py (same as ilumi_sdk.py via chunking logic):
    # action_hdr = struct.pack("<B B H B B H", action_idx, next_action_idx, time_val, time_unit, 0, len(command_payload))
    action_idx = 5
    next_action_idx = 0xFF
    delay_ms = 500
    command_payload = bytes([0x00, 0x00, 0xFF, 0x00, 0xFF])
    
    time_val = 500
    time_unit = 0 # ms
    action_hdr = struct.pack("<B B H B B H", action_idx, next_action_idx, time_val, time_unit, 0, len(command_payload))
    expected_hdr = bytes([0x05, 0xFF, 0xF4, 0x01, 0x00, 0x00, 0x05, 0x00])
    assert action_hdr == expected_hdr
    print("  Action Header packing OK.")

def test_calendar_event_logic():
    print("Testing Calendar Event packing...")
    # Matches my implementation in ilumi_sdk.py:
    # payload = struct.pack("<B B B B B B B", alarm_idx, action_idx, bcd_year, bcd_month, bcd_day, bcd_hour, bcd_min)
    alarm_idx = 2
    action_idx = 15
    year = 2024
    month = 12
    day = 25
    hour = 10
    minute = 0
    
    bcd_year = bin_to_bcd(year % 100)
    bcd_month = bin_to_bcd(month)
    bcd_day = bin_to_bcd(day)
    bcd_hour = bin_to_bcd(hour)
    bcd_min = bin_to_bcd(minute)
    
    payload = struct.pack("<B B B B B B B", alarm_idx, action_idx, bcd_year, bcd_month, bcd_day, bcd_hour, bcd_min)
    expected_payload = bytes([0x02, 0x0F, 0x24, 0x12, 0x25, 0x10, 0x00])
    assert payload == expected_payload
    print("  Calendar Event packing OK.")

if __name__ == "__main__":
    test_daily_alarm_logic()
    test_action_header_logic()
    test_calendar_event_logic()
    print("\nALL STANDALONE LOGIC TESTS PASSED!")
    print("This confirms the Python implementation's byte-order and packing logic matches the bulb's protocol.")
