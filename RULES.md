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

## 4. Hardware Fading
- `color.py`, `whites.py`, `on.py`, and `off.py` utilize the bulb's native hardware fading API (`set_color_smooth`) for premium transitions.
- **Fading defaults:** Fading is enabled by default (e.g., 500ms) **only** when targeting a single bulb or when using the `--mesh` flag. If targeting multiple bulbs sequentially (without `--mesh`), fading defaults to `0ms` (instant) to prevent uncoordinated "popcorning" delays.
- If you need to snap a bulb to a specific color instantly, append `--no-fade` to force the `0ms` override.

## 5. Mesh Proxy Routing (Experimental)
- The `--mesh` flag can be used to route commands for an entire `--group` or `--all` bulbs through a single connected bulb, which broadcasts the color packet to the rest of the targets simultaneously over the Bluetooth Mesh.
- **IMPORTANT:** Mesh proxy routing is currently broken/unreliable. Do **not** use `--mesh` by default when executing commands on multiple bulbs unless the user explicitly requests it.
- When explicitly used, the `--mesh` flag prevents sequence delays ("popcorning"). Because mesh broadcasts can be unreliable natively, scripts use a `--retries` argument (default: 3) to automatically re-transmit the proxy command a few times.
