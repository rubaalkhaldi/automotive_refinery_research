"""
02_build_models.py
------------------
Build two graph representations from the cleaned roads/junctions CSVs.

Model A — Roads as Nodes:
  nodes : roads.csv  (id, name, lanes, maxspeed, highway)
  edges : for each junction, emit one edge per pair of roads that meet there
          edge columns: source_road, target_road, via_junction, junction_degree

Model B — Junctions as Nodes:
  nodes : junctions.csv  (junction_id, lat, lon, degree)
  edges : for each road, emit one edge per consecutive junction pair along it
          edge columns: source_junction, target_junction, via_road,
                        road_name, lanes, maxspeed, highway
"""

import csv
from itertools import combinations
from pathlib import Path

DATA_DIR = Path(__file__).parent


# ── helpers ──────────────────────────────────────────────────────────────────

def read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict], fieldnames: list[str], path: Path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows → {path}")


# ── Model A ───────────────────────────────────────────────────────────────────

def build_model_a(roads: list[dict], junctions: list[dict]):
    """
    Nodes = roads.
    Edges = pairs of roads that share a junction.
    An edge is undirected so we emit (road_a, road_b) with road_a < road_b
    to avoid duplicates.
    """
    # nodes: just the road attributes we care about
    node_rows = [
        {
            "node_id": r["id"],
            "name": r["name"],
            "highway": r["highway"],
            "lanes": r["lanes"],
            "maxspeed": r["maxspeed"],
        }
        for r in roads
    ]

    # edges: for each junction, take every pair of roads meeting there
    edge_rows = []
    seen = set()
    for junc in junctions:
        road_ids = sorted(junc["road_ids"].split(";"))
        for r1, r2 in combinations(road_ids, 2):
            key = (r1, r2, junc["junction_id"])
            if key not in seen:
                seen.add(key)
                edge_rows.append({
                    "source": r1,
                    "target": r2,
                    "via_junction": junc["junction_id"],
                    "junction_degree": junc["degree"],
                })

    write_csv(node_rows, ["node_id", "name", "highway", "lanes", "maxspeed"],
              DATA_DIR / "model_a_nodes.csv")
    write_csv(edge_rows, ["source", "target", "via_junction", "junction_degree"],
              DATA_DIR / "model_a_edges.csv")


# ── Model B ───────────────────────────────────────────────────────────────────

def build_model_b(roads: list[dict], junctions: list[dict]):
    """
    Nodes = junctions.
    Edges = roads that connect two junctions.

    For each road we look at its ordered node sequence and find which nodes
    are junctions.  Each consecutive pair of junctions along the road
    becomes a directed edge (preserving road direction).
    """
    # Build lookup: osm_node_id → junction_id
    node_to_junc = {j["osm_node_id"]: j["junction_id"] for j in junctions}

    # nodes
    node_rows = [
        {
            "node_id": j["junction_id"],
            "osm_node_id": j["osm_node_id"],
            "lat": j["lat"],
            "lon": j["lon"],
            "degree": j["degree"],
        }
        for j in junctions
    ]

    # edges
    edge_rows = []
    road_lookup = {r["id"]: r for r in roads}

    for road in roads:
        osm_nodes = road["node_sequence"].split(",")
        # collect only the nodes that are junctions, in order
        junc_sequence = [
            node_to_junc[n] for n in osm_nodes if n in node_to_junc
        ]
        # consecutive pairs → edges
        for i in range(len(junc_sequence) - 1):
            src = junc_sequence[i]
            tgt = junc_sequence[i + 1]
            edge_rows.append({
                "source": src,
                "target": tgt,
                "via_road": road["id"],
                "road_name": road["name"],
                "lanes": road["lanes"],
                "maxspeed": road["maxspeed"],
                "highway": road["highway"],
            })

    write_csv(node_rows, ["node_id", "osm_node_id", "lat", "lon", "degree"],
              DATA_DIR / "model_b_nodes.csv")
    write_csv(
        edge_rows,
        ["source", "target", "via_road", "road_name", "lanes", "maxspeed", "highway"],
        DATA_DIR / "model_b_edges.csv",
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Step 2: Build Graph Models ===")
    roads = read_csv(DATA_DIR / "roads.csv")
    junctions = read_csv(DATA_DIR / "junctions.csv")

    print("\n-- Model A: Roads as nodes --")
    build_model_a(roads, junctions)

    print("\n-- Model B: Junctions as nodes --")
    build_model_b(roads, junctions)


if __name__ == "__main__":
    main()
