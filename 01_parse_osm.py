"""
01_parse_osm.py
---------------
Parse the synthetic OSM-like JSON, detect junctions (nodes shared by 2+ ways),
and write two clean CSVs:
  - data/roads.csv       : one row per road
  - data/junctions.csv   : one row per junction, with participating road IDs
"""

import json
import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent


def load_osm(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def detect_junctions(ways: list[dict]) -> dict[str, list[str]]:
    """
    A junction is any OSM node that appears in 2 or more ways.
    Returns: { node_id -> [way_id, way_id, ...] }
    """
    node_to_ways = defaultdict(list)
    for way in ways:
        for node_id in way["nodes"]:
            node_to_ways[node_id].append(way["id"])

    return {
        node_id: road_ids
        for node_id, road_ids in node_to_ways.items()
        if len(road_ids) >= 2
    }


def clean_road(way: dict) -> dict:
    """Normalise and validate a single road record."""
    return {
        "id": way["id"],
        "name": way.get("name", "Unnamed").strip(),
        "highway": way.get("highway", "unclassified"),
        "lanes": int(way.get("lanes", 1)),
        "maxspeed": int(way.get("maxspeed", 50)),
        "node_sequence": ",".join(way["nodes"]),  # ordered node list
    }


def write_roads_csv(roads: list[dict], path: Path):
    fieldnames = ["id", "name", "highway", "lanes", "maxspeed", "node_sequence"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(roads)
    print(f"  Wrote {len(roads)} roads → {path}")


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
    fieldnames = ["junction_id", "osm_node_id", "lat", "lon", "road_ids", "degree"]
    rows = []
    for node_id, road_ids in sorted(junctions.items()):
        coords = node_coords.get(node_id, {"lat": None, "lon": None})
        rows.append({
            "junction_id": f"j_{node_id}",
            "osm_node_id": node_id,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "road_ids": ";".join(sorted(road_ids)),
            "degree": len(road_ids),
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
    node_coords = {n["id"]: {"lat": n["lat"], "lon": n["lon"]} for n in osm["nodes"]}

    # Clean roads
    roads = [clean_road(w) for w in osm["ways"]]

    # Detect junctions
    junctions = detect_junctions(osm["ways"])

    # Write outputs
    write_roads_csv(roads, DATA_DIR / "roads.csv")
    write_junctions_csv(junctions, node_coords, DATA_DIR / "junctions.csv")

    print("\nSummary:")
    print(f"  Roads    : {len(roads)}")
    print(f"  Junctions: {len(junctions)}")


if __name__ == "__main__":
    main()
