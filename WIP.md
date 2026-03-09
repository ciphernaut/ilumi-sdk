# Work In Progress - Firmware Update Integration

## Current Status
- [x] **SDK Support**: Added `GET_DEVICE_INFO` and `CONFIG` commands to `ilumi_sdk.py`.
- [x] **Notification Handling**: Fixed response parsing for 4-byte response headers.
- [x] **Local Version Check**: Implemented `python3 firmware.py version` to report current firmware/model.
- [x] **DFU Trigger**: Implemented `python3 firmware.py dfu` to switch Gen2 bulbs to update mode.
- [x] **Platform Detection**: SDK automatically detects Gen1 (Broadcom) vs Gen2 (Nordic) devices.

## Local Version Check
- [x] Implemented `python3 firmware.py version` to report current firmware/model.
- [x] Implemented `python3 firmware.py dfu` to switch Gen2 bulbs to update mode.
- [x] Platform Detection: SDK automatically detects Gen1 (Broadcom) vs Gen2 (Nordic) devices.

## Decentralized Firmware Strategy
The original Ilumi distribution servers are no longer available. Future firmware management must rely on decentralized extraction and distribution.

1. **Firmware Extraction (Peer Mimicry)**:
   - Theoretical concept: An agent or script mimics a "bulb in need of an update" to trigger a firmware push from an existing bulb that has a newer version.
   - Requires protocol capture of the handshake between two bulbs during a mesh update.

2. **Mesh Distribution (Peer Cloning)**:
   - Once a firmware blob is extracted, implement the `DATA_CHUNK` and `CONFIG` routines to broadcast the update across the mesh.
   - One bulb acts as the "source" and transfers its image to neighbors in the vicinity.

## Gen1 FOTA (Broadcom)
- [ ] Implement block-by-block data transfer logic in `ilumi_sdk.py`.
- [ ] Add header validation and CRC checks for Gen1 updates.

## User Guide: Firmware Updates
Once implemented, users will be able to check and update their bulbs with ease:

1. **Check Version**:
   ```bash
   python3 firmware.py version --all
   ```
2. **Perform Update**:
   ```bash
   python3 firmware.py update --name kitchen
   ```
   *Note: This will automatically put the bulb into DFU mode and flash the latest compatible image.*
