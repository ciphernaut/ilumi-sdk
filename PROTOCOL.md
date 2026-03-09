# Ilumi GATT Protocol Reference

This document provides a technical overview of the reverse-engineered Bluetooth Low Energy (BLE) protocol used to control Ilumi Smart Bulbs.

## Service & Characteristic

- **Service UUID**: `f000f0c0-0451-4000-b000-000000000000`
- **Characteristic UUID**: `f000f0c1-0451-4000-b000-000000000000`

All commands and notifications are exchanged via this single GATT characteristic.

## Packet Structure

Every packet sent to the bulb starts with a **6-byte header**.

| Offset | Type | Description |
|---|---|---|
| 0-3 | `uint32_le` | **Network Key**: Plaintext key used for mesh identification. Defaults to `0` for uncommissioned bulbs. |
| 4 | `uint8` | **Sequence Number**: Must be an **even number**. Increments by 2 for each command to prevent replay attacks. |
| 5 | `uint8` | **Command Type**: The ID of the command being executed. |

## Data Chunking

The BLE Maximum Transmission Unit (MTU) for Ilumi bulbs is limited. Payloads larger than **20 bytes** must be split into 10-byte chunks using the `DATA_CHUNK` (52) command.

### Chunk Structure
- **Total Length** (`uint16_le`): Total size of the original un-chunked payload.
- **Offset** (`uint16_le`): Current byte offset in the original payload.
- **Data** (10 bytes): The actual payload fragment.

## Command Definitions

### 0: SET_COLOR (Fast)
Sets the bulb color without requiring a BLE acknowledgment.
- **Payload (7 bytes)**: `R, G, B, W, Brightness, 0, 0` (All `uint8`)

### 4: TURN_ON
- **Payload (4 bytes)**:
  - `delay` (`uint16_le`): Delay before turning on (ms).
  - `transit` (`uint16_le`): Fade-in duration (ms).

### 5: TURN_OFF
- **Payload (4 bytes)**:
  - `delay` (`uint16_le`): Delay before turning off (ms).
  - `transit` (`uint16_le`): Fade-out duration (ms).

### 28: PROXY_MSG (Mesh)
Routes a command through a proxy bulb to other nodes in the mesh.
- **Payload**:
  - `ttl` (`uint8`): Time-to-live / Service type.
  - `count` (`uint8`): Number of target MAC addresses.
  - `len` (`uint16_le`): Length of inner payload.
  - `mac` (6 bytes): Target MAC address in **Little-Endian** format.
  - `inner_payload`: The actual command (including header) to be executed by the target.

### 37: SET_COLOR_SMOOTH
Fades to a color with high precision.
- **Payload (11 bytes)**:
  - `time_val` (`uint16_le`): Duration value.
  - `time_unit` (`uint8`): `0` for ms, `1` for seconds.
  - `R, G, B, W, Brightness, 0` (`uint8`)
  - `delay_sec` (`uint8`): Delay before start (seconds).

### 40: GET_DEVICE_INFO
Queries the bulb for hardware/firmware metadata.
- **Notification Response (10 bytes payload)**:
  - `firmware_version` (`uint16_le`)
  - `bootloader_version` (`uint16_le`)
  - `commission_status` (`uint8`)
  - `model_number` (`uint8`)
  - `reset_reason` (`uint16_le`)
  - `ble_stack_version` (`uint16_le`)
