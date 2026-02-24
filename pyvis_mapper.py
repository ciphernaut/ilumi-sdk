import json
import os
import argparse
import networkx as nx
from pyvis.network import Network
import config

def rssi_to_weight(rssi):
    """Convert RSSI to a weight for MST. Stronger (higher) RSSI should have lower weight."""
    return -rssi

def get_color_for_rssi(rssi):
    """Return a color based on RSSI strength."""
    if rssi >= -70: return "#22c55e" # Green
    if rssi >= -85: return "#eab308" # Yellow
    return "#ef4444" # Red

class PyvisMapper:
    def __init__(self):
        self.bulbs = {}
        self.links = {}
        self.name_map = {}
        self.config_bulbs = config.get_all_bulbs()
        for mac, data in self.config_bulbs.items():
            self.name_map[mac.upper()] = data.get("name", mac)

    def load_data(self, filename):
        if not os.path.exists(filename):
            print(f"Error: {filename} not found.")
            return False
        
        with open(filename, "r") as f:
            data = json.load(f)
        
        self.bulbs = data.get("bulbs", {})
        links_raw = data.get("links", {})
        self.links = {}
        for k, v in links_raw.items():
            macs = k.split("|")
            self.links[tuple(sorted(macs))] = v
        
        self.name_map.update(data.get("name_map", {}))
        return True

    def generate_html(self, output_file="mesh_map.html"):
        # Create NetworkX graph to calculate backbone
        G = nx.Graph()
        for mac, info in self.bulbs.items():
            G.add_node(mac.upper(), label=self.name_map.get(mac.upper(), mac[-5:]))
        
        for (m1, m2), rssi in self.links.items():
            if rssi < 0: # Only add real links
                G.add_edge(m1, m2, weight=rssi_to_weight(rssi), rssi=rssi)
        
        # Calculate Backbone: MST + Ensure at least 2 paths per node for redundancy
        backbone_edges = set()
        mst = nx.minimum_spanning_tree(G, weight='weight')
        backbone_edges.update(tuple(sorted(e)) for e in mst.edges())
        
        for node in G.nodes():
            # Get edges for this node sorted by RSSI
            edges = sorted(G.edges(node, data=True), key=lambda x: x[2]['rssi'], reverse=True)
            # Add top 2 paths to backbone for redundancy
            for i in range(min(2, len(edges))):
                backbone_edges.add(tuple(sorted((edges[i][0], edges[i][1]))))

        # Initialize Pyvis Network
        net = Network(height="900px", width="100%", bgcolor="#0f172a", font_color="white", heading="Ilumi Mesh Multi-Path Explorer")
        
        # Physics settings for a smooth, premium feel
        net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=250, spring_strength=0.001, damping=0.95)

        # Add Nodes
        for mac in G.nodes():
            name = self.name_map.get(mac, mac)
            is_active = mac in self.bulbs
            
            # Aesthetics
            color = "#38bdf8" if is_active else "#94a3b8"
            size = 32 if is_active else 22
            
            tooltip = f"<b>Name:</b> {name}<br><b>MAC:</b> {mac}<br><b>Status:</b> {'Active' if is_active else 'Neighbor Only'}"
            
            net.add_node(mac, label=name, title=tooltip, color=color, size=size, borderWidth=3, shadow=True)

        # Add Edges
        for m1, m2, data in G.edges(data=True):
            rssi = data['rssi']
            pair = tuple(sorted([m1, m2]))
            is_backbone = pair in backbone_edges
            
            # Color based on signal quality
            if rssi >= -60: color = "#22c55e"   # Excellent (Green)
            elif rssi >= -75: color = "#84cc16" # Good (Lime)
            elif rssi >= -85: color = "#eab308" # Fair (Yellow)
            else: color = "#ef4444"             # Poor (Red)

            # Visual weight: Stronger signals should be thicker
            normalized_weight = max(1, (rssi + 100) / 4) 
            
            width = normalized_weight if is_backbone else 1
            opacity = 0.95 if is_backbone else 0.25
            label = f"{int(rssi)} dBm" # SHOW ALL LABELS
            
            # Backbone links get a glow/shadow
            shadow = {"enabled": True, "color": color, "size": 15} if is_backbone else False
            
            net.add_edge(m1, m2, title=f"RSSI: {rssi} dBm", color=color, 
                         width=width, opacity=opacity, label=label, 
                         font={'size': 14, 'color': 'white', 'strokeWidth': 0},
                         shadow=shadow, dashes=not is_backbone)

        net.save_graph(output_file)
        print(f"Interactive Multi-Path map generated: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ilumi Pyvis Mesh Mapper")
    parser.add_argument("--load", default="mesh_data.json", help="Load mesh data from JSON file")
    args = parser.parse_args()
    
    m = PyvisMapper()
    if m.load_data(args.load):
        m.generate_html()
