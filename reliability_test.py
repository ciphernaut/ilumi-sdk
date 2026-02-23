import asyncio
import time
import argparse
import sys
import statistics
from typing import List, Dict, Any
from bleak import BleakScanner
from ilumi_sdk import IlumiSDK, ILUMI_SERVICE_UUID

async def scan_bulbs(timeout: float = 5.0) -> List[Dict[str, Any]]:
    print(f"Scanning for Ilumi bulbs ({timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    
    ilumi_devices = []
    for mac, (device, adv_data) in devices.items():
        uuids = [u.lower() for u in adv_data.service_uuids]
        if ILUMI_SERVICE_UUID.lower() in uuids or (device.name and "ilumi" in device.name.lower()):
            ilumi_devices.append({
                "address": device.address,
                "name": device.name or "Unknown",
                "rssi": adv_data.rssi
            })
    
    # Sort by RSSI (strongest first)
    ilumi_devices.sort(key=lambda x: x["rssi"], reverse=True)
    return ilumi_devices

async def test_bulb_reliability(mac: str, iterations: int = 10) -> Dict[str, Any]:
    print(f"  Testing {mac} ({iterations} iterations)...")
    sdk = IlumiSDK(mac)
    
    results = {
        "conn_success": 0,
        "cmd_success": 0,
        "latencies": [],
        "errors": []
    }
    
    start_total = time.time()
    try:
        async with sdk:
            results["conn_success"] = 1
            for i in range(iterations):
                start_cmd = time.time()
                try:
                    # Use get_bulb_color as a ping/status check
                    color = await sdk.get_bulb_color()
                    if color:
                        results["cmd_success"] += 1
                        results["latencies"].append(time.time() - start_cmd)
                    else:
                        results["errors"].append(f"Iter {i+1}: Timeout/Empty response")
                except Exception as e:
                    results["errors"].append(f"Iter {i+1}: {str(e)}")
                
                # Small gap between pings
                await asyncio.sleep(0.1)
                
    except Exception as e:
        results["errors"].append(f"Connection failed: {str(e)}")
        results["conn_success"] = 0

    end_total = time.time()
    
    summary = {
        "connected": results["conn_success"] > 0,
        "success_rate": (results["cmd_success"] / iterations * 100) if iterations > 0 else 0,
        "avg_latency": statistics.mean(results["latencies"]) if results["latencies"] else 0,
        "min_latency": min(results["latencies"]) if results["latencies"] else 0,
        "max_latency": max(results["latencies"]) if results["latencies"] else 0,
        "jitter": statistics.stdev(results["latencies"]) if len(results["latencies"]) > 1 else 0,
        "total_test_time": end_total - start_total,
        "errors": results["errors"]
    }
    return summary

async def main():
    parser = argparse.ArgumentParser(description="Ilumi Bluetooth Reliability Benchmarking Tool")
    parser.add_argument("--timeout", type=float, default=5.0, help="Scan timeout in seconds")
    parser.add_argument("--iters", type=int, default=10, help="Number of commands per bulb")
    parser.add_argument("--mac", type=str, help="Test only a specific MAC address")
    args = parser.parse_args()

    if args.mac:
        bulbs = [{"address": args.mac, "name": "Target Device", "rssi": 0}]
    else:
        bulbs = await scan_bulbs(args.timeout)
    
    if not bulbs:
        print("No Ilumi bulbs found.")
        return

    print(f"\nDiscovered {len(bulbs)} bulbs. Starting reliability benchmark...")
    print("-" * 80)
    print(f"{'MAC Address':<20} | {'Name':<15} | {'RSSI':<5} | {'Success%':<8} | {'Avg Lat (s)':<12}")
    print("-" * 80)

    all_stats = []

    for b in bulbs:
        stats = await test_bulb_reliability(b["address"], args.iters)
        b.update(stats)
        all_stats.append(b)
        
        # Color code success rate loosely in terminal if supported (not doing here for simplicity)
        print(f"{b['address']:<20} | {b['name']:<15} | {b['rssi']:<5} | {b['success_rate']:>7.1f}% | {b['avg_latency']:>11.3f}")

    print("-" * 80)
    
    # Identify the best proxy candidate
    # Weighted score: 40% RSSI (normalized), 50% Success Rate, 10% Latency (inverse)
    # Actually, Success Rate is the most important for proxying.
    
    def calculate_score(b):
        if not b["connected"]: return -1
        # RSSI is negative, typical range -40 to -90. Normalize -90 -> 0, -40 -> 100
        rssi_norm = max(0, min(100, (b["rssi"] + 95) * 2)) 
        # Success Rate is 0-100
        # Latency: 0.1s is good (100 pts), 1.0s is bad (0 pts)
        lat_norm = max(0, min(100, (1.0 - b["avg_latency"]) * 100))
        
        return (rssi_norm * 0.3) + (b["success_rate"] * 0.6) + (lat_norm * 0.1)

    all_stats.sort(key=calculate_score, reverse=True)
    
    print("\n🏆 Reliability Rankings (Best candidates for Mesh Proxy):")
    for i, b in enumerate(all_stats):
        if not b["connected"]:
            print(f"{i+1}. {b['address']} ({b['name']}): CONNECTION FAILED")
            continue
        
        score = calculate_score(b)
        print(f"{i+1}. {b['address']} ({b['name']}): Score {score:.1f}/100")
        print(f"   [RSSI: {b['rssi']} dBm, Success: {b['success_rate']}%, Avg Lat: {b['avg_latency']:.3f}s]")

    if all_stats and all_stats[0]["connected"]:
        best = all_stats[0]
        print(f"\nRECOMMENDATION: Use '{best['name']}' ({best['address']}) as your primary --proxy.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
