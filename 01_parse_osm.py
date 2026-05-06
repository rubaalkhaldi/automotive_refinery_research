"""
01_parse_osm.py
---------------
Parse the synthetic OSM-like JSON, detect junctions (nodes shared by 2+ ways or
road endpoints), convert GPS coordinates into local x/y meters,
and write two clean CSVs:
  - data/nodes.csv       : one row per OSM node, with lat/lon and local x/y
  - data/roads.csv       : one row per road
  - data/junctions.csv   : one row per junction, with participating road IDs
"""

import json
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent


def load_osm(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def project_to_local_xy(nodes: list[dict]) -> dict[str, dict]:
    """
    Convert lat/lon to local meter coordinates using an equirectangular
    projection around the selected area's center. This is accurate enough for
    small OSM extracts used in vehicle/road-network experiments.
    """
    origin_lat = sum(float(n["lat"]) for n in nodes) / len(nodes)
    origin_lon = sum(float(n["lon"]) for n in nodes) / len(nodes)
    origin_lat_rad = math.radians(origin_lat)
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = 111_320.0 * math.cos(origin_lat_rad)

    projected = {}
    for node in nodes:
        lat = float(node["lat"])
        lon = float(node["lon"])
        projected[node["id"]] = {
            "lat": lat,
            "lon": lon,
            "x": (lon - origin_lon) * meters_per_degree_lon,
            "y": (lat - origin_lat) * meters_per_degree_lat,
        }
    return projected


def detect_junctions(ways: list[dict]) -> dict[str, list[str]]:
    """
    A junction is any OSM node where roads meet/split, or where a road ends.
    Returns: { node_id -> [way_id, way_id, ...] }
    """
    node_to_ways = defaultdict(list)
    endpoint_nodes = set()
    for way in ways:
        node_ids = way["nodes"]
        endpoint_nodes.add(node_ids[0])
        endpoint_nodes.add(node_ids[-1])
        for node_id in node_ids:
            node_to_ways[node_id].append(way["id"])

    return {
        node_id: road_ids
        for node_id, road_ids in node_to_ways.items()
        if len(set(road_ids)) >= 2 or node_id in endpoint_nodes
    }


def clean_road(way: dict) -> dict:
    """Normalise and validate a single road record."""
    lanes = int(way.get("lanes", 1))
    width = parse_float(way.get("width"))
    if width is None:
        width = lanes * 3.5
    return {
        "id": way["id"],
        "name": way.get("name", "Unnamed").strip(),
        "highway": way.get("highway", "unclassified"),
        "lanes": lanes,
        "maxspeed": int(way.get("maxspeed", 50)),
        "width": f"{float(width):.3f}",
        "node_sequence": ",".join(way["nodes"]),  # ordered node list
    }


def parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    cleaned = str(value).split(";")[0].replace(",", ".")
    number = []
    for ch in cleaned:
        if ch.isdigit() or ch == ".":
            number.append(ch)
        elif number:
            break
    try:
        return float("".join(number))
    except ValueError:
        return None


def write_roads_csv(roads: list[dict], path: Path):
    fieldnames = ["id", "name", "highway", "lanes", "maxspeed", "width", "node_sequence"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(roads)
    print(f"  Wrote {len(roads)} roads → {path}")


def write_nodes_csv(node_coords: dict[str, dict], path: Path):
    fieldnames = ["osm_node_id", "lat", "lon", "x", "y"]
    rows = []
    for node_id, coords in sorted(node_coords.items()):
        rows.append({
            "osm_node_id": node_id,
            "lat": f"{coords['lat']:.7f}",
            "lon": f"{coords['lon']:.7f}",
            "x": f"{coords['x']:.3f}",
            "y": f"{coords['y']:.3f}",
        })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} nodes → {path}")


def write_junctions_csv(
    junctions: dict[str, list[str]],
    node_coords: dict[str, dict],
    path: Path,
):
    """
    Each junction row:
      junction_id, lat, lon, road_ids (semicolon-separated), degree
    junction_id is constructed as j_<node_id> for clarity.
    """
    fieldnames = ["junction_id", "osm_node_id", "lat", "lon", "x", "y", "road_ids", "degree"]
    rows = []
    for node_id, road_ids in sorted(junctions.items()):
        coords = node_coords.get(node_id, {"lat": None, "lon": None})
        unique_road_ids = sorted(set(road_ids))
        rows.append({
            "junction_id": f"j_{node_id}",
            "osm_node_id": node_id,
            "lat": f"{coords['lat']:.7f}",
            "lon": f"{coords['lon']:.7f}",
            "x": f"{coords['x']:.3f}",
            "y": f"{coords['y']:.3f}",
            "road_ids": ";".join(unique_road_ids),
            "degree": len(unique_road_ids),
        })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} junctions → {path}")


def main():
    print("=== Step 1: Parse & Clean OSM ===")
    osm = load_osm(DATA_DIR / "raw_osm.json")

    # Index nodes by id for coordinate lookup
    node_coords = project_to_local_xy(osm["nodes"])

    # Clean roads
    roads = [clean_road(w) for w in osm["ways"]]

    # Detect junctions
    junctions = detect_junctions(osm["ways"])

    # Write outputs
    write_nodes_csv(node_coords, DATA_DIR / "nodes.csv")
    write_roads_csv(roads, DATA_DIR / "roads.csv")
    write_junctions_csv(junctions, node_coords, DATA_DIR / "junctions.csv")

    print("\nSummary:")
    print(f"  Roads    : {len(roads)}")
    print(f"  Junctions: {len(junctions)}")


if __name__ == "__main__":
    main()
