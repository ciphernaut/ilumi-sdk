import asyncio
import colorsys
import time
import argparse
from ilumi_sdk import IlumiSDK
import config

async def stream_colors(targets, duration=10, fps=30):
    print(f"Target: {fps} FPS for {duration} seconds.")

    # Instantiate SDKs
    sdks = [IlumiSDK(mac) for mac in targets]
    
    # We need to manually manage the contexts for simultaneous streaming
    for sdk in sdks:
        await sdk.__aenter__()

    try:
        start_time = time.time()
        frames_sent = 0
        tpf = 1.0 / fps

        print("Streaming...")
        while time.time() - start_time < duration:
            loop_start = time.time()

            # Generate a rotating hue across the time spectrum
            hue = ((time.time() - start_time) / 3.0) % 1.0 
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            
            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)

            # Fire off the color command to all bulbs concurrently
            await asyncio.gather(*(sdk.set_color_fast(r, g, b, 0, 255) for sdk in sdks))
            frames_sent += 1

            # Sleep enough to maintain target FPS
            elapsed = time.time() - loop_start
            sleep_time = tpf - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        end_time = time.time()
        actual_fps = frames_sent / (end_time - start_time)
        
        print("\n--- Streaming Complete ---")
        print(f"Total Sent : {frames_sent} frames")
        print(f"Elapsed    : {end_time - start_time:.2f} seconds")
        print(f"Actual Rate: {actual_fps:.2f} FPS")
        
    finally:
        for sdk in sdks:
            await sdk.__aexit__(None, None, None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ilumi Fast Streaming Test")
    parser.add_argument("--duration", type=int, default=10, help="Duration to run the test in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Target frames per second")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    args = parser.parse_args()

    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        exit(1)

    asyncio.run(stream_colors(targets, args.duration, args.fps))
