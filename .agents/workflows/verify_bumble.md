---
description: Comprehensive verification of the Ilumi Bumble SDK and scripts
---

This workflow ensures that the Bumble SDK is functioning correctly and that recent changes haven't introduced regressions in the CLI scripts.

### 1. Run Unit Tests
// turbo
```bash
export ILUMI_USE_BUMBLE=1
python3 test_bumble_sdk.py
```

### 2. Verify Script Integrity
Check that all core scripts can import the SDK without errors.
// turbo
```bash
export ILUMI_USE_BUMBLE=1
for script in on.py off.py color.py whites.py stream.py audio_stream.py; do
    python3 -c "import $(basename $script .py); print('OK: $script')"
done
```

### 3. Check CLI Help
Ensure Argparse hasn't been broken by targeting changes.
// turbo
```bash
python3 audio_stream.py --help > /dev/null && echo "OK: audio_stream help"
```

### 4. Hardware Validation (If reachable)
Run a brief reliability test if a Bluetooth adapter is available.
// turbo
```bash
export ILUMI_USE_BUMBLE=1
export ILUMI_BT_TRANSPORT="usb:0"
python3 reliability_test.py --count 1 --mac "F8:DD:7A:AA:4B:0D"
```
