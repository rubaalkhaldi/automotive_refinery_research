"""
03_to_refinery.py
-----------------
Convert the two graph model CSVs into valid Refinery (.refinery) files.

Refinery syntax used:
  - `class` declarations for node and edge types
  - `pred` for binary relations (edges)
  - Instance facts using the `<ClassName>(<id>).` form
  - Attribute facts using `<attr>(<id>, <value>).`

We produce two files:
  output/model_a_roads_as_nodes.refinery
  output/model_b_junctions_as_nodes.refinery
"""

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent
OUT_DIR  = Path(__file__).parent
OUT_DIR.mkdir(exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

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


# ── Model A ───────────────────────────────────────────────────────────────────

def convert_model_a(nodes: list[dict], edges: list[dict]) -> str:
    """Convert Model A into the Refinery syntax expected by this repo."""
    sections: list[str] = []

    # ── schema ──
    schema = [
        "// Model A: Roads are nodes, junctions are edges",
        "",
        "class Road {",
        "    string name",
        "    string highway",
        "    int lanes",
        "    int maxspeed",
        "    TrafficSignKind[] signs",
        "    Road[1..4] junction opposite junction",
        "}",
        "",
        "enum TrafficSignKind {",
        "    STOPSIGN, PCROSSING, UTURN",
        "}",
        "",
        "// A junction connects two roads.",
        "// 'degree' records how many roads meet at that junction.",
        "// pred junction(road1: Road, road2: Road, via: string, degree: int).",
    ]
    sections.append("\n".join(schema))

    # ── Road instances ──
    road_lines = []
    for n in nodes:
        rid = safe_id(n["node_id"])
        road_lines.append(f"Road({rid}).")
        road_lines.append(f"    name({rid}): \"{escape_string(n['name'])}\".")
        road_lines.append(f"    highway({rid}): \"{escape_string(n['highway'])}\".")
        road_lines.append(f"    lanes({rid}): {n['lanes']}.")
        road_lines.append(f"    maxspeed({rid}): {n['maxspeed']}.")
        road_lines.append("")
    sections.append(block("Road instances", road_lines))

    # ── Junction edges ──
    edge_lines = []
    for e in edges:
        src = safe_id(e["source"])
        tgt = safe_id(e["target"])
        # Model A uses a binary opposite relation in the generated Refinery code,
        # so each CSV edge becomes facts in both directions.
        edge_lines.append(f"junction({src}, {tgt}).junction({tgt}, {src}).")
    edge_lines.append("")
    edge_lines.append("default !junction(*,*).")
    sections.append(block("Junction edges", edge_lines))

    return "\n".join(sections)


# ── Model B ───────────────────────────────────────────────────────────────────

def convert_model_b(nodes: list[dict], edges: list[dict]) -> str:
    """Convert Model B into the object-and-relation Refinery style."""
    sections: list[str] = []

    # ── schema ──
    schema = [
        "// Model B: Junctions are nodes, roads are edges",
        "",
        "class Junction {",
        "    real lat",
        "    real lon",
        "    int degree",
        "    Junction[1..4] road opposite road",
        "}",
        "",
        "// A road segment connects two junctions.",
        "// Each segment is emitted as a binary road relation in both directions.",
        "// Original road metadata is preserved as comments next to the facts.",
    ]
    sections.append("\n".join(schema))

    # ── Junction instances ──
    junc_lines = []
    for n in nodes:
        jid = safe_id(n["node_id"])
        junc_lines.append(f"Junction({jid}).")
        junc_lines.append(f"    lat({jid}): {n['lat']}.")
        junc_lines.append(f"    lon({jid}): {n['lon']}.")
        junc_lines.append(f"    degree({jid}): {n['degree']}.")
        junc_lines.append("")
    sections.append(block("Junction instances", junc_lines))

    # ── Road edges ──
    edge_lines = []
    for e in edges:
        src = safe_id(e["source"])
        tgt = safe_id(e["target"])
        edge_lines.append(
            f"// {escape_string(e['via_road'])}: "
            f"name=\"{escape_string(e['road_name'])}\", "
            f"lanes={e['lanes']}, maxspeed={e['maxspeed']}, "
            f"highway=\"{escape_string(e['highway'])}\"."
        )
        edge_lines.append(f"road({src}, {tgt}).road({tgt}, {src}).")
    edge_lines.append("")
    edge_lines.append("default !road(*,*).")
    sections.append(block("Road edges", edge_lines))

    return "\n".join(sections)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Step 3: Convert to Refinery ===")

    # Model A
    a_nodes = read_csv(DATA_DIR / "model_a_nodes.csv")
    a_edges = read_csv(DATA_DIR / "model_a_edges.csv")
    a_text  = convert_model_a(a_nodes, a_edges)
    out_a   = OUT_DIR / "model_a_roads_as_nodes.refinery"
    out_a.write_text(a_text)
    print(f"  Wrote → {out_a}")

    # Model B
    b_nodes = read_csv(DATA_DIR / "model_b_nodes.csv")
    b_edges = read_csv(DATA_DIR / "model_b_edges.csv")
    b_text  = convert_model_b(b_nodes, b_edges)
    out_b   = OUT_DIR / "model_b_junctions_as_nodes.refinery"
    out_b.write_text(b_text)
    print(f"  Wrote → {out_b}")


if __name__ == "__main__":
    main()
