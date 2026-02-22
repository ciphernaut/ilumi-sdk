import requests
from requests.auth import HTTPBasicAuth

CLIENT_ID = "ZCRYTSQZTRSVXTH"
CLIENT_SECRET = "L3KQbuv05KuEJyaP5NLwwN9mBYFPiBrdg7f9q3BrL98iuJYw1n"
TOKEN_URL = "https://api.ilumi.io/api/v1/assets/tokens"
FIRMWARE_URL = "https://api.ilumi.io/api/v1/firmware"

def get_access_token():
    """Retrieves an access token using Basic Auth."""
    print(f"Requesting token from {TOKEN_URL}...")
    try:
        response = requests.post(
            TOKEN_URL,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=10
        )
        print(f"Token response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        return data.get("accessToken")
    except Exception as e:
        print(f"Error retrieving access token: {e}")
        return None

def get_latest_firmware(model_number):
    """
    Fetches firmware metadata and returns the latest version for the given model.
    """
    token = get_access_token()
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"Fetching firmware from {FIRMWARE_URL}...")
    try:
        response = requests.get(FIRMWARE_URL, headers=headers, timeout=10)
        print(f"Firmware response status: {response.status_code}")
        response.raise_for_status()
        assets = response.json()

        # assets is likely a list of ILAssetDescriptor objects
        # We need to find the one where targetModel matches model_number
        # and it has the highest versionNumber.

        model_firmwares = [
            a for a in assets 
            if a.get("targetModel") == model_number
        ]

        if not model_firmwares:
            return None

        # Sort by versionNumber descending
        latest = sorted(model_firmwares, key=lambda x: x.get("versionNumber", 0), reverse=True)[0]
        return latest
    except Exception as e:
        print(f"Error fetching firmware metadata: {e}")
        return None

if __name__ == "__main__":
    # Test with a known model number (e.g., 65 for Gen2)
    latest = get_latest_firmware(65)
    if latest:
        print(f"Latest firmware for model 65: {latest.get('versionNumber')} ({latest.get('version')})")
    else:
        print("No firmware found for model 65.")
