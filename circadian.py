import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from ilumi_sdk import execute_on_targets, IlumiSDK
import config

async def main():
    parser = argparse.ArgumentParser(description="Control Ilumi hardware-backed circadian rhythm")
    parser.add_argument("mode", choices=["on", "off", "status", "sync", "upload"], help="Action to perform: toggle mode, query status, sync clock, or upload profile")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--json", action="store_true", help="Output execution results strictly as JSON")
    parser.add_argument("--mesh", action="store_true", help="Use mesh routing via a single bulb connection")
    parser.add_argument("--proxy", type=str, help="Specify proxy bulb by name or MAC")
    parser.add_argument("--retries", type=int, default=3, help="Number of times to send mesh commands (default: 3)")
    parser.add_argument("--profile", type=str, help="Path to JSON profile for upload")
    parser.add_argument("--timestamp", type=float, help="Optional Unix timestamp for sync")
    args = parser.parse_args()
    
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        if args.json:
            print(json.dumps({"error": "No targets resolved"}))
        else:
            print("No targets resolved. Please run enroll.py or check your arguments.")
        return

    if args.proxy:
        proxy_targets = config.resolve_targets(target_mac=args.proxy, target_name=args.proxy)
        proxy_target = proxy_targets[0] if proxy_targets else targets[0]
    else:
        proxy_target = targets[0]

    async def _set_circadian(sdk):
        enabled = (args.mode == "on")
        if not args.json:
            print(f"Setting circadian rhythm to {'ON' if enabled else 'OFF'} on {sdk.mac_address}...")
        async with sdk:
            await sdk.set_circadian(enabled)

    async def _mesh_set_circadian(sdk):
        enabled = (args.mode == "on")
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy circadian {'ON' if enabled else 'OFF'} to {len(targets)} targets...")
        async with sdk:
            for i in range(args.retries):
                await sdk.set_circadian(enabled, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)

    async def _sync_time(sdk):
        if not args.json:
            print(f"Synchronizing clock on {sdk.mac_address} to {args.timestamp or 'system time'}...")
        async with sdk:
            await sdk.sync_time(timestamp=args.timestamp)

    async def _mesh_sync_time(sdk):
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy sync_time to {len(targets)} targets...")
        async with sdk:
            for i in range(args.retries):
                await sdk.sync_time(timestamp=args.timestamp, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)

    async def _upload_profile(sdk):
        profile = None
        if args.profile:
            with open(args.profile, 'r') as f:
                profile = json.load(f)
        if not args.json:
            print(f"Uploading circadian profile to {sdk.mac_address} starting from {args.timestamp or 'system time'}...")
        async with sdk:
            # Disable native circadian first to avoid conflicts
            await sdk.set_circadian(False)
            await sdk.upload_circadian_profile(profile, timestamp=args.timestamp)

    async def _mesh_upload_profile(sdk):
        profile = None
        if args.profile:
            with open(args.profile, 'r') as f:
                profile = json.load(f)
        if not args.json:
            print(f"[{sdk.mac_address}] Sending mesh proxy upload_circadian_profile to {len(targets)} targets...")
        async with sdk:
            # Disable native circadian first via mesh
            for i in range(args.retries):
                await sdk.set_circadian(False, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)
            
            for i in range(args.retries):
                await sdk.upload_circadian_profile(profile, timestamp=args.timestamp, targets=targets)
                if i < args.retries - 1:
                    await asyncio.sleep(0.3)

    async def _get_status(sdk):
        if not args.json:
            print(f"Querying circadian status from {sdk.mac_address}...")
        async with sdk:
            status = await sdk.get_circadian()
            if not args.json:
                print(f"[{sdk.mac_address}] Circadian state: {'ON' if status else 'OFF' if status is False else 'Unknown (Timeout)'}")
            return status

    results = {}
    if args.mode == "status":
        # Status query requires individual connections or mesh proxy with response
        if args.mesh:
            # Querying over mesh requires targeting one specific bulb through the proxy
            async def _mesh_query(sdk):
                async with sdk:
                    return await sdk.get_circadian(target=targets[0])
            
            outcome = await execute_on_targets([proxy_target], _mesh_query)
            results = outcome
        else:
            results = await execute_on_targets(targets, _get_status)
    elif args.mode == "sync":
        if args.mesh:
            results = await execute_on_targets([proxy_target], _mesh_sync_time)
        else:
            results = await execute_on_targets(targets, _sync_time)
    elif args.mode == "upload":
        if args.mesh:
            results = await execute_on_targets([proxy_target], _mesh_upload_profile)
        else:
            results = await execute_on_targets(targets, _upload_profile)
    else:
        if args.mesh:
            results = await execute_on_targets([proxy_target], _mesh_set_circadian)
        else:
            results = await execute_on_targets(targets, _set_circadian)

    if args.json:
        print(json.dumps({"command": f"circadian_{args.mode}", "targets": targets, "results": results}))

if __name__ == "__main__":
    asyncio.run(main())
