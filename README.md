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

## Troubleshooting
If animations don't play:
1.  **Protocol Fix**: Ensure `IlumiApiCmdType.ILUMI_API_CMD_SET_COLOR_PATTERN` is set to `7` and `START_COLOR_PATTERN` is set to `8` in `ilumi_sdk.py`.
2.  **Explicit Start**: `effects.py` handles both uploading and triggering the animation pattern.

## Permissions & Debugging
Refer to `ENABLEMENT.md` for Bluetooth permission setup and HCI snoop log gathering instructions. For protocol captures, you can uncomment the "observing mode" loop in `effects.py` to keep the connection alive.
