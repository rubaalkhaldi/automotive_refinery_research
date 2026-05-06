"""
03_to_refinery.py
-----------------
Convert graph model CSVs into Refinery (.refinery) files.
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
        "enum TrafficSignKind {",
        "    STOPSIGN, PCROSSING, UTURN",
        "}",
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
    sections.append(block("Road-junction relations", relation_lines))

    return "\n".join(sections)


def convert_model_b(nodes: list[dict], edges: list[dict]) -> str:
    """Convert the older junction-node comparison model."""
    sections: list[str] = []
    schema = [
        "// Model B: Junctions are nodes, roads are edges",
        "",
        "class Junction {",
        "    real x",
        "    real y",
        "    int degree",
        "    Junction[1..4] road opposite road",
        "}",
        "",
        "// A road part connects two junctions.",
        "// The road geometry is preserved as comments next to the facts.",
    ]
    sections.append("\n".join(schema))

    junc_lines = []
    for n in nodes:
        jid = safe_id(n["node_id"])
        junc_lines.append(f"Junction({jid}).")
        junc_lines.append(f"    x({jid}): {n['x']}.")
        junc_lines.append(f"    y({jid}): {n['y']}.")
        junc_lines.append(f"    degree({jid}): {n['degree']}.")
        junc_lines.append("")
    sections.append(block("Junction instances", junc_lines))

    edge_lines = []
    for e in edges:
        src = safe_id(e["source"])
        tgt = safe_id(e["target"])
        edge_lines.append(
            f"// {escape_string(e['via_road'])}: "
            f"name=\"{escape_string(e['road_name'])}\", "
            f"lanes={e['lanes']}, maxspeed={e['maxspeed']}, "
            f"highway=\"{escape_string(e['highway'])}\", "
            f"length={e['length']}, geometry=\"{escape_string(e['geometry'])}\"."
        )
        edge_lines.append(f"road({src}, {tgt}).road({tgt}, {src}).")
    edge_lines.append("")
    edge_lines.append("default !road(*,*).")
    sections.append(block("Road edges", edge_lines))

    return "\n".join(sections)


def main():
    print("=== Step 3: Convert to Refinery ===")

    a_junctions = read_csv(DATA_DIR / "model_a_junctions.csv")
    a_roads = read_csv(DATA_DIR / "model_a_roads.csv")
    a_edges = read_csv(DATA_DIR / "model_a_edges.csv")
    a_text = convert_model_a(a_junctions, a_roads, a_edges)
    out_a = OUT_DIR / "model_a_roads_as_nodes.refinery"
    out_a.write_text(a_text)
    print(f"  Wrote -> {out_a}")

    b_nodes = read_csv(DATA_DIR / "model_b_nodes.csv")
    b_edges = read_csv(DATA_DIR / "model_b_edges.csv")
    b_text = convert_model_b(b_nodes, b_edges)
    out_b = OUT_DIR / "model_b_junctions_as_nodes.refinery"
    out_b.write_text(b_text)
    print(f"  Wrote -> {out_b}")


if __name__ == "__main__":
    main()
