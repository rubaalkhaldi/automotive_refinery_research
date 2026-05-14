"""
02_build_models.py
------------------
Build graph CSVs from the cleaned OSM CSVs.

The generated Refinery model uses Junction and Road as nodes:
  Junction and Road are both model nodes.
  A Road node connects exactly two Junction nodes.
  Shape points stay inside the Road as geometry attributes.
"""

import csv
import math
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


def parse_sequence(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def distance(a: dict, b: dict) -> float:
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))


def geometry_for(node_ids: list[str], node_lookup: dict[str, dict]) -> str:
    return ";".join(
        f"{float(node_lookup[node_id]['x']):.3f},{float(node_lookup[node_id]['y']):.3f}"
        for node_id in node_ids
    )


def geometry_length(node_ids: list[str], node_lookup: dict[str, dict]) -> float:
    return sum(
        distance(node_lookup[a], node_lookup[b])
        for a, b in zip(node_ids, node_ids[1:])
    )


def coordinate_interval(node_ids: list[str], node_lookup: dict[str, dict], axis: str, width: float) -> str:
    values = [float(node_lookup[node_id][axis]) for node_id in node_ids]
    half_width = width / 2
    return f"{min(values) - half_width:.3f}..{max(values) + half_width:.3f}"


def split_roads_between_junctions(
    roads: list[dict],
    junctions: list[dict],
    node_lookup: dict[str, dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split each OSM way at junction/end nodes.

    The returned road rows are Road model nodes. Intermediate OSM points remain
    encoded in geometry, so they do not become main graph nodes.
    """
    junction_node_ids = {j["osm_node_id"] for j in junctions}
    junction_lookup = {j["osm_node_id"]: j for j in junctions}
    incident_counts = {j["junction_id"]: 0 for j in junctions}
    road_rows = []
    edge_rows = []

    for road in roads:
        osm_nodes = parse_sequence(road["node_sequence"])
        split_indexes = [
            index for index, node_id in enumerate(osm_nodes)
            if node_id in junction_node_ids
        ]

        for segment_index, (start_i, end_i) in enumerate(zip(split_indexes, split_indexes[1:]), start=1):
            segment_nodes = osm_nodes[start_i:end_i + 1]
            if len(segment_nodes) < 2:
                continue

            start_junction = junction_lookup[segment_nodes[0]]["junction_id"]
            end_junction = junction_lookup[segment_nodes[-1]]["junction_id"]
            road_id = f"{road['id']}_s{segment_index}"
            length = geometry_length(segment_nodes, node_lookup)
            width = float(road["width"])

            road_rows.append({
                "node_id": road_id,
                "original_way_id": road["id"],
                "name": road["name"],
                "highway": road["highway"],
                "lanes": road["lanes"],
                "maxspeed": road["maxspeed"],
                "width": f"{width:.3f}",
                "start_junction": start_junction,
                "end_junction": end_junction,
                "length": f"{length:.3f}",
                "rx": coordinate_interval(segment_nodes, node_lookup, "x", width),
                "ry": coordinate_interval(segment_nodes, node_lookup, "y", width),
                "point_count": len(segment_nodes),
                "geometry": geometry_for(segment_nodes, node_lookup),
            })
            edge_rows.append({"source": road_id, "target": start_junction, "kind": "startsAt"})
            edge_rows.append({"source": road_id, "target": end_junction, "kind": "endsAt"})
            incident_counts[start_junction] += 1
            incident_counts[end_junction] += 1

    junction_rows = []
    for j in junctions:
        junction_rows.append({
            "node_id": j["junction_id"],
            "osm_node_id": j["osm_node_id"],
            "lat": j["lat"],
            "lon": j["lon"],
            "x": j["x"],
            "y": j["y"],
            "degree": incident_counts[j["junction_id"]],
        })

    return junction_rows, road_rows, edge_rows


def validate_model_a(junctions: list[dict], roads: list[dict], edges: list[dict]):
    junction_ids = {j["node_id"] for j in junctions}
    road_ids = {r["node_id"] for r in roads}
    relation_counts = {road_id: 0 for road_id in road_ids}
    degree_counts = {junction_id: 0 for junction_id in junction_ids}

    for edge in edges:
        road_id = edge["source"]
        junction_id = edge["target"]
        if road_id not in road_ids:
            raise ValueError(f"Unknown road in edge: {road_id}")
        if junction_id not in junction_ids:
            raise ValueError(f"Unknown junction in edge: {junction_id}")
        if edge["kind"] not in {"startsAt", "endsAt"}:
            raise ValueError(f"Unknown edge kind: {edge['kind']}")
        relation_counts[road_id] += 1
        degree_counts[junction_id] += 1

    bad_roads = [road_id for road_id, count in relation_counts.items() if count != 2]
    if bad_roads:
        raise ValueError(f"Roads without exactly two junction relations: {bad_roads}")

    bad_degrees = [
        (j["node_id"], j["degree"], degree_counts[j["node_id"]])
        for j in junctions
        if int(j["degree"]) != degree_counts[j["node_id"]]
    ]
    if bad_degrees:
        raise ValueError(f"Junction degree mismatch: {bad_degrees}")


def build_model_a(roads: list[dict], junctions: list[dict], nodes: list[dict]):
    """Nodes = Junctions + Roads. Edges = startsAt/endsAt relations."""
    node_lookup = {node["osm_node_id"]: node for node in nodes}
    junction_rows, road_rows, edge_rows = split_roads_between_junctions(
        roads,
        junctions,
        node_lookup,
    )
    validate_model_a(junction_rows, road_rows, edge_rows)
    node_rows = (
        [{"node_id": j["node_id"], "kind": "Junction"} for j in junction_rows]
        + [{"node_id": r["node_id"], "kind": "Road"} for r in road_rows]
    )

    write_csv(
        node_rows,
        ["node_id", "kind"],
        DATA_DIR / "model_a_nodes.csv",
    )
    write_csv(
        junction_rows,
        ["node_id", "osm_node_id", "lat", "lon", "x", "y", "degree"],
        DATA_DIR / "model_a_junctions.csv",
    )
    write_csv(
        road_rows,
        [
            "node_id",
            "original_way_id",
            "name",
            "highway",
            "lanes",
            "maxspeed",
            "width",
            "start_junction",
            "end_junction",
            "length",
            "rx",
            "ry",
            "point_count",
            "geometry",
        ],
        DATA_DIR / "model_a_roads.csv",
    )
    write_csv(
        edge_rows,
        ["source", "target", "kind"],
        DATA_DIR / "model_a_edges.csv",
    )


def main():
    print("=== Step 3: Build Graph Model ===")
    nodes = read_csv(DATA_DIR / "nodes.csv")
    roads = read_csv(DATA_DIR / "roads.csv")
    junctions = read_csv(DATA_DIR / "junctions.csv")

    print("\n-- Junctions and roads as nodes --")
    build_model_a(roads, junctions, nodes)


if __name__ == "__main__":
    main()
