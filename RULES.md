# Ilumi SDK - Agent Rules

When assisting users with the Ilumi Python SDK, you **MUST** adhere to the following hardware and topology constraints.

## 1. Network Constraints
- **Sequential Connections Only**: The physical Bluetooth host controller will crash with an `[org.bluez.Error.InProgress]` error if multiple `BleakClient` instances attempt to connect simultaneously.
- **NEVER** run `asyncio.gather` on `IlumiSDK` instantiation or `turn_on`/`set_color` commands directly over multiple MAC addresses.
- **ALWAYS** use the built-in wrapper scripts (`on.py`, `color.py`, etc) or the `execute_on_targets(targets, coro_func)` utility inside `ilumi_sdk.py`, as they are specifically designed to safely iterate and multiplex commands over the mesh fleet natively.

## 2. Configuration & Topology Inference
- The mesh configuration is defined in `ilumi_config.json`.
- Before suggesting commands to the user, ensure you read `ilumi_config.json` to understand what groups and names the user has set up. 
- Try to use `--group` targeting where applicable to minimize the number of direct MAC inputs you need to process.
  Example:
  ```bash
  python3 whites.py core_breach --group lounge
  ```

## 3. Automation Output Extraction
- When you execute SDK commands on behalf of the user, **ALWAYS append the `--json` flag** to the command.
- This suppresses human-readable stdout logging (which consumes unnecessary tokens) and instead emits a single, raw JSON dict confirming the execution status across all resolved targets.
  Example:
  ```bash
  python3 color.py 0 255 0 --name kitchen --json
  # Will cleanly output {"command": "set_color", "targets": ["FD:66:EE:..."], "results": {"FD:66:EE:...": {"success": true, "error": null}}}
  ```
