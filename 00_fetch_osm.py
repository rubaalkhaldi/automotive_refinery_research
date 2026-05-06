"""
00_fetch_osm.py
---------------
Fetch a small road extract from OpenStreetMap through Overpass and normalize it
to the raw_osm.json shape used by this project.

Examples:
  python3 00_fetch_osm.py --center-lat 47.4979 --center-lon 19.0402 --radius-m 300
  python3 00_fetch_osm.py --bbox 47.4950,19.0380,47.5000,19.0520
"""

import argparse
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def bbox_from_center(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    delta_lat = radius_m / 111_320.0
    delta_lon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon


def build_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return f"""
[out:json][timeout:25];
(
  way["highway"]({south},{west},{north},{east});
);
(._;>;);
out body;
"""


def fetch_overpass(query: str) -> dict:
    encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(OVERPASS_URL, data=encoded)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(overpass_json: dict) -> dict:
    nodes = {}
    ways = []

    for element in overpass_json.get("elements", []):
        if element.get("type") == "node":
            nodes[str(element["id"])] = {
                "id": str(element["id"]),
                "lat": element["lat"],
                "lon": element["lon"],
            }

    for element in overpass_json.get("elements", []):
        if element.get("type") != "way":
            continue
        tags = element.get("tags", {})
        node_ids = [str(node_id) for node_id in element.get("nodes", []) if str(node_id) in nodes]
        if len(node_ids) < 2:
            continue
        ways.append({
            "id": f"w{element['id']}",
            "name": tags.get("name", "Unnamed"),
            "highway": tags.get("highway", "unclassified"),
            "lanes": parse_int(tags.get("lanes"), 1),
            "maxspeed": parse_maxspeed(tags.get("maxspeed"), 50),
            "width": parse_float(tags.get("width")),
            "nodes": node_ids,
        })

    used_node_ids = {node_id for way in ways for node_id in way["nodes"]}
    return {
        "nodes": [nodes[node_id] for node_id in sorted(used_node_ids)],
        "ways": ways,
    }


def parse_int(value: object, default: int) -> int:
    try:
        return int(str(value).split(";")[0])
    except (TypeError, ValueError):
        return default


def parse_maxspeed(value: object, default: int) -> int:
    if value is None:
        return default
    digits = "".join(ch for ch in str(value).split(";")[0] if ch.isdigit())
    return int(digits) if digits else default


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--center-lat", type=float)
    parser.add_argument("--center-lon", type=float)
    parser.add_argument("--radius-m", type=float, default=300)
    parser.add_argument("--bbox", help="south,west,north,east")
    parser.add_argument("--output", default=str(DATA_DIR / "raw_osm.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    if args.bbox:
        bbox = tuple(float(part) for part in args.bbox.split(","))
        if len(bbox) != 4:
            raise SystemExit("--bbox must be south,west,north,east")
    elif args.center_lat is not None and args.center_lon is not None:
        bbox = bbox_from_center(args.center_lat, args.center_lon, args.radius_m)
    else:
        raise SystemExit("Use either --bbox or --center-lat/--center-lon.")

    print("=== Step 0: Fetch OSM ===")
    overpass_json = fetch_overpass(build_query(bbox))
    normalized = normalize(overpass_json)
    output = Path(args.output)
    output.write_text(json.dumps(normalized, indent=2))
    print(f"  Wrote {len(normalized['ways'])} ways and {len(normalized['nodes'])} nodes -> {output}")


if __name__ == "__main__":
    main()
