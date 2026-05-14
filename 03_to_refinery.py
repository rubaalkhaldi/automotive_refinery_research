"""
03_to_refinery.py
-----------------
Convert the generated graph model CSVs into a Refinery (.refinery) file.
"""

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent
OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(exist_ok=True)


def read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def safe_id(raw: str) -> str:
    """Turn an arbitrary string into a valid Refinery identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", raw)
    if s and s[0].isdigit():
        s = "_" + s
    return s


def block(title: str, lines: list[str]) -> str:
    sep = "/" * 60
    return f"\n{sep}\n// {title}\n{sep}\n" + "\n".join(lines) + "\n"


def escape_string(value: str) -> str:
    """Escape a string for use in Refinery string literals."""
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def convert_model_a(junctions: list[dict], roads: list[dict], edges: list[dict]) -> str:
    """Convert the requested Junction--Road--Junction model."""
    sections: list[str] = []
    schema = [
        "// Model A: Junctions and roads are both nodes",
        "// Roads connect to junctions through startsAt/endsAt relations.",
        "// Road geometry is stored as an encoded x,y point list on the Road.",
        "",
        "class Junction {",
        "    real x",
        "    real y",
        "    int degree",
        "    Road[] startsRoad opposite startsAt",
        "    Road[] endsRoad opposite endsAt",
        "}",
        "",
        "class Road {",
        "    string originalWayId",
        "    string name",
        "    string highway",
        "    int lanes",
        "    int maxspeed",
        "    real length",
        "    real rx",
        "    real ry",
        "    int pointCount",
        "    string geometry",
        "    Junction[1] startsAt opposite startsRoad",
        "    Junction[1] endsAt opposite endsRoad",
        "}",
        "",
        "abstract class TrafficSign {",
        "    Road[1] on",
        "}",
        "",
        "class UTurnSign extends TrafficSign.",
        "class PCrossingSign extends TrafficSign.",
    ]
    sections.append("\n".join(schema))

    junction_lines = []
    for j in junctions:
        jid = safe_id(j["node_id"])
        junction_lines.append(f"Junction({jid}).")
        junction_lines.append(f"    x({jid}): {j['x']}.")
        junction_lines.append(f"    y({jid}): {j['y']}.")
        junction_lines.append(f"    degree({jid}): {j['degree']}.")
        junction_lines.append("")
    sections.append(block("Junction instances", junction_lines))

    road_lines = []
    for road in roads:
        rid = safe_id(road["node_id"])
        road_lines.append(f"Road({rid}).")
        road_lines.append(f"    originalWayId({rid}): \"{escape_string(road['original_way_id'])}\".")
        road_lines.append(f"    name({rid}): \"{escape_string(road['name'])}\".")
        road_lines.append(f"    highway({rid}): \"{escape_string(road['highway'])}\".")
        road_lines.append(f"    lanes({rid}): {road['lanes']}.")
        road_lines.append(f"    maxspeed({rid}): {road['maxspeed']}.")
        road_lines.append(f"    length({rid}): {road['length']}.")
        road_lines.append(f"    rx({rid}): {road['rx']}.")
        road_lines.append(f"    ry({rid}): {road['ry']}.")
        road_lines.append(f"    pointCount({rid}): {road['point_count']}.")
        road_lines.append(f"    geometry({rid}): \"{escape_string(road['geometry'])}\".")
        road_lines.append("")
    sections.append(block("Road instances", road_lines))

    relation_lines = []
    for edge in edges:
        road_id = safe_id(edge["source"])
        junction_id = safe_id(edge["target"])
        relation_lines.append(f"{edge['kind']}({road_id}, {junction_id}).")
    relation_lines.append("")
    relation_lines.append("default !startsAt(*,*).")
    relation_lines.append("default !endsAt(*,*).")
    relation_lines.append("")
    relation_lines.append("error pred diffKindOfSign(x, y, r) <->")
    relation_lines.append("    on(x, r),")
    relation_lines.append("    on(y, r),")
    relation_lines.append("    UTurnSign(x),")
    relation_lines.append("    PCrossingSign(y).")
    sections.append(block("Road-junction relations", relation_lines))

    return "\n".join(sections)


def main():
    print("=== Step 4: Convert to Refinery ===")

    a_j