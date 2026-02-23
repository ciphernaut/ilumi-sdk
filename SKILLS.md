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

## 3. Core SDK & GAI Integration

For complex logic or persistent control, AI agents should use the `IlumiSDK` class in `ilumi_sdk.py`.

### AI Discoverability
- **Discovery**: Use `await IlumiSDK.discover()` to find bulbs.
- **Connection**: Always use `async with IlumiSDK(mac_address) as sdk:` for reliable communication.
- **Function Calling**: Use `tools.json` to understand the standard parameter schemas for bulb control.

### GAI Readiness
- **Logging**: Internal SDK logs are sent to `stderr`.
- **JSON Output**: CLI tools prioritize parsable JSON on `stdout`.
- **Safety**: Raw commands are protected by `_send_raw_command` with explicit "Brick Clause" warnings in docstrings.

### Protocol Knowledge
Deep technical details on the GATT protocol (sequence numbering, proxy endianness, etc.) can be found in `PROTOCOL.md`.
