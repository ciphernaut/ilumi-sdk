import asyncio
import colorsys
import time
from ilumi_sdk import IlumiSDK

async def stream_colors(mac_address, duration=10, fps=30):
    print(f"Starting connection to {mac_address} for streaming test...")
    print(f"Target: {fps} FPS for {duration} seconds.")

    sdk = IlumiSDK(mac_address)
    async with sdk:
        start_time = time.time()
        frames_sent = 0
        
        # Calculate time per frame
        tpf = 1.0 / fps

        print("Streaming...")
        while time.time() - start_time < duration:
            loop_start = time.time()

            # Generate a rotating hue across the time spectrum
            hue = ((time.time() - start_time) / 3.0) % 1.0 
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            
            # Convert float 0.0-1.0 to int 0-255
            r = int(rgb[0] * 255)
            g = int(rgb[1] * 255)
            b = int(rgb[2] * 255)

            # Fire off the color command without waiting for an ACK
            await sdk.set_color_fast(r, g, b, 0, 255)
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ilumi Fast Streaming Test")
    parser.add_argument("--mac", type=str, required=False, help="MAC address of the Ilumi bulb")
    parser.add_argument("--duration", type=int, default=10, help="Duration to run the test in seconds")
    parser.add_argument("--fps", type=int, default=30, help="Target frames per second")
    args = parser.parse_args()

    # The IlumiSDK will automatically fallback to ilumi_config.json if no MAC is provided
    asyncio.run(stream_colors(args.mac, args.duration, args.fps))
