import asyncio
import struct
import argparse
import config
from ilumi_sdk import IlumiSDK

ARTNET_PORT = 6454

class ArtNetProtocol(asyncio.DatagramProtocol):
    def __init__(self, sdk, universe, start_channel):
        self.sdk = sdk
        self.universe = universe
        self.start_channel = start_channel - 1  # DMX channels are 1-512, arrays are 0-511
        
        # State cache to prevent sending duplicate packets to the bulb
        self.r, self.g, self.b, self.w = 0, 0, 0, 0

    def connection_made(self, transport):
        self.transport = transport
        print(f"Listening for Art-Net DMX on UDP 0.0.0.0:{ARTNET_PORT}")
        print(f"Targeting Universe {self.universe}, Channels {self.start_channel+1}-{self.start_channel+4} (RGBW)")

    def datagram_received(self, data, addr):
        # 1. Art-Net Header Check (18 bytes minimum for DMX payload)
        if len(data) < 18 or data[0:8] != b"Art-Net\x00":
            return
            
        # 2. OpCode Check (OpDmx is 0x5000, Little Endian)
        opcode = struct.unpack('<H', data[8:10])[0]
        if opcode != 0x5000:
            return
            
        # 3. Universe Match (Little Endian in modern Art-Net)
        universe = struct.unpack('<H', data[14:16])[0]
        if universe != self.universe:
            return
            
        # 4. Length and Payload Extraction (Length is Big Endian)
        length = struct.unpack('>H', data[16:18])[0]
        dmx_data = data[18:18+length]
        
        # 5. Route specified channels to the bulb
        if len(dmx_data) >= self.start_channel + 4:
            r = dmx_data[self.start_channel]
            g = dmx_data[self.start_channel + 1]
            b = dmx_data[self.start_channel + 2]
            w = dmx_data[self.start_channel + 3]
            
            # Fire and forget if the color changed
            if (r, g, b, w) != (self.r, self.g, self.b, self.w):
                self.r, self.g, self.b, self.w = r, g, b, w
                # We use create_task to ensure the UDP thread doesn't block waiting for BLE
                asyncio.create_task(self.sdk.set_color_fast(r, g, b, w, 255))

async def main(mac, universe, channel):
    print("Initializing Bluetooth Connection...")
    sdk = IlumiSDK(mac)
    
    async with sdk:
        loop = asyncio.get_running_loop()
        
        # Start the UDP Server
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ArtNetProtocol(sdk, universe, channel),
            local_addr=('0.0.0.0', ARTNET_PORT)
        )
        
        try:
            print("Server running. Press Ctrl+C to stop.")
            while True:
                # Keep the main coroutine alive while the UDP endpoint listens in the background
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            transport.close()
            print("Turning bulb off...")
            await sdk.set_color_fast(0, 0, 0, 0, 0)
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ilumi Art-Net DMX Streamer")
    parser.add_argument("--mac", type=str, required=False, help="MAC address of the bulb")
    parser.add_argument("--universe", type=int, default=0, help="Art-Net Universe (0-32767)")
    parser.add_argument("--channel", type=int, default=1, help="Start DMX channel (1-512) for RGBW")
    args = parser.parse_args()

    mac = args.mac or config.get_config("mac_address")
    if not mac:
        print("No MAC address specified in arguments or config.")
        exit(1)

    try:
        asyncio.run(main(mac, args.universe, args.channel))
    except KeyboardInterrupt:
        print("\nStopping...")
