"""
02_extract_scenario.py
----------------------
Select a smaller GPS/bbox scenario from the cleaned full-area cache.

The cache files are produced by 01_parse_osm.py. This script writes the active
nodes.csv, roads.csv, and junctions.csv files consumed by 02_build_models.py.

Examples:
  python3 02_extract_scenario.py --center-lat 47.4979 --center-lon 19.0402 --radius-m 300
  python3 02_extract_scenario.py --bbox 47.4950,19.0380,47.5000,19.0520
"""

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent


def read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict], fieldnames: list[str], path: Path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows -> {path}")


def bbox_from_center(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    delta_lat = radius_m / 111_320.0
    delta_lon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = tuple(float(part) for part in value.split(","))
    if len(parts) != 4:
        raise SystemExit("--bbox must be south,west,north,east")
    return parts


def parse_sequence(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def node_in_bbox(node: dict, bbox: tuple[float, float, float, float]) -> bool:
    south, west, north, east = bbox
    lat = float(node["lat"])
    lon = float(node["lon"])
    return south <= lat <= north and west <= lon <= east


def road_intersects_bbox(road: dict, node_lookup: dict[str, dict], bbox: tuple[float, float, float, float]) -> bool:
    return any(
        node_id in node_lookup and node_in_bbox(node_lookup[node_id], bbox)
        for node_id in parse_sequence(road["node_sequence"])
    )


def detect_junctions(roads: list[dict]) -> dict[str, list[str]]:
    node_to_roads = defaultdict(list)
    endpoint_nodes = set()
    for road in roads:
        node_ids = parse_sequence(road["node_sequence"])
        if len(node_ids) < 2:
            continue
        endpoint_nodes.add(node_ids[0])
        endpoint_nodes.add(node_ids[-1])
        for node_id in node_ids:
            node_to_roads[node_id].append(road["id"])

    return {
        node_id: road_ids
        for node_id, road_ids in node_to_roads.items()
        if len(set(road_ids)) >= 2 or node_id in endpoint_nodes
    }


def build_junction_rows(junctions: dict[str, list[str]], node_lookup: dict[str, dict]) -> list[dict]:
    rows = []
    for node_id, road_ids in sorted(junctions.items()):
        node = node_lookup[node_id]
        unique_road_ids = sorted(set(road_ids))
        rows.append({
            "junction_id": f"j_{node_id}",
            "osm_node_id": node_id,
            "lat": node["lat"],
            "lon": node["lon"],
            "x": node["x"],
            "y": node["y"],
            "road_ids": ";".join(unique_road_ids),
            "degree": len(unique_road_ids),
        })
    return rows


def extract_scenario(bbox: tuple[float, float, float, float]):
    cache_nodes = read_csv(DATA_DIR / "cache_nodes.csv")
    cache_roads = read_csv(DATA_DIR / "cache_roads.csv")
    node_lookup = {node["osm_node_id"]: node for node in cache_nodes}

    selected_roads = [
        road for road in cache_roads
        if road_intersects_bbox(road, node_lookup, bbox)
    ]
    selected_node_ids = {
        node_id
        for road in selected_roads
        for node_id in parse_sequence(road["node_sequence"])
    }
    selected_nodes = [
        node for node in cache_nodes
        if node["osm_node_id"] in selected_node_ids
    ]
    selected_junctions = build_junction_rows(
        detect_junctions(selected_roads),
        node_lookup,
    )

    write_csv(selected_nodes, ["osm_node_id", "lat", "lon", "x", "y"], DATA_DIR / "nodes.csv")
    write_csv(selected_roads, ["id", "name", "highway", "lanes", "maxspeed", "width", "node_sequence"], DATA_DIR / "roads.csv")
    write_csv(selected_junctions, ["junction_id", "osm_node_id", "lat", "lon", "x", "y", "road_ids", "degree"], DATA_DIR / "junctions.csv")

    print("\nSummary:")
    print(f"  Scenario roads    : {len(selected_roads)}")
    print(f"  Scenario nodes    : {len(selected_nodes)}")
    print(f"  Scenario junctions: {len(selected_junctions)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--center-lat", type=float)
    parser.add_argument("--center-lon", type=float)
    parser.add_argument("--radius-m", type=float, default=300)
    parser.add_argument("--bbox", help="south,west,north,east")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.bbox:
        bbox = parse_bbox(args.bbox)
    elif args.center_lat is not None and args.center_lon is not None:
        bbox = bbox_from_center(args.center_lat, args.center_lon, args.radius_m)
    else:
        raise SystemExit("Use either --bbox or --center-lat/--center-lon.")

    print("=== Step 2: Extract Scenario ===")
    print(f"  BBox: {bbox[0]:.7f},{bbox[1]:.7f},{bbox[2]:.7f},{bbox[3]:.7f}")
    extract_scenario(bbox)


if __name__ == "__main__":
    main()
