import asyncio
import json
import paho.mqtt.client as mqtt
import config
from ilumi_sdk import IlumiSDK

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASS = None

# We use the config's MAC or command line arg
MAC_ADDRESS = config.get_config("mac_address", "00:00:00:00:00:00")
MAC_CLEAN = MAC_ADDRESS.replace(":", "").lower()

# Home Assistant Discovery topics
PREFIX = "homeassistant"
LIGHT_ID = f"ilumi_{MAC_CLEAN}"
DISCOVERY_TOPIC = f"{PREFIX}/light/{LIGHT_ID}/config"
STATE_TOPIC = f"ilumi/{LIGHT_ID}/state"
COMMAND_TOPIC = f"ilumi/{LIGHT_ID}/set"
AVAILABILITY_TOPIC = f"ilumi/{LIGHT_ID}/availability"

class MqttBridge:
    def __init__(self, mac):
        self.mac = mac
        self.sdk = IlumiSDK(mac)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"ilumi_bridge_{MAC_CLEAN}")
        
        if MQTT_USER and MQTT_PASS:
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Current state cache
        self.state = {
            "state": "OFF",
            "brightness": 255,
            "color": {
                "r": 255, "g": 255, "b": 255
            },
            "white_value": 0
        }

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected to MQTT Broker with result code {reason_code}")
        
        # Publish Home Assistant Discovery Payload
        discovery_payload = {
            "name": f"Ilumi Bulb ({self.mac})",
            "unique_id": LIGHT_ID,
            "stat_t": STATE_TOPIC,
            "cmd_t": COMMAND_TOPIC,
            "avty_t": AVAILABILITY_TOPIC,
            "schema": "json",
            "brightness": True,
            "color_mode": True,
            "supported_color_modes": ["rgbw"],
            "device": {
                "identifiers": [LIGHT_ID],
                "name": "Ilumi Smart Bulb",
                "manufacturer": "Ilumi",
                "model": "Mesh Bulb"
            }
        }
        
        self.client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
        self.client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        self.publish_state()
        
        # Subscribe to command topic
        self.client.subscribe(COMMAND_TOPIC)
        print(f"Subscribed to {COMMAND_TOPIC}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Received MQTT command: {payload}")
            
            # We must schedule the async SDK calls from the sync MQTT callback
            asyncio.run_coroutine_threadsafe(self.process_command(payload), self.loop)
        except Exception as e:
            print(f"Error processing message: {e}")

    async def process_command(self, payload):
        """Processes the JSON payload from Home Assistant and updates the bulb."""
        if "state" in payload:
            self.state["state"] = payload["state"]
            if payload["state"] == "ON":
                await self.sdk.turn_on()
            else:
                await self.sdk.turn_off()

        changed_color = False
        if "brightness" in payload:
            self.state["brightness"] = payload["brightness"]
            changed_color = True
            
        if "color" in payload:
            # HA sends {'r': x, 'g': x, 'b': x}
            self.state["color"] = payload["color"]
            changed_color = True
            
        if "white_value" in payload:
            self.state["white_value"] = payload["white_value"]
            changed_color = True

        if changed_color and self.state["state"] == "ON":
            r = self.state["color"].get("r", 255)
            g = self.state["color"].get("g", 255)
            b = self.state["color"].get("b", 255)
            w = self.state.get("white_value", 0)
            bri = self.state.get("brightness", 255)
            
            # Use fast mode for smoother slider dragging in Home Assistant
            await self.sdk.set_color_fast(r, g, b, w, bri)

        self.publish_state()

    def publish_state(self):
        """Publishes the current state back to HA for UI synchronization."""
        self.client.publish(STATE_TOPIC, json.dumps(self.state), retain=True)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        
        print("Connecting to local Bluetooth adapter...")
        # Start the persistent SDK connection
        async with self.sdk:
            print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            # We run the MQTT loop in a separate thread so it doesn't block asyncio
            self.client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            
            try:
                # Keep the main asyncio loop alive while the MQTT thread does its thing
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                print("Disconnecting...")
                self.client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
                self.client.loop_stop()
                self.client.disconnect()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ilumi MQTT Bridge for Home Assistant")
    parser.add_argument("--mac", type=str, required=False, help="MAC address of the Ilumi bulb")
    parser.add_argument("--broker", type=str, default="127.0.0.1", help="MQTT Broker IP")
    args = parser.parse_args()

    MQTT_BROKER = args.broker
    mac = args.mac or config.get_config("mac_address")

    if not mac:
        print("No MAC address specified in arguments or ilumi_config.json")
        exit(1)

    bridge = MqttBridge(mac)
    
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        print("Shutting down bridge.")
