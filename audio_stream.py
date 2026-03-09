import asyncio
import numpy as np
import sounddevice as sd
from ilumi_sdk import IlumiSDK
import config
# XXX: harness - audio_stream needs more comprehensive testing
import os
import math
import argparse
import struct
import sys
import logging
import json
import signal
from typing import List, Optional

# Audio Config
SAMPLE_RATE = 44100
CHUNK_SIZE = 2048  # Frames per audio block

# Frequency bands to watch (in Hz)
BASS_MIN = 20
BASS_MAX = 200
HIGH_MIN = 3000
HIGH_MAX = 10000

class AudioVisualizer:
    def __init__(self, targets, use_mesh=False, proxy=None):
        self.targets = targets
        self.use_mesh = use_mesh
        self.proxy = proxy
        self.all_sdks = []
        
        if self.use_mesh:
            # In mesh mode, we only connect to the proxy bulb (or the first target)
            proxy_mac = self.proxy if self.proxy else targets[0]
            self.all_sdks = [IlumiSDK(proxy_mac)]
            print(f"Mesh Mode: Commands will be proxied via {proxy_mac}")
        else:
            self.all_sdks = [IlumiSDK(mac) for mac in targets]
            
        self.sdks = []  # populated after successful connect
        self.r = 0
        self.g = 0
        self.b = 0
        
        # Smoothing factors
        self.r_val = 0.0
        self.b_val = 0.0
        self.decay = 0.85     
        self.smoothing = 0.4  

        # Concurrency control: BlueZ needs a limit, Bumble can handle many more
        limit = 100 if os.environ.get("ILUMI_USE_BUMBLE") == "1" else 2
        self._connect_sem = asyncio.Semaphore(limit)
        self.stop_event = None # Will be set by run()

    def audio_callback(self, indata, frames, time, status):
        """Called by sounddevice for each block of audio."""
        if status:
            print(f"Status: {status}")

        mono_data = np.mean(indata, axis=1)
        fft_data = np.abs(np.fft.rfft(mono_data))
        freqs = np.fft.rfftfreq(len(mono_data), 1.0 / SAMPLE_RATE)

        bass_idx = np.where((freqs >= BASS_MIN) & (freqs <= BASS_MAX))[0]
        bass_energy = np.mean(fft_data[bass_idx]) if len(bass_idx) > 0 else 0

        high_idx = np.where((freqs >= HIGH_MIN) & (freqs <= HIGH_MAX))[0]
        high_energy = np.mean(fft_data[high_idx]) if len(high_idx) > 0 else 0

        raw_r = min(1.0, bass_energy * 0.1) 
        raw_b = min(1.0, high_energy * 0.3)

        if raw_r > self.r_val:
            self.r_val = self.r_val * self.smoothing + raw_r * (1 - self.smoothing)
        else:
            self.r_val = self.r_val * self.decay
            
        if raw_b > self.b_val:
            self.b_val = self.b_val * self.smoothing + raw_b * (1 - self.smoothing)
        else:
            self.b_val = self.b_val * self.decay

        self.r = int(min(255, max(0, self.r_val * 255)))
        self.b = int(min(255, max(0, self.b_val * 255)))

    async def _connect_sdk(self, sdk):
        """Try to connect a single SDK; return it on success, None on failure."""
        async with self._connect_sem:
            try:
                await sdk.__aenter__()
                return sdk
            except Exception as e:
                print(f"Warning: could not connect to {sdk.mac_address} – {e}. Skipping.")
                return None

    async def _send_color(self, sdk, r, g, b):
        """Send a color command to one SDK (or via mesh), logging but not raising on failure."""
        try:
            if self.use_mesh:
                # Send proxy command to all targets via the connected proxy SDK
                await sdk.set_color_fast(r, g, b, 0, 255, targets=self.targets)
            else:
                await sdk.set_color_fast(r, g, b, 0, 255)
        except Exception as e:
            print(f"Warning: command failed for {sdk.mac_address} – {e}. Skipping.")
            if sdk in self.sdks:
                self.sdks.remove(sdk)

    async def run(self, device=None, stop_event: Optional[asyncio.Event] = None):
        self.stop_event = stop_event if stop_event else asyncio.Event()

        total = len(self.all_sdks)
        print(f"Connecting to {total} bulbs concurrently...")

        results = await asyncio.gather(*(self._connect_sdk(sdk) for sdk in self.all_sdks))
        self.sdks = [sdk for sdk in results if sdk is not None]

        if not self.sdks:
            print("No bulbs could be connected. Exiting.")
            self.stop_event.set() # Signal main loop to stop
            return

        print(f"{len(self.sdks)}/{total} bulbs connected.")

        if self.use_mesh and not getattr(self, 'skip_health_check', False):
            print("Verifying mesh nodes availability (5s scan)...")
            try:
                from bumble_sdk import IlumiSDK as BumbleSDK
                discovered = await BumbleSDK.discover(timeout=5.0)
                found_macs = {config.normalize_mac(d['address']) for d in discovered}
                
                # Proxy is considered online by definition if we are connected to it
                proxy_mac = config.normalize_mac(self.all_sdks[0].mac_address)
                if proxy_mac:
                    found_macs.add(proxy_mac)
                
                offline = [m for m in self.targets if config.normalize_mac(m) not in found_macs]
                if offline:
                    print(f"Warning: {len(offline)} mesh nodes appear to be offline or out of range: {', '.join(offline)}")
                    print("Excluding offline nodes from stream to improve reliability.")
                    self.targets = [m for m in self.targets if config.normalize_mac(m) in found_macs]
                else:
                    print("All mesh nodes appear to be online.")
                print(f"Active Mesh Targets: {len(self.targets)} bulbs.")
            except Exception as e:
                print(f"Mesh health check failed: {e}")

        try:
            print("Starting Audio Stream...")
            
            # Print the audio device being used
            default_device = sd.query_devices(kind='input')
            print(f"Using Audio Input: {default_device['name']} "
                  f"(Default Sample Rate: {default_device['default_samplerate']}Hz)")

            with sd.InputStream(callback=self.audio_callback,
                                channels=1, 
                                samplerate=SAMPLE_RATE, 
                                blocksize=CHUNK_SIZE,
                                device=device):

                print("Listening... Press Ctrl+C to stop.")
                while not self.stop_event.is_set():
                    # Check for disconnected SDKs and try to reconnect
                    if not self.sdks:
                        print("Disconnected. Attempting to reconnect...")
                        # Ensure we don't spam reconnection attempts too fast
                        await asyncio.sleep(2.0)
                        results = await asyncio.gather(*(self._connect_sdk(sdk) for sdk in self.all_sdks))
                        self.sdks = [sdk for sdk in results if sdk is not None]
                        if not self.sdks:
                            continue
                        print(f"Reconnected: {len(self.sdks)}/{len(self.all_sdks)} bulbs active.")

                    # Only send if we have sdk AND either non-mesh OR mesh with targets
                    if self.sdks and (not self.use_mesh or self.targets):
                        # Send colors to all active SDKs
                        await asyncio.gather(*(self._send_color(sdk, self.r, self.g, self.b) for sdk in self.sdks))
                    elif self.use_mesh and not self.targets:
                        # Log once to avoid spamming the console
                        if not getattr(self, '_targets_empty_logged', False):
                            print("Warning: No active mesh targets online. Waiting...")
                            self._targets_empty_logged = True
                    
                    if self.use_mesh and self.targets:
                        self._targets_empty_logged = False
                        
                    await asyncio.sleep(0.033) 
                        
        except asyncio.CancelledError:
            print("Visualizer task cancelled.")
        except Exception as e:
            print(f"An error occurred during audio streaming: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"Visualizer run loop finished. Stop event set: {self.stop_event.is_set()}")

    async def stop(self):
        """Turns off bulbs and cleans up SDK connections."""
        print("Turning bulbs off...")
        await asyncio.gather(*(self._send_color(sdk, 0, 0, 0) for sdk in self.sdks))
        await asyncio.sleep(0.5)
        for sdk in list(self.sdks): # Use list() to avoid mutation during iteration
            try:
                await sdk.__aexit__(None, None, None)
            except Exception:
                pass
        self.sdks = []
            
        # Final cleanup for Bumble transport
        if os.environ.get('ILUMI_USE_BUMBLE') == '1':
            try:
                from bumble_sdk import shutdown_bumble
                await shutdown_bumble()
            except ImportError:
                pass
            except Exception as e:
                print(f"Error during Bumble shutdown: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ilumi Audio Visualizer")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    parser.add_argument("--device", type=str, default=None,
                        help="Audio input device name or index (use --list-devices to see options)")
    parser.add_argument("--list-devices", action="store_true",
                        help="List available audio input devices and exit")
    parser.add_argument("--mesh", action="store_true", help="Use mesh routing via a single bulb connection")
    parser.add_argument("--proxy", type=str, help="Specify proxy bulb by name or MAC")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip the startup mesh health verification.")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        exit(0)

    # Mutual exclusivity for targeting
    if args.all:
        targets = config.get_all_bulbs()
    elif args.group:
        targets = config.resolve_targets(target_group=args.group)
    elif args.name:
        targets = config.resolve_targets(target_name=args.name)
    elif args.mac:
        targets = [args.mac]
    else:
        print("No target specified. Use --all, --group, --name, or --mac.")
        sys.exit(1)
        
    if not targets:
        print("No bulbs found matching criteria.")
        sys.exit(1)

    # Allow passing device as integer index
    device = int(args.device) if args.device and args.device.isdigit() else args.device

    proxy_mac = None
    if args.proxy:
        proxy_targets = config.resolve_targets(target_mac=args.proxy, target_name=args.proxy)
        if proxy_targets:
            proxy_mac = proxy_targets[0]

    visualizer = AudioVisualizer(targets, use_mesh=args.mesh, proxy=proxy_mac)
    visualizer.skip_health_check = args.skip_health_check
    visualizer.skip_health_check = args.skip_health_check

    async def main():
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def handle_signal():
            import time
            print(f"\nSignal received at {time.strftime('%H:%M:%S')}. Shutting down gracefully...")
            stop_event.set()
            
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_signal)
            except NotImplementedError:
                # Signal handlers not supported on all platforms/loops
                pass

        try:
            # Run visualizer and wait for stop event or completion
            viz_task = asyncio.create_task(visualizer.run(device=device, stop_event=stop_event))
            stop_task = asyncio.create_task(stop_event.wait())
            
            # Use a wait to allow signal to interrupt
            done, pending = await asyncio.wait(
                [viz_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if stop_event.is_set():
                print("Stopping visualizer...")
                viz_task.cancel()
                try:
                    await viz_task
                except asyncio.CancelledError:
                    pass
        finally:
            # Explicitly turn off bulbs before exiting
            await visualizer.stop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
