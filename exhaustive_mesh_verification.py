import asyncio
import os
import subprocess
import time

async def run_cmd(cmd):
    print(f"Running: {cmd}")
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()

async def verify_bulb(name, proxy, cycle_num):
    print(f"--- Cycle {cycle_num} for Proxy: {proxy}, Target: {name} ---")
    
    # Off
    rc, out, err = await run_cmd(f"python3 off.py --mac {name} --mesh --proxy {proxy}")
    if rc != 0: print(f"Off Failed: {err}")
    await asyncio.sleep(2)
    
    # Capture webcam if target is computer
    if name == "FD:66:EE:0A:7B:67":
        await run_cmd(f"sg video -c 'fswebcam -r 1280x720 --no-banner v_cycle_{proxy}_{cycle_num}_off.jpg'")
    
    # On
    rc, out, err = await run_cmd(f"python3 on.py --mac {name} --mesh --proxy {proxy}")
    if rc != 0: print(f"On Failed: {err}")
    await asyncio.sleep(2)
    
    if name == "FD:66:EE:0A:7B:67":
        await run_cmd(f"sg video -c 'fswebcam -r 1280x720 --no-banner v_cycle_{proxy}_{cycle_num}_on.jpg'")

async def main():
    # 3 cycles with 'four' as proxy targeting 'computer' (visible)
    for i in range(1, 4):
        await verify_bulb("FD:66:EE:0A:7B:67", "four", i)
        
    # 3 cycles with 'computer' as proxy targeting 'one' (inner verification)
    # Even if not visible, we verify command completion
    for i in range(1, 4):
        await verify_bulb("E2:B0:F7:F4:50:60", "computer", i)

if __name__ == "__main__":
    asyncio.run(main())
