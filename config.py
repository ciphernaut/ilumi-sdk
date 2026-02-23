import json
import os

CONFIG_FILE = "ilumi_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
        
    try:
        os.chmod(CONFIG_FILE, 0o660)
    except Exception as e:
        print(f"Warning: Could not set strict permissions on {CONFIG_FILE}: {e}")

def update_config(key, value):
    config = load_config()
    config[key] = value
    save_config(config)

def get_config(key, default=None):
    config = load_config()
    return config.get(key, default)

# --- Multi-Bulb Helpers ---

def get_all_bulbs():
    """Returns the dictionary of all enrolled bulbs mapped by MAC address."""
    return get_config("bulbs", {})

def add_bulb(mac, name, group, node_id=None):
    """Adds or updates a bulb in the configuration."""
    config = load_config()
    if "bulbs" not in config:
        config["bulbs"] = {}
        
    if node_id is None:
        # Auto-increment node_id if not provided
        existing_nodes = [b.get("node_id", 0) for b in config["bulbs"].values()]
        node_id = max(existing_nodes) + 1 if existing_nodes else 1

    config["bulbs"][mac] = {
        "name": name,
        "group": group,
        "node_id": node_id
    }
    save_config(config)
    return node_id

def get_bulb_by_name(name):
    """Returns a tuple of (mac, bulb_data) matching the exact name, or (None, None)."""
    if not name: return None, None
    bulbs = get_all_bulbs()
    for mac, data in bulbs.items():
        if data.get("name", "").lower() == name.lower():
            return mac, data
    return None, None

def get_bulbs_in_group(group):
    """Returns a dictionary of {mac: bulb_data} for bulbs matching the group."""
    if not group: return {}
    bulbs = get_all_bulbs()
    return {mac: data for mac, data in bulbs.items() if data.get("group", "").lower() == group.lower()}

def resolve_targets(target_mac=None, target_name=None, target_group=None, target_all=False):
    """
    Resolves CLI arguments into a list of MAC addresses to control.
    Returns: list of string MAC addresses.
    """
    bulbs = get_all_bulbs()
    
    if target_all:
        return list(bulbs.keys())
        
    if target_group:
        return list(get_bulbs_in_group(target_group).keys())
        
    if target_name:
        mac, _ = get_bulb_by_name(target_name)
        if mac:
            return [mac]
        else:
            print(f"Warning: No bulb found with name '{target_name}'")
            
    if target_mac:
        return [target_mac]

    # If nothing was specified, fall back to the legacy 'mac_address' if it exists,
    # or return all bulbs if the user hasn't provided any specific target.
    # To enforce explicit targeting, we could return [], but returning all is usually friendlier 
    # for users with only 1-2 bulbs. Let's return all if there are any, else legacy mac.
    if bulbs:
        return list(bulbs.keys())
        
    legacy_mac = get_config("mac_address")
    if legacy_mac:
        return [legacy_mac]
        
    return []
