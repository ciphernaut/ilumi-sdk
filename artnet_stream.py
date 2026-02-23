import asyncio
import struct
import argparse
import config
from ilumi_sdk import IlumiSDK

ARTNET_PORT = 6454

class ArtNetProtocol(asyncio.DatagramProtocol):
    def __init__(self, targets, universe, start_channel):
        self.sdks = [IlumiSDK(mac) for mac in targets]
        self.universe = universe
        self.start_channel = start_channel - 1  # DMX channels are 1-512, arrays are 0-511
        
        # State cache to prevent sending duplicate packets to the bulb
        self.r, self.g, self.b, self.w = 0, 0, 0, 0

    def connection_made(self, transport):
        self.transport = transport
        print(f"Listening for Art-Net DMX on UDP 0.0.0.0:{ARTNET_PORT}")
        print(f"Targeting Universe {self.universe}, Channels {self.start_channel+1}-{self.start_channel+4} (RGBW)")
        print(f"Outputting to {len(self.sdks)} bulb(s)")

    def datagram_received(self, data, addr):
        if len(data) < 18 or data[0:8] != b"Art-Net\x00":
            return
            
        opcode = struct.unpack('<H', data[8:10])[0]
        if opcode != 0x5000:
            return
            
        universe = struct.unpack('<H', data[14:16])[0]
        if universe != self.universe:
            return
            
        length = struct.unpack('>H', data[16:18])[0]
        dmx_data = data[18:18+length]
        
        if len(dmx_data) >= self.start_channel + 4:
            r = dmx_data[self.start_channel]
            g = dmx_data[self.start_channel + 1]
            b = dmx_data[self.start_channel + 2]
            w = dmx_data[self.start_channel + 3]
            
            if (r, g, b, w) != (self.r, self.g, self.b, self.w):
                self.r, self.g, self.b, self.w = r, g, b, w
                # Fire and forget to all bulbs
                for sdk in self.sdks:
                    asyncio.create_task(sdk.set_color_fast(r, g, b, w, 255))

async def main(targets, universe, channel):
    print(f"Initializing Bluetooth Connection to {len(targets)} bulb(s)...")
    protocol_instance = ArtNetProtocol(targets, universe, channel)
    
    for sdk in protocol_instance.sdks:
        await sdk.__aenter__()
    
    try:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: protocol_instance,
            local_addr=('0.0.0.0', ARTNET_PORT)
        )
        
        print("Server running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)
            
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        print("\nTurning bulbs off...")
        for sdk in protocol_instance.sdks:
            await sdk.set_color_fast(0, 0, 0, 0, 0)
        await asyncio.sleep(0.5)
        
        if 'transport' in locals():
            transport.close()
            
        for sdk in protocol_instance.sdks:
            await sdk.__aexit__(None, None, None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ilumi Art-Net DMX Streamer")
    parser.add_argument("--universe", type=int, default=0, help="Art-Net Universe (0-32767)")
    parser.add_argument("--channel", type=int, default=1, help="Start DMX channel (1-512) for RGBW")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    args = parser.parse_args()

    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)
    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        exit(1)

    try:
        asyncio.run(main(targets, args.universe, args.channel))
    except KeyboardInterrupt:
        print("\nStopping...")
