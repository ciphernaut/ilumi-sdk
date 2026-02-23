# Security Policy

This document outlines the security assumptions, critical components, and best practices for deploying the Ilumi Python SDK in a real-world environment.

## 1. Mesh Topology Exposure
**Risk Level:** High
The SDK stores the mesh configuration, including the plaintext `network_key` and MAC addresses, in `ilumi_config.json`. If this file is accessed by an unauthorized user on the local machine or via an exposed container, they will be able to hijack the entire Bluetooth mesh network without needing to re-enroll.
- **Mitigation**: The SDK enforces `chmod 660` on this configuration file automatically, ensuring only the owner and users in the same group can read or write to it. It is your responsibility to ensure the host machine's user accounts are properly segregated.

## 2. Network Interface Binding
**Risk Level:** Medium
The SDK contains network listeners, such as the Art-Net DMX receiver (`artnet_stream.py`), which open UDP ports to listen for high-speed color updates.
- **Mitigation**: By default, network interfaces bind strictly to `127.0.0.1` (localhost). If you wish to accept Art-Net packets from external devices on your LAN, you must explicitly use the `--bind 0.0.0.0` argument, which exposes the service to the network.

## 3. MQTT Broker Authentication
**Risk Level:** High
The `mqtt_bridge.py` service connects to a Home Assistant MQTT broker to expose the bulbs as auto-discovered devices. Currently, the bridge script is engineered for rapid local deployment and **does not hardcode username/password authentication mechanisms**.
- **Mitigation**: If you are deploying this in a production ecosystem, you should rely on your MQTT Broker's infrastructure to enforce network-level security (e.g., placing the bridge and broker on a secured VLAN) or wrap the `mqtt_bridge.py` execution within a secure tunneling architecture. Do not expose the MQTT broker publicly without adding authentication to the Python client execution logic natively.

## 4. Dangerous Commands & Disruption Risks
**Risk Level:** Moderate to Critical
There are commands within the SDK capable of disrupting your setup or permanently altering the bulbs.
- **Moderate Risk (`unenroll.py`)**: Factory resets the bulbs, destroying their mesh keys. This will not brick the device, but it is highly disruptive as it requires physically re-identifying and running the entire `enroll.py` workflow again.
- **Critical Risk (`firmware.py --enter-dfu`)**: Forces the bulbs into Nordic DFU bootloader mode. If a valid firmware image is not successfully flashed via Nordic tools afterward, the bulb may remain stuck in the bootloader (bricked state).
- **Mitigation**: These scripts require an explicit interactive confirmation prompt (or a strict `--force` flag automation override) before execution to prevent accidental triggering by automated endpoints or AI agents.

## 5. Input Payload Clamping
**Risk Level:** Low
Automated downstream controllers or AI agents may attempt to pass invalid color variables to the SDK (e.g., a Red absolute value of `300` or `-50`).
- **Mitigation**: The core SDK (`ilumi_sdk.py`) intercepts all color and brightness payloads before they are byte-packed and clamps them strictly between `0` and `255` to prevent buffer overflows or undefined bulb behavior.
