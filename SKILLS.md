---
name: ilumi_mesh_management
description: Manage Ilumi Smart Bulb fleets via Bluetooth Low Energy Mesh
---

# Ilumi Mesh Management Skill

This skill allows you to map and control a user's physical Ilumi Smart Bulb mesh network natively through the CLI wrappers.

## 1. Environment Discovery
Always start your interaction by pulling the `ilumi_config.json` via file read. 
Parse the `bulbs` array. This represents the absolute truth of the physical space you are controlling.

Example Configuration:
```json
{
    "bulbs": {
        "E2:B0:F7:F4:50:60": {"name": "one", "group": "nanobot", "node_id": 1},
        "F8:DD:7A:AA:4B:0D": {"name": "four", "group": "organobot", "node_id": 4}
    }
}
```

## 2. Execution Design 
When the user asks for a lighting change, map their request to the topology above.
- If they ask to turn off the "nanobot" area, you do not need to iterate over bulbs `one`, `two` and `three` individually.
- The SDK inherently supports group targeting.

Your command should strictly use the routing args: `--name`, `--group`, `--all`, `--mac`, `--stream`, or `--proxy`.

**Critical Efficiency Rule:** When acting on behalf of the user within an interactive Shell, you **MUST** use the `--json` output flag to conserve your token ingestion.

### Example Executions
Action: Set the "organobot" group to Red.
```bash
python3 color.py 255 0 0 --group organobot --json
```

Action: Turn off the entire house.
```bash
python3 off.py --all --json
```

Action: Trigger a custom effect on bulb "four".
```bash
python3 effects.py radiation_leak --name four --json
```

## 3. Core SDK & AI Agent Integration

For direct manipulation or complex logic within an agentic workflow, use the `IlumiSDK` class in `ilumi_sdk.py`.

### Direct SDK Usage Example
Agents should use the asynchronous context manager to ensure safe connection handling and multiplexing.

```python
import asyncio
from ilumi_sdk import IlumiSDK

async def main():
    # Targets can be resolved from ilumi_config.json
    mac = "E2:B0:F7:F4:50:60"
    
    async with IlumiSDK(mac) as sdk:
        # Get current state
        color = await sdk.get_bulb_color()
        print(f"Current color: {color}")
        
        # Set a new color with hardware fading
        await sdk.set_color_smooth(0, 255, 0, duration_ms=1000)
        
        # Query hardware info
        info = await sdk.get_device_info()
        print(f"Firmware: {info['firmware_version']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Agent Discovery Guidelines
- **Configuration Parsing**: Always read `ilumi_config.json` FIRST to map human-readable names to MAC addresses.
- **Connection Stewardship**: Use `async with IlumiSDK(mac) as sdk:` to prevent "InProgress" errors on the HCI adapter.
- **Token Efficiency**: When running CLI tools, use the `--json` flag to minimize stdout verbosity.
- **Mesh Logic**: Use `sdk.send_proxy_message()` only when sequential `--stream` control is insufficient for the required latency.

### Protocol Knowledge
Deep technical details on the GATT protocol (sequence numbering, proxy endianness, etc.) can be found in [PROTOCOL.md](./PROTOCOL.md).
