import asyncio
import time
import argparse
import sys
from ilumi_sdk import IlumiSDK
import config

# Morse Code Mapping
MORSE_CODE = {
    'A': '.-',     'B': '-...',   'C': '-.-.',   'D': '-..',    'E': '.',
    'F': '..-.',   'G': '--.',    'H': '....',   'I': '..',     'J': '.---',
    'K': '-.-',    'L': '.-..',   'M': '--',     'N': '-.',     'O': '---',
    'P': '.--.',   'Q': '--.-',   'R': '.-.',    'S': '...',    'T': '-',
    'U': '..-',    'V': '...-',   'W': '.--',    'X': '-..-',   'Y': '-.--',
    'Z': '--..',
    '1': '.----',  '2': '..---',  '3': '...--',  '4': '....-',  '5': '.....',
    '6': '-....',  '7': '--...',  '8': '---..',  '9': '----.',  '0': '-----',
    ' ': ' '
}

async def blink_morse(target_mac, text, wpm=15):
    # Timing calculation based on PARIS standard for Morse
    # Unit (dot length) = 1200 / WPM ms
    unit_ms = 1200 / wpm
    unit_sec = unit_ms / 1000.0
    
    print(f"Targeting: {target_mac}")
    print(f"Text     : {text}")
    print(f"WPM      : {wpm} (Unit: {unit_ms:.1f}ms)")
    
    sdk = IlumiSDK(target_mac)
    
    # Persistent connection
    async with sdk:
        print("Connected. Starting Morse sequence...")
        
        for char in text.upper():
            if char not in MORSE_CODE:
                continue
                
            code = MORSE_CODE[char]
            if code == ' ':
                # Inter-word space (7 units total - already handled 3 by previous char/space)
                print(" ", end="", flush=True)
                await asyncio.sleep(unit_sec * 4) 
                continue
            
            print(f"{char}: {code} ", end="", flush=True)
            for i, symbol in enumerate(code):
                # Turn ON (White at full brightness)
                await sdk.set_color_fast(255, 255, 255, 255, 255)
                
                # Sustain for dot or dash
                duration = unit_sec if symbol == '.' else unit_sec * 3
                await asyncio.sleep(duration)
                
                # Turn OFF
                await sdk.set_color_fast(0, 0, 0, 0, 0)
                
                # Inter-element gap (1 unit)
                if i < len(code) - 1:
                    await asyncio.sleep(unit_sec)
            
            # Inter-character gap (3 units total - already handled 1 by last element gap)
            print("| ", end="", flush=True)
            await asyncio.sleep(unit_sec * 2)
            
        print("\nSequence complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blink Ilumi bulb in Morse code (Stream Mode)")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--text", type=str, default="hello world", help="Text to blink in Morse code")
    parser.add_argument("--wpm", type=int, default=15, help="Morse speed in Words Per Minute (default: 15)")
    args = parser.parse_args()

    targets = config.resolve_targets(args.mac, args.name)
    if not targets:
        print("No targets resolved.")
        sys.exit(1)
    
    target_mac = targets[0]
    
    try:
        asyncio.run(blink_morse(target_mac, args.text, args.wpm))
    except KeyboardInterrupt:
        print("\nAborted by user.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        pass

