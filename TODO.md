# TODO

- [x] **Bulb Group Functionality**: Implement and test the ability to control multiple bulbs simultaneously using group IDs.
- [x] **Spatial Layout Awareness**: Added recursive mesh crawling and interactive spatial mapping (`mesh_mapper.py`, `pyvis_mapper.py`).
- [ ] **AI-Optimized Command Output**: Refine CLI output (e.g., more compact JSON, reduced verbosity) to conserve tokens when driven by AI agents.
- [x] **Live Visualization Sources**:
    - [x] Audio reaction mode (e.g., syncing lights to music via `audio_stream.py`).
    - [x] Other live data-driven visualization sources (e.g., Art-Net DMX via `artnet_stream.py`).

## Deferred/Unimplemented Original App Features
The following features exist in the original Ilumi Android App's BLE GATT protocol but have not yet been implemented in our Python SDK:
- [x] **Alarms and Scheduling**: (`ILUMI_API_CMD_SET_DAILY_ALARM`, `ILUMI_API_CMD_SET_CALENDAR_EVENT`) - The bulbs have an internal Real-Time Clock (RTC). **Clock synchronization is now implemented via `sync_time()`.**
- [ ] **iBeacon Emulation/Configuration**: (`ILUMI_API_CMD_SET_IBEACON` = 44) - The original bulbs could act as Bluetooth LE iBeacons for spatial tracking. Other related missing: `GET_IBEACON_MAJOR_MINOR` (45), `GET_IBEACON_UUID` (46).
- [x] **Hardware Actions/Triggers**: (`ILUMI_API_CMD_ADD_ACTION` = 50) - Configuring internal hardware macros.
- [x] **Circadian Rhythms**: (`ILUMI_API_CMD_ENABLE_CIRCADIAN` = 42) - Hardware-backed automatic color temperature adjustment slowly over the course of a day.
- [x] **Advanced Patterns & Cleaners**:
    - [x] `ILUMI_API_CMD_DELETE_COLOR_PATTERN` (18)
    - [x] `ILUMI_API_CMD_DELETE_ALL_COLOR_PATTERNS` (19)
    - [x] `ILUMI_API_CMD_CLEAR_ALL_USER_DATA` (20)
- [ ] **Node & Group Management**:
    - [ ] `ILUMI_API_CMD_SET_NODE_ID`/`GET_NODE_ID` (21, 22)
    - [ ] `ILUMI_API_CMD_ADD_GROUP_ID`/`DEL_GROUP_ID`/`GET_GROUP_IDS` (23, 24, 25)
    - [ ] `ILUMI_API_CMD_CLEAR_ALL_GROUP_IDS` (26)
- [ ] **Mesh & Routing Extensions**:
    - [ ] `ILUMI_API_CMD_ADD_ROUTING_ENTRY`/`CLEAR_ROUTING` (29, 30)
    - [ ] `ILUMI_API_CMD_TREE_MESH` (41)
    - [ ] `ILUMI_API_CMD_PROXY_MSG_GROUP` (43)
- [ ] **Strip & Zone Control**:
    - [ ] `ILUMI_API_CMD_STRIP` (78)
    - [ ] `ILUMI_API_CMD_STRIP_STR_CMD` (79)
    - [ ] `ILUMI_API_ZONE_COLOR` (80)
    - [ ] `ILUMI_SET_STRIP_COLOR_AT_LEN` (83)
- [ ] **Hardware Diagnostics & Misc**:
    - [ ] `ILUMI_API_CMD_GET_TEMP_VOLTAGE` (47)
    - [ ] `ILUMI_API_CMD_BLINK_WITH_COLOR`/`BLINK_WITH_DEAULT_COLOR` (2, 3)
    - [x] `ILUMI_API_CMD_SET_RANDOM_COLOR`/`RANDOM_COLOR_SEQUENCE` (48, 38)
    - [x] `ILUMI_API_CMD_PING`/`PING_ECHO` (84, 85)

## Phase 7: Polish & UX Details
- [x] **Hardware Fading/Transitions**: Implement `ILUMI_API_CMD_SET_COLOR_SMOOTH` as the default in `on.py`, `off.py`, `whites.py`, and `color.py`, adding a `--no-fade` opt-out flag. Fixed fade granularity to ensure millisecond-level precision.
