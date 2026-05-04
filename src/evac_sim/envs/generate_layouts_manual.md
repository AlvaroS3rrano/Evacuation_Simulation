# Generated layouts

This folder stores automatically generated routing layouts for each environment.

The recommended workflow is:

1. Define or update the environment geometry in `evac_sim/envs/environment_data/<env>.py`.
2. Run `scripts/generate_layout.py` with the desired algorithm and parameters.
3. Inspect the generated `layout_preview.png`.
4. Optionally edit `layout.json` manually.
5. Configure the environment to load the selected JSON layout.

Each generation creates a timestamped folder:

```text
evac_sim/envs/generated_layouts/
└── YYYYMMDD_HHMMSS_<environment>_<algorithm>/
    ├── layout.json
    ├── layout_preview.png
    └── metadata.json
```

## Output files

### `layout.json`

Editable routing layout with:

- `metadata`
- `waypoints`
- `specific_areas`
- `nodes`
- `edges`
- `target_nodes`

### `layout_preview.png`

Visual inspection image with:

- walkable area
- generated cells / areas
- cell ids
- graph edges
- waypoint ids and acceptance radii

### `metadata.json`

Generation configuration and summary.

## Algorithms

### Greedy square grid

Creates large square cells by rasterizing the walkable area and repeatedly selecting the largest valid square.

Useful when:

- the environment has many orthogonal corridors;
- you want fewer nodes;
- manual editing after generation is expected.

Example:

```bash
python scripts/generate_layout.py   --env cruise_ship   --algorithm greedy   --min-cell-size 1.0   --greedy-min-square-size 2.0   --greedy-center-within
```

Important parameters:

| Parameter | Meaning |
|---|---|
| `--min-cell-size` | Base raster size. Smaller values create finer layouts. |
| `--greedy-min-square-size` | Minimum square size to keep. |
| `--greedy-center-within` | Accept cells whose center is inside the walkable area instead of requiring full coverage. |

### Quadtree

Recursively subdivides the walkable area into squares. Smaller squares appear near complex boundaries.

Useful when:

- the environment has irregular boundaries;
- you want adaptive spatial detail;
- you want a square-based baseline.

Example:

```bash
python scripts/generate_layout.py   --env cruise_ship   --algorithm quadtree   --min-cell-size 0.75   --max-cell-size 8.0   --accept-partial-min-cells
```

Important parameters:

| Parameter | Meaning |
|---|---|
| `--min-cell-size` | Smallest square side. |
| `--max-cell-size` | Maximum initial square size. |
| `--accept-partial-min-cells` | Keeps clipped boundary cells if their center is walkable. |

### Convex navmesh

Triangulates the walkable area and optionally subdivides large triangles. Each triangle is convex, so it can be used as a navigation node.

Useful when:

- you want a navigation mesh rather than an artificial square grid;
- routes should follow the actual spatial structure more closely;
- you want more precise waypoint-to-waypoint movement.

Example:

```bash
python scripts/generate_layout.py   --env cruise_ship   --algorithm convex_navmesh   --navmesh-min-area 0.02   --navmesh-max-area 0.25   --radius-ratio 0.18   --min-waypoint-radius 0.10   --max-waypoint-radius 0.30
```

Important parameters:

| Parameter | Meaning |
|---|---|
| `--navmesh-min-area` | Discards tiny triangles. |
| `--navmesh-max-area` | Subdivides triangles larger than this value. Lower means more precision. |
| `--radius-ratio` | Waypoint radius as a fraction of triangle size. |
| `--min-waypoint-radius` | Prevents waypoints from becoming too hard to reach. |
| `--max-waypoint-radius` | Prevents agents from completing waypoints too early. |

Recommended starting values:

```bash
--navmesh-min-area 0.02
--navmesh-max-area 0.25
--radius-ratio 0.18
--min-waypoint-radius 0.10
--max-waypoint-radius 0.30
```

If agents skip waypoints too early:

```bash
--max-waypoint-radius 0.20
```

If the graph is too coarse:

```bash
--navmesh-max-area 0.15
```

If the graph is too large or slow:

```bash
--navmesh-max-area 0.50
```

## Preview options

```bash
--show-edge-weights
--hide-cell-id
--hide-node-id
--dpi 300
```

## Loading a generated layout from an environment

Example:

```python
from pathlib import Path

from evac_sim.envs.layout_io import load_layout_json

layout = load_layout_json(
    Path(__file__).parent.parent / "generated_layouts" / "20260501_120000_cruise_ship_convex_navmesh" / "layout.json"
)

waypoints = layout["waypoints"]
specific_areas = layout["specific_areas"]
graph = layout["graph"]
targets = layout["target_nodes"]
```

## Recommended project policy

Do not edit generated folders in place after using them in experiments unless the folder is part of an intentional experiment.

For stable experiments:

1. Generate a layout.
2. Inspect the preview.
3. If needed, manually edit `layout.json`.
4. Commit the selected generated folder.
5. Reference that folder explicitly from the environment.

## Future improvements

The current system provides a solid and flexible foundation, but several enhancements could improve quality, performance and realism:

### Navmesh quality
- Merge adjacent triangles into larger convex polygons.
- Remove elongated or low-quality triangles (sliver filtering).
- Apply angle-based triangulation constraints.

### Routing improvements
- Use portal-based routing instead of centroid-to-centroid connections.
- Incorporate dynamic edge costs (risk, congestion, density).
- Add support for multi-layer or multi-floor navigation.

### Waypoints
- Replace centroid-based waypoints with portal midpoints.
- Adaptive waypoint placement depending on geometry complexity.
- Better control of waypoint density in large open areas.

### Performance
- Reduce node count via controlled merging.
- Cache generated layouts for reuse.
- Optimize graph construction for large environments.

### Tooling
- Interactive visualization/editor for layouts.
- Automatic validation checks (disconnected components, unreachable nodes).
- Integration with simulation metrics for iterative refinement.
