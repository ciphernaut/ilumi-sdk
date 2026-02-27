import asyncio
import sys
import math
import random
import struct
import logging
import argparse
import json
import os
from typing import List, Dict, Any, Tuple
from ilumi_sdk import IlumiSDK, ILUMI_SERVICE_UUID
import config

# Physics parameters for force-directed layout
REPULSION_CONSTANT = 1200000.0 
ATTRACTION_CONSTANT = 0.1
ITERATIONS = 1200
DAMPING = 0.98

def rssi_to_distance(rssi: float) -> float:
    """Crude approximation of distance from RSSI."""
    rssi = max(-100, min(-30, rssi))
    # Higher RSSI (closer to 0) -> shorter distance
    dist = 10 ** ((-rssi - 10) / 25) * 50
    return dist

class MeshMapper:
    def __init__(self):
        self.bulbs: Dict[str, Dict[str, Any]] = {}
        self.links: Dict[Tuple[str, str], float] = {} # (mac1, mac2) -> avg_rssi
        self.backbone: Set[Tuple[str, str]] = set() # Links that form the strongest paths
        self.positions: Dict[str, List[float]] = {} # mac -> [x, y]
        self.name_map: Dict[str, str] = {}
        
        # Pre-load known bulbs from config
        self.config_bulbs = config.get_all_bulbs()
        for mac, data in self.config_bulbs.items():
            self.name_map[mac.upper()] = data.get("name", mac)

    def save_data(self, filename: str):
        """Saves crawled mesh data to a JSON file."""
        data = {
            "bulbs": self.bulbs,
            "links": {f"{k[0]}|{k[1]}": v for k, v in self.links.items()},
            "name_map": self.name_map
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Mesh data cached to {filename}")

    def load_data(self, filename: str):
        """Loads mesh data from a JSON file."""
        if not os.path.exists(filename):
            print(f"Error: Cache file {filename} not found.")
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
        self._calculate_backbone()
        print(f"Loaded {len(self.bulbs)} bulbs and {len(self.links)} links from {filename}")
        return True

    def _calculate_backbone(self):
        """Calculates a Maximum Spanning Tree to highlight the strongest links."""
        all_macs = set()
        for p in self.links.keys():
            all_macs.update(p)
        
        if not all_macs: return
        
        # Sort links by RSSI (strongest first)
        sorted_links = sorted(self.links.items(), key=lambda x: x[1], reverse=True)
        
        parent = {mac: mac for mac in all_macs}
        def find(i):
            if parent[i] == i: return i
            return find(parent[i])
        
        def union(i, j):
            root_i, root_j = find(i), find(j)
            if root_i != root_j:
                parent[root_i] = root_j
                return True
            return False

        self.backbone = set()
        for pair, rssi in sorted_links:
            # We filter out 0.0 or junk RSSI
            if rssi >= 0 or rssi < -100: continue
            
            if union(pair[0], pair[1]):
                self.backbone.add(pair)

    async def _resolve_names(self):
        """Try once to resolve names via scan."""
        try:
            discovered = await IlumiSDK.discover(timeout=2.0)
            for d in discovered:
                addr = d["address"].upper()
                if addr not in self.name_map:
                    self.name_map[addr] = d["name"] or "Unknown"
        except:
            pass

    async def gather_data(self, macs: List[str] = None, timeout: float = 3.0):
        print("Gathering bulb names...")
        await self._resolve_names()
        
        queue = []
        if not macs:
            if self.config_bulbs:
                for mac in self.config_bulbs:
                    queue.append(mac.upper())
            else:
                print("No bulbs in config. Scanning...")
                discovered = await IlumiSDK.discover(timeout)
                for d in discovered:
                    queue.append(d['address'].upper())
        else:
            for mac in macs:
                queue.append(mac.upper())

        print(f"Crawling mesh starting from {len(queue)} seed nodes...")
        
        visited = set()
        while queue:
            mac = queue.pop(0).upper()
            if mac in visited: continue
            visited.add(mac)

            name = self.name_map.get(mac, f"Node {mac[-5:]}")
            print(f"  Connecting to {name} ({mac})...")
            
            retries = 2
            neighbors = None
            for attempt in range(retries + 1):
                try:
                    sdk = IlumiSDK(mac)
                    async with sdk:
                        neighbors = await sdk.get_mesh_info()
                        if neighbors: break
                except Exception as e:
                    if "InProgress" in str(e) and attempt < retries:
                        await asyncio.sleep(1.5)
                    else:
                        break
            
            if neighbors:
                if mac not in self.bulbs:
                     self.bulbs[mac] = {"name": name, "raw_neighbors": []}
                self.bulbs[mac]["raw_neighbors"] = neighbors
                print(f"    Found {len(neighbors)} neighbors.")
                for n in neighbors:
                    n_mac = n["address"].upper()
                    if n_mac not in visited and n_mac not in queue:
                        queue.append(n_mac)

        self._process_links()
        self._calculate_backbone()

    def _process_links(self):
        """Cross-reference unidirectional links to create bidirectional averages."""
        temp_links = {}
        for mac, info in self.bulbs.items():
             for n in info["raw_neighbors"]:
                n_mac = n["address"].upper()
                rssi = n["rssi"]
                # Skip invalid-seeming RSSI
                if rssi == 0: continue
                
                pair = tuple(sorted([mac.upper(), n_mac.upper()]))
                if pair not in temp_links:
                    temp_links[pair] = []
                temp_links[pair].append(rssi)

        for pair, rssis in temp_links.items():
            self.links[pair] = sum(rssis) / len(rssis)

    def calculate_layout(self):
        """Force-directed layout optimized for maximum separation."""
        all_macs = sorted(list(set([m for p in self.links.keys() for m in p] + list(self.bulbs.keys()))))
        if not all_macs: return

        # Initial layout in a very wide circle
        center_x, center_y = 800, 500
        radius = 650
        for i, mac in enumerate(all_macs):
            angle = 2 * math.pi * i / len(all_macs)
            self.positions[mac] = [
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle)
            ]

        for i in range(ITERATIONS):
            forces = {mac: [0.0, 0.0] for mac in all_macs}
            
            # Repulsion (Between all nodes)
            for j, mac_a in enumerate(all_macs):
                for k, mac_b in enumerate(all_macs):
                    if j >= k: continue
                    dx, dy = self.positions[mac_a][0] - self.positions[mac_b][0], self.positions[mac_a][1] - self.positions[mac_b][1]
                    dist_sq = dx*dx + dy*dy or 0.1
                    dist = math.sqrt(dist_sq)
                    rep_f = REPULSION_CONSTANT / dist_sq
                    forces[mac_a][0] += (dx/dist) * rep_f; forces[mac_a][1] += (dy/dist) * rep_f
                    forces[mac_b][0] -= (dx/dist) * rep_f; forces[mac_b][1] -= (dy/dist) * rep_f

            # Attraction (Strengthened for Backbone links to pull them closer and central)
            for (mac_a, mac_b), avg_rssi in self.links.items():
                if mac_a not in self.positions or mac_b not in self.positions: continue
                dx, dy = self.positions[mac_a][0] - self.positions[mac_b][0], self.positions[mac_a][1] - self.positions[mac_b][1]
                dist = math.sqrt(dx*dx + dy*dy) or 0.1
                ideal_dist = rssi_to_distance(avg_rssi)
                
                # Backbone links attract more strongly to show hierarchy
                strength = ATTRACTION_CONSTANT * 2.0 if (mac_a, mac_b) in self.backbone else ATTRACTION_CONSTANT * 0.5
                att_f = strength * (dist - ideal_dist)
                
                forces[mac_a][0] -= (dx/dist) * att_f; forces[mac_a][1] -= (dy/dist) * att_f
                forces[mac_b][0] += (dx/dist) * att_f; forces[mac_b][1] += (dy/dist) * att_f

            damping = DAMPING * (1.0 - i/ITERATIONS)
            for mac in all_macs:
                self.positions[mac][0] += max(-50, min(50, forces[mac][0])) * damping
                self.positions[mac][1] += max(-50, min(50, forces[mac][1])) * damping
                # Weak center pull (Gravity)
                self.positions[mac][0] += (800 - self.positions[mac][0]) * 0.002
                self.positions[mac][1] += (500 - self.positions[mac][1]) * 0.002
                # Clamp to larger canvas
                self.positions[mac][0] = max(100, min(1500, self.positions[mac][0]))
                self.positions[mac][1] = max(100, min(900, self.positions[mac][1]))

    def print_matrix(self):
        """Prints context matrix."""
        all_macs = sorted(list(set([m for p in self.links.keys() for m in p] + list(self.bulbs.keys()))))
        if not all_macs: return
        names = [self.name_map.get(m, m[-5:]) for m in all_macs]
        max_n = max(len(n) for n in names)
        
        print("\n=== Mesh RSSI Matrix ===")
        header = " " * (max_n + 3) + "".join([f"{n[:8]:>9}" for n in names])
        print(header); print("-" * len(header))
        for i, m_r in enumerate(all_macs):
            row = f"{names[i]:<{max_n}} |"
            for m_c in all_macs:
                if m_r == m_c: row += "   --   "
                else:
                    pair = tuple(sorted([m_r, m_c]))
                    rssi = self.links.get(pair)
                    row += f"{int(rssi):>7} " if rssi else "   .    "
            print(row)
        print("-" * len(header))

    def generate_svg(self, filename: str = "mesh_map.svg"):
        """Generates premium SVG with PATH HIGHLIGHTING."""
        width, height = 1600, 1400
        all_macs = sorted(list(self.positions.keys()))
        names = [self.name_map.get(mac, self.name_map.get(mac.upper(), mac[-5:])) for mac in all_macs]
        
        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">']
        svg.append('''<defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" /><feComposite in="SourceGraphic" operator="over" /></filter>
    <filter id="strongGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" /><feComposite in="SourceGraphic" operator="over" /></filter>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e293b"/></linearGradient>
</defs><rect width="100%" height="100%" fill="url(#bg)" />''')

        # Grid
        for i in range(0, width, 100):
            svg.append(f'<line x1="{i}" y1="0" x2="{i}" y2="1000" stroke="#334155" stroke-width="0.5" opacity="0.1" />')
        for j in range(0, 1000, 100):
            svg.append(f'<line x1="0" y1="{j}" x2="{width}" y2="{j}" stroke="#334155" stroke-width="0.5" opacity="0.1" />')

        # 1. Secondary Links (Faint, Dashed)
        for (mac_a, mac_b), rssi in self.links.items():
            if (mac_a, mac_b) in self.backbone: continue
            if mac_a not in self.positions or mac_b not in self.positions: continue
            p1, p2 = self.positions[mac_a], self.positions[mac_b]
            t = (rssi + 100) / 65
            svg.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="#475569" stroke-width="1.5" stroke-dasharray="8,5" opacity="0.4" />')

        # 2. Backbone Links (Glowing, Strong)
        for (mac_a, mac_b) in self.backbone:
            if mac_a not in self.positions or mac_b not in self.positions: continue
            rssi = self.links[(mac_a, mac_b)]
            p1, p2 = self.positions[mac_a], self.positions[mac_b]
            t = (rssi + 100) / 65
            hue = 30 + (160 * max(0, min(1, t)))
            svg.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="hsla({hue}, 90%, 65%, 0.9)" stroke-width="{3+8*t}" stroke-linecap="round" filter="url(#strongGlow)"/>')

        # 3. Node Symbols
        for mac, pos in self.positions.items():
            is_active = mac in self.bulbs
            color = "#38bdf8" if is_active else "#94a3b8"
            svg.append(f'<circle cx="{pos[0]}" cy="{pos[1]}" r="25" fill="#0f172a" stroke="{color}" stroke-width="4" filter="url(#glow)"/><circle cx="{pos[0]}" cy="{pos[1]}" r="10" fill="{color}"/>')

        # 4. RSSI Labels on Backbone Links
        for (mac_a, mac_b) in self.backbone:
            rssi = self.links[(mac_a, mac_b)]
            p1, p2 = self.positions[mac_a], self.positions[mac_b]
            mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
            t = (rssi + 100) / 65
            hue = 30 + (160 * max(0, min(1, t)))
            svg.append(f'<circle cx="{mx}" cy="{my}" r="16" fill="#1e293b" stroke="hsla({hue}, 80%, 75%, 1)" stroke-width="2"/><text x="{mx}" y="{my+5}" fill="hsla({hue}, 80%, 75%, 1)" font-size="12" font-weight="bold" text-anchor="middle" font-family="sans-serif">{int(rssi)}</text>')

        # 5. Node Labels
        for i, mac in enumerate(all_macs):
            pos = self.positions[mac]
            name = self.name_map.get(mac, self.name_map.get(mac.upper(), f"Node {mac[-5:]}"))
            svg.append(f'<rect x="{pos[0]-75}" y="{pos[1]+35}" width="150" height="42" rx="8" fill="#1e293b" stroke="#334155" opacity="0.95"/><text x="{pos[0]}" y="{pos[1]+55}" fill="#f1f5f9" font-size="15" font-weight="bold" text-anchor="middle" font-family="sans-serif">{name}</text><text x="{pos[0]}" y="{pos[1]+70}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">{mac}</text>')

        # 6. Legends (Enhanced)
        svg.append('''
<g transform="translate(50, 50)">
    <rect width="320" height="150" rx="15" fill="#1e293b" stroke="#334155" opacity="0.95" />
    <text x="20" y="30" fill="#f8fafc" font-size="18" font-weight="bold" font-family="sans-serif">Path Viability Legend</text>
    
    <line x1="20" y1="60" x2="80" y2="60" stroke="#38bdf8" stroke-width="6" filter="url(#glow)" />
    <text x="95" y="65" fill="#cbd5e1" font-size="14" font-family="sans-serif">Primary Backbone (Strongest Path)</text>
    
    <line x1="20" y1="95" x2="80" y2="95" stroke="#475569" stroke-width="2" stroke-dasharray="8,5" />
    <text x="95" y="100" fill="#cbd5e1" font-size="14" font-family="sans-serif">Secondary/Redundant Mesh Links</text>
    
    <circle cx="30" cy="125" r="8" fill="#38bdf8" />
    <text x="50" y="130" fill="#cbd5e1" font-size="14" font-family="sans-serif">Active Bulb Node</text>
</g>''')

        # Matrix View (Bottom)
        mx, my = 200, 1100
        cell_w, cell_h = 120, 35
        svg.append(f'<g transform="translate({mx}, {my})"><text x="0" y="-25" fill="#f8fafc" font-size="20" font-weight="bold" font-family="sans-serif">Mesh Connectivity Matrix (Signal Quality)</text>')
        for i, name in enumerate(names):
            svg.append(f'<text x="{(i+1)*cell_w + cell_w/2}" y="15" fill="#94a3b8" font-size="13" text-anchor="middle" font-family="sans-serif">{name[:12]}</text>')
        for i, m_r in enumerate(all_macs):
            svg.append(f'<text x="0" y="{(i+1)*cell_h + 23}" fill="#f1f5f9" font-size="13" font-weight="bold" font-family="sans-serif" text-anchor="end">{names[i]}</text>')
            for j, m_c in enumerate(all_macs):
                x, y = (j+1)*cell_w, (i+1)*cell_h
                pair = tuple(sorted([m_r, m_c]))
                rssi = self.links.get(pair) if m_r != m_c else None
                cell_color = "#1e293b"
                val_text = "-"
                if rssi:
                    t = (rssi + 100) / 65
                    cell_color = f"hsla({30+160*t}, 70%, 20%, 0.6)"
                    val_text = str(int(rssi))
                svg.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{cell_color}" stroke="#334155"/><text x="{x+cell_w/2}" y="{y+23}" fill="#cbd5e1" font-size="12" text-anchor="middle" font-family="sans-serif">{val_text}</text>')
        svg.append('</g></svg>')

        with open(filename, "w") as f: f.write("\n".join(svg))
        print(f"Path-Optimized SVG saved to {filename}")

async def main():
    parser = argparse.ArgumentParser(description="Ilumi Mesh Path Mapper")
    parser.add_argument("--macs", nargs="+", help="Seed MAC addresses")
    parser.add_argument("--matrix", action="store_true", help="Print matrix to console")
    parser.add_argument("--save", help="Save mesh data to JSON file")
    parser.add_argument("--load", help="Load mesh data from JSON file")
    args = parser.parse_args()
    
    m = MeshMapper()
    
    if args.load:
        if not m.load_data(args.load):
            return
    else:
        await m.gather_data(macs=args.macs)
        if args.save:
            m.save_data(args.save)
            
    if not m.links and not m.bulbs:
        print("No data collected or loaded.")
        return
        
    print("Calculating path-weighted layout...")
    m.calculate_layout(); m.generate_svg()
    if args.matrix: m.print_matrix()

if __name__ == "__main__": asyncio.run(main())
