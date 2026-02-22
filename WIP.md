# Work In Progress - Firmware Update Integration

## Current Status
- [x] **SDK Support**: Added `GET_DEVICE_INFO` and `CONFIG` commands to `ilumi_sdk.py`.
- [x] **Notification Handling**: Fixed response parsing for 4-byte response headers.
- [x] **Local Version Check**: Implemented `python3 firmware.py version` to report current firmware/model.
- [x] **DFU Trigger**: Implemented `python3 firmware.py dfu` to switch Gen2 bulbs to update mode.
- [x] **Platform Detection**: SDK automatically detects Gen1 (Broadcom) vs Gen2 (Nordic) devices.

## Upstream API Plan
The goal is to automatically check for available updates from Ilumi's servers.

1. **Authentication**:
   - Use the discovered Client ID (`ZCRYTSQZTRSVXTH`) and Secret (`L3KQbuv05KuEJyaP5NLwwN9mBYFPiBrdg7f9q3BrL98iuJYw1n`) with Basic Auth.
   - Endpoint: `https://api.ilumi.io/api/v1/assets/tokens` to get session tokens.

2. **Metadata Retrieval**:
   - Endpoint: `https://api.ilumi.io/api/v1/firmware`
   - Iterate through `ILAssetDescriptor` results and match `targetModel` with the bulb's `model_number`.
   - Compare `version` (parsed as `versionNumber`) with local version.

3. **CLI Integration**:
   - Update `firmware.py` to perform this check automatically when `version` is called.
   - Add a "New version available: X.XX" message if an update is found on the server.

## Gen1 FOTA (Broadcom)
- [ ] Implement block-by-block data transfer logic in `ilumi_sdk.py`.
- [ ] Add header validation and CRC checks for Gen1 updates.
