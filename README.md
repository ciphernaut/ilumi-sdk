# Ilumi Smart Bulb Python SDK

This repository provides a Python interface for controlling Ilumi Smart Bulbs via Bluetooth Low Energy (BLE). It has been reverse-engineered from the official Ilumi Android App to bypass initial pairing requirements and communicate directly with the bulb's GATT characteristics.

## Prerequisites

- Linux with a Bluetooth adapter
- Python 3.x
- `bleak` library for BLE communication

## Setup

1. **Set up a virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install bleak
   ```

2. **Enroll the Bulb (First Time Only):**
   Before you can control the bulb, you need to enroll your machine to it. This script will discover your bulb, assign it a network key, and save the session configuration (including the anti-replay sequence number) to `ilumi_config.json`.
   ```bash
   python3 enroll.py
   ```

## Usage

Once enrolled, you can use the provided simple scripts to control the bulb:

- **Turn On / Off:**
  ```bash
  python3 on.py
  python3 off.py
  ```

- **Set Color (Red, Green, Blue, White [optional], Brightness [optional]):**
  ```bash
  # Set to green
  python3 color.py 0 255 0
  
  # Set to red at very low brightness (25/255)
  python3 color.py 255 0 0 0 25
  ```

- **Predefined Whites & Effects:**
  Use `whites.py` for static profiles and `effects.py` for animations. Both scripts will output a **JSON array** of available modes if called without arguments.

  ```bash
  # List all available white profiles
  python3 whites.py
  
  # Set the early_morning profile
  python3 whites.py early_morning
  
  # List all available animations
  python3 effects.py
  
  # Play the fireworks animation
  python3 effects.py fireworks
  ```

### Meltdown Effects (Custom)
We've added custom high-intensity effects:
- **core_breach**: Trigger via `python3 whites.py core_breach`. Uses the bulb's hardware flicker mode for an unstable molten orange glow.
- **radiation_leak**: Trigger via `python3 effects.py radiation_leak`. A rapid (100ms) strobe that alternates between toxic green and ionizing cyan.

## Advanced Integrations

This SDK supports bypassing the standard BLE acknowledgement sequence (using `write_without_response`) to achieve high-throughput, UDP-like streaming to the bulb (upwards of ~20 frames per second). 

### Live Streaming & Audio Reactivity
- **Test Stream:** Run a 20 FPS high-speed color sweep:
  ```bash
  python3 stream.py --fps 20 --duration 10
  ```
- **Audio Visualizer:** Maps your system microphone's bass to Red and treble to Blue in real-time.
  ```bash
  pip install sounddevice soundfile numpy scipy
  python3 audio_stream.py
  ```

### Smart Home Ecosystems (MQTT)
Integrate the bulb seamlessly into **Home Assistant** (or OpenHAB/Node-RED) using the MQTT protocol.
- **MQTT Bridge:** Runs a persistent Bluetooth connection and translates standard Home Assistant JSON commands to lightning-fast SDK calls. The bulb will automatically appear in Home Assistant via MQTT Auto-Discovery.
  ```bash
  pip install paho-mqtt
  python3 mqtt_bridge.py --broker [YOUR_MQTT_IP_ADDRESS]
  ```

### Professional Lighting Software (Art-Net DMX)
Control the bulb natively using professional lighting consoles and VJ software (like QLC+, Resolume, and SoundSwitch).
- **Network DMX Interface:** Listens for standard Art-Net UDP Packets (`OpDmx`) on Port `6454` and maps DMX channels 1-4 directly to the bulb's R, G, B, and W LEDs.
  ```bash
  python3 artnet_stream.py --universe 0 --channel 1
  ```

## Troubleshooting
If animations don't play:
1.  **Protocol Fix**: Ensure `IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN` is set to `7` and `START_COLOR_PATTERN` is set to `8` in `ilumi_sdk.py`.
2.  **Explicit Start**: `effects.py` handles both uploading and triggering the animation pattern.

## Permissions & Debugging
Refer to `ENABLEMENT.md` for Bluetooth permission setup and HCI snoop log gathering instructions. For protocol captures, you can uncomment the "observing mode" loop in `effects.py` to keep the connection alive.
