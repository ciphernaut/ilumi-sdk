import asyncio
import json
import paho.mqtt.client as mqtt
import config
from ilumi_sdk import IlumiSDK

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USER = None
MQTT_PASS = None

PREFIX = "homeassistant"

class BulbNode:
    """Manages the MQTT and BLE mapping for a single bulb."""
    def __init__(self, bridge, mac, name):
        self.bridge = bridge
        self.mac = mac
        self.name = name
        self.sdk = IlumiSDK(mac)
        
        mac_clean = mac.replace(":", "").lower()
        self.light_id = f"ilumi_{mac_clean}"
        
        self.discovery_topic = f"{PREFIX}/light/{self.light_id}/config"
        self.state_topic = f"ilumi/{self.light_id}/state"
        self.command_topic = f"ilumi/{self.light_id}/set"
        self.availability_topic = f"ilumi/{self.light_id}/availability"

        self.state = {
            "state": "OFF",
            "brightness": 255,
            "color": { "r": 255, "g": 255, "b": 255 },
            "white_value": 0
        }

    def get_discovery_payload(self):
        return {
            "name": f"Ilumi Bulb ({self.name})",
            "unique_id": self.light_id,
            "stat_t": self.state_topic,
            "cmd_t": self.command_topic,
            "avty_t": self.availability_topic,
            "schema": "json",
            "brightness": True,
            "color_mode": True,
            "supported_color_modes": ["rgbw"],
            "device": {
                "identifiers": [self.light_id],
                "name": f"Ilumi {self.name}",
                "manufacturer": "Ilumi",
                "model": "Mesh Bulb"
            }
        }

    def publish_discovery(self):
        self.bridge.client.publish(self.discovery_topic, json.dumps(self.get_discovery_payload()), retain=True)
        self.publish_availability("online")
        self.publish_state()

    def publish_availability(self, status):
        self.bridge.client.publish(self.availability_topic, status, retain=True)

    def publish_state(self):
        self.bridge.client.publish(self.state_topic, json.dumps(self.state), retain=True)

    async def process_command(self, payload):
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
            self.state["color"]["r"] = payload["color"].get("r", self.state["color"]["r"])
            self.state["color"]["g"] = payload["color"].get("g", self.state["color"]["g"])
            self.state["color"]["b"] = payload["color"].get("b", self.state["color"]["b"])
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
            await self.sdk.set_color_fast(r, g, b, w, bri)

        self.publish_state()


class MqttBridge:
    def __init__(self, targets):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ilumi_bridge_master")
        if MQTT_USER and MQTT_PASS:
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.nodes = {}
        all_configs = config.get_all_bulbs()
        
        for mac in targets:
            name = all_configs.get(mac, {}).get("name", mac)
            self.nodes[mac] = BulbNode(self, mac, name)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected to MQTT Broker with result code {reason_code}")
        for node in self.nodes.values():
            node.publish_discovery()
            self.client.subscribe(node.command_topic)
            print(f"[{node.mac}] Published Discovery & Subscribed to {node.command_topic}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            print(f"Rx [{topic}]: {payload}")
            
            # Find which node this belongs to by command topic
            for node in self.nodes.values():
                if node.command_topic == topic:
                    asyncio.run_coroutine_threadsafe(node.process_command(payload), self.loop)
                    break
        except Exception as e:
            print(f"Error processing message: {e}")

    async def run(self):
        self.loop = asyncio.get_running_loop()
        
        print(f"Connecting to {len(self.nodes)} local Bluetooth adapter(s)...")
        for node in self.nodes.values():
            await node.sdk.__aenter__()

        try:
            print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            print("Disconnecting...")
            for node in self.nodes.values():
                node.publish_availability("offline")
            self.client.loop_stop()
            self.client.disconnect()
            for node in self.nodes.values():
                await node.sdk.__aexit__(None, None, None)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ilumi Multi-Bulb MQTT Bridge")
    parser.add_argument("--broker", type=str, default="127.0.0.1", help="MQTT Broker IP")
    parser.add_argument("--mac", type=str, help="Target a specific MAC address")
    parser.add_argument("--name", type=str, help="Target a specific bulb by name")
    parser.add_argument("--group", type=str, help="Target a specific group")
    parser.add_argument("--all", action="store_true", help="Target all enrolled bulbs")
    args = parser.parse_args()

    MQTT_BROKER = args.broker
    targets = config.resolve_targets(args.mac, args.name, args.group, args.all)

    if not targets:
        print("No targets resolved. Please run enroll.py or check your arguments.")
        exit(1)

    bridge = MqttBridge(targets)
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        print("Shutting down bridge.")
