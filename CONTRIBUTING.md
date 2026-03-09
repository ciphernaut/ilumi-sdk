# Contributing to Ilumi SDK

Thank you for your interest in contributing to the Ilumi Python SDK! This document provides guidelines for human developers to set up a development environment and contribute code.

## 1. Environment Setup

The SDK requires Python 3.11+ and a Linux environment with a Bluetooth adapter.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-repo/ilumi-sdk.git
    cd ilumi-sdk
    ```

2.  **Create a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 2. Code Structure

- `ilumi_sdk.py`: The core SDK using the `bleak` library.
- `bumble_sdk.py`: The direct HCI SDK using the `bumble` library.
- `enroll.py`, `on.py`, `off.py`, etc.: CLI wrapper scripts.
- `PROTOCOL.md`: Technical reference for the GATT protocol.
- `tests/`: Directory for test scripts and diagnostic captures.

## 3. Running Tests

We use `pytest` for unit testing. Hardware-specific tests may require a live Ilumi bulb and a Bluetooth adapter.

```bash
# Run all unit tests
python3 -m pytest sdk_tests/
```

To run tests with the Bumble backend enabled:
```bash
export ILUMI_USE_BUMBLE=1
python3 -m pytest sdk_tests/
```

## 4. Hardware Verification

If you are modifying the core protocol logic, you **MUST** verify the changes on physical hardware.
- Use `enroll.py` to ensure your bulb is correctly identified.
- Use `tests/reliability_test.py` to check for command delivery consistency.
- Use `btmon` (via `ENABLEMENT.md` instructions) to capture HCI traces for debugging.

## 5. Pull Request Guidelines

- Ensure your code follows PEP 8 standards.
- Documentation for new features is required.
- Update `TODO.md` if you are completing an existing task.
- Attach a success log or screenshot of physical verification if applicable.
