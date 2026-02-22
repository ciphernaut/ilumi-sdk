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

- **Turn On:**
  ```bash
  python3 on.py
  ```

- **Turn Off:**
  ```bash
  python3 off.py
  ```

- **Set Color (Red, Green, Blue, White [optional]):**
  The `color.py` script takes RGB(W) values between 0 and 255.
  ```bash
  # Set to green
  python3 color.py 0 255 0

  # Set to red
  python3 color.py 255 0 0

  # Set to white
  python3 color.py 255 255 255 255
  ```

## Permissions & Debugging

If you run into Bluetooth permission errors during execution, or you want to debug the raw packet traffic (such as gathering Android HCI snoop logs), refer to the `ENABLEMENT.md` file in this repository for instructions.
