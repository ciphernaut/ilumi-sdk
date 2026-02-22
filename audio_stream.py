import asyncio
import numpy as np
import sounddevice as sd
from ilumi_sdk import IlumiSDK
import config
import math

# Audio Config
SAMPLE_RATE = 44100
CHUNK_SIZE = 2048  # Frames per audio block

# Frequency bands to watch (in Hz)
BASS_MIN = 20
BASS_MAX = 200
HIGH_MIN = 3000
HIGH_MAX = 10000

class AudioVisualizer:
    def __init__(self, mac_address):
        self.sdk = IlumiSDK(mac_address)
        self.r = 0
        self.g = 0
        self.b = 0
        
        # Smoothing factors
        self.r_val = 0.0
        self.b_val = 0.0
        self.decay = 0.85     # How fast the color fades out (0=instant, 1=never)
        self.smoothing = 0.4  # How fast the color fades in (0=instant, 1=never)

    def audio_callback(self, indata, frames, time, status):
        """Called by sounddevice for each block of audio."""
        if status:
            print(f"Status: {status}")

        # Mix down to mono
        mono_data = np.mean(indata, axis=1)

        # Apply Fast Fourier Transform
        fft_data = np.abs(np.fft.rfft(mono_data))
        freqs = np.fft.rfftfreq(len(mono_data), 1.0 / SAMPLE_RATE)

        # Isolate Bass frequencies
        bass_idx = np.where((freqs >= BASS_MIN) & (freqs <= BASS_MAX))[0]
        bass_energy = np.mean(fft_data[bass_idx]) if len(bass_idx) > 0 else 0

        # Isolate High frequencies
        high_idx = np.where((freqs >= HIGH_MIN) & (freqs <= HIGH_MAX))[0]
        high_energy = np.mean(fft_data[high_idx]) if len(high_idx) > 0 else 0

        # Normalize energies (adjust these scaling factors based on mic sensitivity)
        # We cap them at 1.0
        raw_r = min(1.0, bass_energy * 0.1) 
        raw_b = min(1.0, high_energy * 0.3)

        # Smooth the values to prevent harsh flickering 
        # Attack
        if raw_r > self.r_val:
            self.r_val = self.r_val * self.smoothing + raw_r * (1 - self.smoothing)
        else: # Decay
            self.r_val = self.r_val * self.decay
            
        if raw_b > self.b_val:
            self.b_val = self.b_val * self.smoothing + raw_b * (1 - self.smoothing)
        else:
            self.b_val = self.b_val * self.decay

        # Convert to 8-bit integers for the Ilumi SDK
        self.r = int(min(255, max(0, self.r_val * 255)))
        self.b = int(min(255, max(0, self.b_val * 255)))

    async def run(self):
        print("Initializing Bluetooth Connection...")
        async with self.sdk:
            print("Starting Audio Stream...")
            
            # Print the audio device being used
            default_device = sd.query_devices(kind='input')
            print(f"Using Audio Input: {default_device['name']} "
                  f"(Default Sample Rate: {default_device['default_samplerate']}Hz)")

            # Open the audio stream
            with sd.InputStream(callback=self.audio_callback,
                                channels=1, 
                                samplerate=SAMPLE_RATE, 
                                blocksize=CHUNK_SIZE):

                
                print("Listening... Press Ctrl+C to stop.")
                try:
                    while True:
                        # Stream the calculated colors as fast as possible (approx 20 FPS based on sleep)
                        await self.sdk.set_color_fast(self.r, self.g, self.b, 0, 255)
                        
                        # Short sleep to prevent CPU/BLE overload (~33ms = ~30fps theoretical cap)
                        await asyncio.sleep(0.033) 
                        
                except KeyboardInterrupt:
                    print("\nStopping...")
                finally:
                    # Turn off or dim the bulb gracefully when exiting
                    print("Turning bulb off...")
                    await self.sdk.set_color_fast(0, 0, 0, 0, 0)
                    await asyncio.sleep(0.5)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ilumi Audio Visualizer")
    parser.add_argument("--mac", type=str, required=False, help="MAC address of the Ilumi bulb")
    args = parser.parse_args()

    mac = args.mac or config.get_config("mac_address")
    if not mac:
        print("No MAC address specified in arguments or config.")
        exit(1)

    visualizer = AudioVisualizer(mac)
    asyncio.run(visualizer.run())
