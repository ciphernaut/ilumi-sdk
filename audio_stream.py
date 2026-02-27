import asyncio
import numpy as np
import sounddevice as sd
from bleak import BleakScanner
from ilumi_sdk import IlumiSDK
import config
import math
import argparse

# Audio Config
SAMPLE_RATE = 44100
CHUNK_SIZE = 2048  # Frames per audio block

# Frequency bands to watch (in Hz)
BASS_MIN = 20
BASS_MAX = 200
HIGH_MIN = 3000
HIGH_MAX = 10000

class AudioVisualizer:
    def __init__(self, targets):
        self.all_sdks = [IlumiSDK(mac) for mac in targets]
        self.sdks = []  # populated after successful connect
        self._connect_sem = asyncio.Semaphore(2)  # BlueZ safe concurrency limit
        self.r = 0
        self.g = 0
        self.b = 0
        
        # Smoothing factors
        self.r_val = 0.0
        self.b_val = 0.0
        self.decay = 0.85     
        self.smoothing = 0.4  

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
        """Send a color command to one SDK, logging but not raising on failure."""
        try:
            await sdk.set_color_fast(r, g, b, 0, 255)
        except Exception as e:
            print(f"Warning: lost connection to {sdk.mac_address} – {e}. Skipping.")

    async def run(self, device=None):
        print(f"Scanning for {len(self.all_sdks)} bulbs...")
        target_macs = {sdk.mac_address.upper() for sdk in self.all_sdks}
        discovered = {
            d.address.upper(): d
            for d in await BleakScanner.discover(timeout=5.0)
            if d.address.upper() in target_macs
        }

        found = len(discovered)
        total = len(self.all_sdks)
        print(f"Found {found}/{total} bulbs in scan. Connecting concurrently...")

        for sdk in self.all_sdks:
            sdk._ble_device = discovered.get(sdk.mac_address.upper())  # None = not found, will fail gracefully

        results = await asyncio.gather(*(self._connect_sdk(sdk) for sdk in self.all_sdks))
        self.sdks = [sdk for sdk in results if sdk is not None]

        if not self.sdks:
            print("No bulbs could be connected. Exiting.")
            return

        print(f"{len(self.sdks)}/{total} bulbs connected.")

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
                while True:
                    await asyncio.gather(*(self._send_color(sdk, self.r, self.g, self.b) for sdk in self.sdks))
                    await asyncio.sleep(0.033) 
                        
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            print("Turning bulbs off...")
            await asyncio.gather(*(self._send_color(sdk, 0, 0, 0) for sdk in self.sdks))
            await asyncio.sleep(0.5)
            for sdk in self.sdks:
                try:
                    await sdk.__aexit__(None, None, None)
                except Exception:
                    pass



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
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        exit(0)

    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        exit(1)

    # Allow passing device as integer index
    device = int(args.device) if args.device and args.device.isdigit() else args.device

    visualizer = AudioVisualizer(targets)
    try:
        asyncio.run(visualizer.run(device=device))
    except KeyboardInterrupt:
        pass
