# TODO

- [x] **Bulb Group Functionality**: Implement and test the ability to control multiple bulbs simultaneously using group IDs.
    - [ ] **Spatial Layout Awareness**: Add capabilities for the SDK to understand and leverage the physical positioning of bulbs for coordinated effects.
- [ ] **AI-Optimized Command Output**: Refine CLI output (e.g., more compact JSON, reduced verbosity) to conserve tokens when driven by AI agents.
- [x] **Live Visualization Sources**:
    - [x] Audio reaction mode (e.g., syncing lights to music via `audio_stream.py`).
    - [x] Other live data-driven visualization sources (e.g., Art-Net DMX via `artnet_stream.py`).

## Deferred/Unimplemented Original App Features
The following features exist in the original Ilumi Android App's BLE GATT protocol but have not yet been implemented in our Python SDK:
- [ ] **Alarms and Scheduling**: (`ILUMI_API_CMD_SET_DAILY_ALARM`, `ILUMI_API_CMD_SET_CALENDAR_EVENT`) - The bulbs have an internal Real-Time Clock (RTC) and can store hardware-level schedules.
- [ ] **iBeacon Emulation/Configuration**: (`ILUMI_API_CMD_SET_IBEACON`) - The original bulbs could act as Bluetooth LE iBeacons for spatial tracking.
- [ ] **Hardware Actions/Triggers**: (`ILUMI_API_CMD_ADD_ACTION`) - Configuring internal hardware macros.
- [ ] **Circadian Rhythms**: (`ILUMI_API_CMD_ENABLE_CIRCADIAN`) - Hardware-backed automatic color temperature adjustment slowly over the course of a day.

## Phase 7: Polish & UX Details
- [x] **Hardware Fading/Transitions**: Implement `ILUMI_API_CMD_SET_COLOR_SMOOTH` as the default in `on.py`, `off.py`, `whites.py`, and `color.py`, adding a `--no-fade` opt-out flag. Fixed fade granularity to ensure millisecond-level precision.
