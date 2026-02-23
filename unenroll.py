import argparse
import asyncio
from ilumi_sdk import execute_on_targets
import config

async def main():
    parser = argparse.ArgumentParser(description="Unenroll (Factory Reset) Ilumi bulb(s)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="CAUTION: Factory reset ALL enrolled bulbs")
    parser.add_argument("--force", action="store_true", help="Force factory reset without confirmation")
    
    args = parser.parse_args()
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please check your arguments.")
        return

    if not args.force:
        print(f"WARNING: You are about to factory reset {len(targets)} bulb(s).")
        confirm = input("Are you sure you want to proceed? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return

    async def _unenroll(sdk):
        print(f"[{sdk.mac_address}] Sending factory reset commissioning command...")
        async with sdk:
            # Commissioning with a blank/0 network key and 0 node/groups 
            # effectively resets the bulb to its un-commissioned factory state.
            success = await sdk.commission(0, 0, 0)
            if success:
                print(f"[{sdk.mac_address}] Successfully unenrolled.")
            else:
                print(f"[{sdk.mac_address}] Failed to unenroll.")

    await execute_on_targets(targets, _unenroll)
    
    # Clean up the config file after unenrollment
    cfg = config.load_config()
    if "bulbs" in cfg:
        original_count = len(cfg["bulbs"])
        cfg["bulbs"] = {k: v for k, v in cfg["bulbs"].items() if k not in targets}
        removed = original_count - len(cfg["bulbs"])
        config.save_config(cfg)
        print(f"Removed {removed} bulb(s) from ilumi_config.json.")

    print("Unenrollment complete.")

if __name__ == "__main__":
    asyncio.run(main())
