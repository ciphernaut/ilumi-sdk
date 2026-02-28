#!/bin/bash
# Master test script for Ilumi SDK and CLI scripts

echo "--- Running Core Bumble SDK Tests ---"
python3 test_bumble_sdk.py
if [ $? -ne 0 ]; then echo "Bumble SDK Tests Failed!"; exit 1; fi

echo ""
echo "--- Running SDK Structure (API Parity) Tests ---"
python3 sdk_tests/test_sdk_structure.py
if [ $? -ne 0 ]; then echo "SDK Structure Tests Failed!"; exit 1; fi

echo ""
echo "--- Running CLI Script (Logic & Routing) Tests ---"
python3 sdk_tests/test_cli_scripts.py
if [ $? -ne 0 ]; then echo "CLI Script Tests Failed!"; exit 1; fi

echo ""
echo "All tests passed successfully!"
