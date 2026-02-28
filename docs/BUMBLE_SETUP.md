# Bumble Bluetooth Setup

This document describes how to set up the Bumble Bluetooth backend for the Ilumi SDK on Linux.

## Requirements

1.  **Dedicated Bluetooth Dongle**: Bumble works best with a dedicated USB Bluetooth dongle. This avoids conflicts with the system's `bluetoothd` (BlueZ).
2.  **Bumble Library**: Installed via `pip install bumble pyusb`.

## Identifying the Dongle

Run the following command to find the Bumble transport name for your dongle:

```bash
./venv/bin/bumble-usb-probe
```

Look for a device with a "[Bluetooth]" subclass. Example output:
```text
ID 0A12:0001
  Bumble Transport Names: usb:0 or usb:0A12:0001
  Bus/Device:             001/002
  Class:                  Wireless Controller
  Subclass/Protocol:      1/1 [Bluetooth]
```
The transport name is `usb:0`.

## Permissions (udev Rules)

By default, Linux prevents non-root users from accessing raw USB devices. If you see `LIBUSB_ERROR_ACCESS [-3]`, you need to set up a udev rule.

1.  **Create the rule file**:
    Create `/etc/udev/rules.d/99-bumble-bluetooth.rules` with the following content (adjust `idVendor` and `idProduct` to match your device from `bumble-usb-probe`):

    ```udev
    SUBSYSTEM=="usb", ATTRS{idVendor}=="0a12", ATTRS{idProduct}=="0001", MODE="0666", DRIVERS=="usb"
    ```
    *(Note: Using `ATTRS` instead of `ATTR` is often more reliable on modern systems).*

2.  **Reload udev**:
    ```bash
    sudo udevadm control --reload-rules && sudo udevadm trigger
    ```

3.  **Reconnect**: Unplug and replug the dongle.

## Usage

Once configured, enable Bumble in the SDK using environment variables:

```bash
ILUMI_USE_BUMBLE=1 ILUMI_BT_TRANSPORT=usb:0 python3 on.py --all
```

## Troubleshooting

### Kernel Driver Conflicts
If Bumble fails to claim the device even with the correct permissions, the kernel's `btusb` driver might be holding it. You may need to stop the bluetooth service:
```bash
sudo systemctl stop bluetooth
```
Or use `rfkill` to block the device.

### Manual Unbinding
Even with the correct permissions, the kernel's `btusb` driver may still be holding the device. Bumble now tries to auto-detach the driver (via `?detach=true` in the transport spec), but if that fails, you can manually unbind it:

1. **Find the device path** (using `lsusb -t`):
   ```bash
   # Look for the port bound to 'btusb' for your 0a12:0001 device
   lsusb -t
   ```
   Example: `Port 002: Dev 009, If 0, Class=Wireless, Driver=btusb` -> Path is `1-2:1.0` (Bus 1, Port 2, Interface 0).

2. **Unbind it**:
   ```bash
   echo "1-2:1.0" | sudo tee /sys/bus/usb/drivers/btusb/unbind
   echo "1-2:1.1" | sudo tee /sys/bus/usb/drivers/btusb/unbind
   ```
