# Scenario configuration parameter reference

This document describes **all** the parameters a scenario (a "case") can have
inside a YAML file under `configs/`, based on what the code actually reads
(not on what appears in each YAML — many scenarios only use a subset). No
current YAML in the project uses 100% of the options: `congestion_heuristics.yaml`
is the most complete in terms of `grouping`/`congestion`, but has no `risk`
block; `management_building.yaml`/`study.yaml` have `risk` but no
`grouping`/`congestion`/`metrics`.

Source of truth (in case something changes and this document goes stale):

| Block | Code that parses it |
|---|---|
| top-level | `src/evac_sim/orchestration/experiment_setup.py` (`prepare_shared_resources`, `run_single_mode`) |
| `risk` | `src/evac_sim/orchestration/risk_config.py` |
| `grouping` | `src/evac_sim/orchestration/grouping_config.py` |
| `congestion` | `src/evac_sim/orchestration/congestion_config.py`, `src/evac_sim/orchestration/edge_capacity.py` |
| `metrics` | `src/evac_sim/metrics/config.py` + `configs/metrics/default_metrics.yaml` |
| validation | `src/evac_sim/envs/scripts/validate_scenario_config.py` (`evac-sim validate`) |

---

## 1. How the YAML files are combined (layers)

1. `configs/defaults.yaml` is always loaded first as the base.
2. The selected case (e.g. `basement:` inside `management_building.yaml`) is
   merged on top (`deep_merge`) — its keys override those from
   `defaults.yaml`.
3. If the case includes a `metrics:` block, it is merged separately on top of
   `configs/metrics/default_metrics.yaml` (independent of points 1-2).

This means you **don't need to repeat in every scenario** the values that are
already in `configs/defaults.yaml`:

```yaml
# configs/defaults.yaml (always applied, unless the case overrides it)
log_every_frames: 10
distance_to_agents: 0.4
distance_to_polygon: 0.5
strength_neighbor_repulsion: 2.6
range_neighbor_repulsion: 0.1
range_geometry_repulsion: 0.05
group_split_threshold: null
```

---

## 2. Top-level fields of a scenario

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `environment` | `str` | **Yes** | — | Name of the environment registered in `ENVIRONMENTS` (`environment_factory.py`): `corridor`, `cruise_ship`, `cruise_ship_v2`, `mall`, `simple_3x3`, `theme_park`, `management_building_basement`, `management_building_floor_0`, `management_building_floor_1`, `parallel_corridors`, `two_exits`, `short_vs_wide`, `comparing_algorithms`. |
| `sources` | `list[str]` | **Yes** | — | Node IDs where agents appear. |
| `agents` | `list[int]` | **Yes** | — | Number of agents per source; **same length as `sources`**, and `agents[i] > 0`. |
| `targets` | `list[str]` | **Yes** | — | Node IDs used as exits (`exit_stage`). Their `specific_areas[id]` must be a convex polygon (required by JuPedSim; if it isn't, `experiment_runner.create_stages` falls back to the `convex_hull`). |
| `mode_type` | `int` (0-6) | **Yes** | — | Which combination(s) of strategy are simulated. See the table in section 3. |
| `master_seed` | `int` | Recommended | *(if missing, `evac-sim validate` assigns a random one and warns)* | Root seed; `risk_seed` and `agent_position_seed` are derived from it (not directly: `random.Random(master_seed)` generates both in sequence). |
| `gamma` | `float > 0` | **Yes** | — | Weight of risk vs. distance when choosing a route (higher = more risk-averse). |
| `stairs_max_speed` | `float > 0` | **Yes** | — | Maximum speed (m/s) on nodes marked `is_stairs=True`. |
| `normal_max_speed` | `float > 0` | **Yes** | — | Maximum speed (m/s) on all other nodes. |
| `every_nth_frame_simulation` | `int > 0` | **Yes** | — | Every how many JuPedSim frames a simulation frame is recorded (affects the saved trajectory). |
| `every_nth_frame_animation` | `int > 0` | **Yes** | — | Every how many frames the risk simulation / animation is sampled. |
| `danger_visualization_frame` | `int > 0` | No | `None` | Frame used to render the danger map in visualizations. Legacy alias: `danger_frame`. |
| `distance_to_agents` | `float` | No | `0.4` (from `defaults.yaml`) | Minimum separation between agents when positioning them (`jps.distribute_by_number`). |
| `distance_to_polygon` | `float` | No | `0.5` (from `defaults.yaml`) | Minimum separation from the source polygon's edge when positioning agents. |
| `group_split_threshold` | `int` \| `null` | No | `null` (from `defaults.yaml`) | Max number of path nodes an agent may lag behind its group's leader (furthest-along agent) before being split off into a "lag" subgroup (`simulation/group_splitting.py:split_group_by_progress_threshold`). `null` or any negative value disables splitting entirely — a group never divides. |
| `log_every_frames` | `int` | No | `10` (from `defaults.yaml`) | Every how many frames a progress line is written to the log. |
| `strength_neighbor_repulsion` | `float` | No | `2.6` (from `defaults.yaml`) / `0` if also absent from defaults | Parameter of JuPedSim's `CollisionFreeSpeedModel` (repulsion between agents). |
| `range_neighbor_repulsion` | `float` | No | `0.1` (from `defaults.yaml`) / `0` | Range of repulsion between agents. |
| `range_geometry_repulsion` | `float` | No | `0.05` (from `defaults.yaml`) / `0` | Range of repulsion against obstacles/walls. |

> **Note:** `distance_to_agents`/`distance_to_polygon`/etc. default to `0`
> (not a "sensible" value) if the field is missing from both the case and
> `defaults.yaml` — in practice they will always be present because
> `defaults.yaml` defines them, but if it's ever removed from there, a
> scenario that doesn't declare it explicitly would silently end up at `0`.

---

## 3. `mode_type`: which simulations it triggers

Each mode (0-3) is a combination of **algorithm** (0 = efficient/shortest
path, 1 = agile/heuristic) and **awareness level** (0 = low, 1 = high) of the
agents. `mode_type` decides which subset of those 4 modes gets executed
(each mode = a full repetition of the simulation, with the same initial
agent assignment):

| `mode_type` | Modes run | Typical use |
|---|---|---|
| `0` | `[0, 1, 2, 3]` (all 4) | compare all 4 combinations at once |
| `1` | `[0, 1]` | two groups with different strategies (special case: here algorithm/awareness is assigned by `sources` index, not by the standard table) |
| `2` | `[0, 1]` | efficient, low vs. high awareness |
| `3` | `[2, 3]` | agile, low vs. high awareness |
| `4` | `[2]` | agile / low awareness only |
| `5` | `[1]` | efficient / high awareness only — **the recommended one** for scenarios where you want a single run with the optimal route and recalculation on danger |
| `6` | `[3]` | agile / high awareness only |

---

## 4. `risk` block (optional)

```yaml
risk:
  enabled: true
  risk_iterations: 7000
  risk_increase_chance: 0.005
  risk_threshold: 0.5
  propagation_threshold: 0.5
  starting_risks:
    - ["8", 1.0]        # [node_id, initial risk 0-1]
  risk_overrides:
    - [2350, "153", 0.6] # [frame, node_id, risk 0-1]
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `false` | If `false` (or the block is missing), there is no risk simulation: all nodes stay at risk `0.0`. |
| `risk_iterations` | `int >= 0` | `1500` | Number of iterations of the risk propagation simulation. |
| `risk_increase_chance` | `float [0,1]` | `0.05` | Probability that a node's risk increases at each iteration. |
| `risk_threshold` | `float [0,1]` | `0.5` | Threshold above which a node is considered "dangerous" for risk-aware routing. |
| `propagation_threshold` | `float [0,1]` | `0.5` | Risk threshold a neighboring node must reach for risk to propagate to it. |
| `starting_risks` | `list[[node_id, float 0-1]]` | `[]` | Nodes with an initial risk != 0 before propagation starts. |
| `risk_overrides` | `list[[frame, node_id, float 0-1]]` | `[]` | Forces a node's risk to a specific value at a specific frame (for scripted scenarios). |

> **Legacy compatibility:** if you don't use the `risk:` block, these same
> keys are still accepted at the scenario's top level (`risk_iterations`,
> `risk_increase_chance`, etc.) as a *fallback*. Using the explicit `risk:`
> block is recommended for new scenarios.

---

## 5. `grouping` block (optional)

Currently only used by `congestion_heuristics.yaml`. If omitted, all agents
from the same `source` are treated as a single indivisible group.

```yaml
grouping:
  enabled: true
  distribution: "normal"      # "fixed" | "normal" | "uniform"
  max_group_size: 5
  min_group_size: 1
  mean_group_size: 3
  std_group_size: 2
  seed: 3201
  order_by_route_proximity: true
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `enabled` | `bool` | No | `true` if the block exists | Set to `false` to disable grouping without removing the block. |
| `max_group_size` | `int > 0` | **Yes** (if `grouping` is present and enabled) | — | Maximum group size. |
| `min_group_size` | `int > 0` | No | `1` | Minimum group size (`<= max_group_size`). |
| `distribution` | `"fixed"` \| `"normal"` \| `"uniform"` | No | `"fixed"` | How a source's agents are split into groups of varying sizes. |
| `mean_group_size` (alias `mean`) | `float > 0` | Only if `distribution: normal` | `None` | Mean of the normal distribution of group sizes. |
| `std_group_size` (alias `std`) | `float >= 0` | Only if `distribution: normal` | `None` | Standard deviation. |
| `seed` | `int` | No | `None` (non-deterministic) | Seed for the `numpy.random.default_rng` used to split agents into groups. |
| `order_by_route_proximity` | `bool` | No | `true` | If `true`, groups are ordered/interleaved by how close their initial route is to the target (prevents one source from "monopolizing" the start of the simulation). |

---

## 6. `congestion` block (optional)

Currently only used by `congestion_heuristics.yaml`. Controls how agent
throughput through nodes/edges is limited and how the `h1`/`h2`/`h3`
heuristics (activated via `--heuristic`, see section 8) reserve capacity.

```yaml
congestion:
  node_capacity_multiplier: 1.0
  edge_flow_capacity_multiplier: 1.0
  block_edges_at_capacity: true
  no_path_policy: "wait"        # "raise" | "wait" | "keep_current"

  capacity_reservations:
    bucket_size_frames: 30
    search_horizon_frames: 300
    traversal_time_scale: 1.0
    node_hold_frames: null
    node_capacity_default: 20
    edge_flow_capacity_default: 10
    allow_oversized_group_reservations: true
    max_oversized_capacity_batches: 4
```

| Field | Type | Default | Description |
|---|---|---|---|
| `node_capacity_multiplier` | `float > 0` | `1.0` | Scales `node_capacity` for all nodes: `ceil(base_node_capacity * multiplier)`, minimum 1. The original value is kept in `base_node_capacity`. |
| `edge_flow_capacity_multiplier` | `float > 0` | `1.0` | Same as above but for edges' `flow_capacity` (`base_flow_capacity`). |
| `block_edges_at_capacity` | `bool` | `true` | If `true`, an edge/node at capacity blocks further agents until it frees up. |
| `no_path_policy` | `"raise"` \| `"wait"` \| `"keep_current"` | `"raise"` (also the default used by the `CongestionConfig` built when the whole block is missing) | What to do when no viable route is found: raise an error, wait, or keep the current route. |
| `capacity_reservations.bucket_size_frames` | `int > 0` | `30` | Size (in frames) of each time "bucket" used to reserve capacity. |
| `capacity_reservations.search_horizon_frames` | `int >= 0` | `300` | Time horizon (in frames) explored when looking for a free capacity slot. |
| `capacity_reservations.traversal_time_scale` | `float` | `1.0` | Scaling factor for the estimated traversal time of an edge when reserving. |
| `capacity_reservations.node_hold_frames` | `int > 0` \| `null` | `null` | Frames an agent holds a node's reservation after arriving (`null` = no extra hold). |
| `capacity_reservations.node_capacity_default` | `int > 0` | `20` | Capacity used for a node that has no `node_capacity` of its own. |
| `capacity_reservations.edge_flow_capacity_default` | `int > 0` | `10` | Capacity used for an edge that has no `flow_capacity` of its own. |
| `capacity_reservations.allow_oversized_group_reservations` | `bool` | `true` | If a group is larger than a resource's capacity, allows reserving it in several "batches" across multiple buckets instead of failing. |
| `capacity_reservations.max_oversized_capacity_batches` | `int > 0` \| `null` | `null` | Batch limit for the point above (`null`/`<=0` = no limit). |

> **⚠️ Obsolete / unsupported keys:** if the YAML includes
> `congestion.edge_capacity_multiplier` or `congestion.temporal_capacity`,
> config loading **fails explicitly** (they were removed on purpose — use
> `edge_flow_capacity_multiplier` and `capacity_reservations` instead).

> **⚠️ Keys that exist in `congestion_heuristics.yaml` but the code does NOT
> read (they do nothing, silently ignored):**
> `capacity_reservations.enabled`, `node_capacity_enabled`, `edge_flow_enabled`,
> `temporal_reservation_enabled`, `allow_waiting`, `block_at_capacity`, and the
> names `time_bucket_frames` / `temporal_horizon_frames` (the actual code
> expects `bucket_size_frames` / `search_horizon_frames`). By coincidence the
> three scenarios in `congestion_heuristics.yaml` use `30`/`300`, which match
> the real defaults — that's why it "works", but if you ever change those
> values in the YAML they will have no effect. Worth renaming or cleaning up
> in a separate pass.

---

## 7. `metrics` block (optional)

Merged on top of `configs/metrics/default_metrics.yaml` (not on top of
`defaults.yaml`). You only need to declare the keys you want to change.

```yaml
metrics:
  density:
    sample_every_frames: 10
    high_density_threshold: 12
```

Full schema inherited from `configs/metrics/default_metrics.yaml`:

| Block | Field | Default | Description |
|---|---|---|---|
| `raw_data` | `agent_area_data`, `group_path_data`, `paths`, `risk_data` | all `true` | Which raw data is saved during the simulation (needed to recompute derived metrics later without rerunning the simulation). |
| `outputs` | `write_density_metrics`, `write_evacuations_metrics`, `write_comparison_metrics`, `write_legacy_experiment_metrics` | all `true` | Which derived metrics files/tables are generated. |
| `density` | `enabled` | `true` | Enables density metric computation. |
| | `source_table` | `agent_area_data` | Source table. |
| | `sample_every_frames` | `25` | Every how many frames density is sampled. |
| | `high_density_threshold` | `10` | Threshold (agents/cell or similar) to count as "high density". |
| | `use_capacity_ratio` | `false` | If `true`, normalizes density against the area's capacity instead of an absolute threshold. |
| | `area_capacity_table` / `area_capacity_default` | `null` | Capacity source per area when `use_capacity_ratio: true`. |
| | `congestion_score_metric` | `p90_density_exposure` | Metric used as the aggregate "congestion score". |
| `evacuation` | `enabled` | `true` | Enables evacuation time metrics (min/avg/median/p90/max per group). |
| `route` | `enabled` | `true` | Enables route cost metrics. |
| `risk` | `enabled` | `false` | Enables risk-exposure derived metrics. |
| `comparison` | `main_metrics`, `aggregations`, `lower_is_better` | see `default_metrics.yaml` | Which metrics and aggregations are used when comparing modes/cases against each other. |

---

## 8. Parameters passed via CLI, **not** in the YAML

These are not read from the case config under any key — they only exist as
`evac-sim run` flags:

| Flag | Default | Description |
|---|---|---|
| `--heuristic` | `none` | `none` \| `h1` \| `h2` \| `h3` — capacity-reservation/rerouting heuristic for congestion. |
| `--horizon-k` | `6` | Number of future edges reserved by the `h2`/`h3` heuristic. |
| `--congestion-reroute-epsilon` | `0.1` | % route improvement required to force a reroute due to congestion. |
| `--case` / `--scenario` | — | Case to run (aliases of each other). |
| `--environment` | — | Runs all cases whose `environment` matches (cannot be combined with `--case`/`--scenario`). |
| `--output-format` | `json,csv` if used | `json`,`csv`,`html` — exports structured results (requires `--case`/`--scenario`). |
| `--out-dir` / `--output-dir` | `./runs/<timestamp>_<case>` | Output folder (aliases of each other). |
| `-v` / `--verbose` | `false` | `DEBUG`-level logs instead of `INFO`. |

---

## 9. Template with all fields

```yaml
my_scenario:
  environment: "management_building_basement"
  sources: ["278", "27", "111"]
  agents: [2, 5, 5]
  targets: ["5", "174"]
  mode_type: 5
  master_seed: 233

  gamma: 0.2
  stairs_max_speed: 0.6
  normal_max_speed: 1.2
  every_nth_frame_simulation: 3
  every_nth_frame_animation: 50
  danger_visualization_frame: 2500

  distance_to_agents: 0.3
  distance_to_polygon: 0.1
  group_split_threshold: 5
  log_every_frames: 10
  strength_neighbor_repulsion: 2.6
  range_neighbor_repulsion: 0.1
  range_geometry_repulsion: 0.05

  risk:
    enabled: true
    risk_iterations: 7000
    risk_increase_chance: 0.005
    risk_threshold: 0.5
    propagation_threshold: 0.5
    starting_risks:
    risk_overrides:

  grouping:
    enabled: true
    distribution: "normal"
    max_group_size: 5
    min_group_size: 1
    mean_group_size: 3
    std_group_size: 2
    seed: 3201
    order_by_route_proximity: true

  congestion:
    node_capacity_multiplier: 1.0
    edge_flow_capacity_multiplier: 1.0
    block_edges_at_capacity: true
    no_path_policy: "wait"
    capacity_reservations:
      bucket_size_frames: 30
      search_horizon_frames: 300
      traversal_time_scale: 1.0
      node_hold_frames:
      node_capacity_default: 20
      edge_flow_capacity_default: 10
      allow_oversized_group_reservations: true
      max_oversized_capacity_batches: 4

  metrics:
    density:
      sample_every_frames: 10
      high_density_threshold: 12
```

---

## 10. What each existing YAML is currently missing

| File | `risk` | `grouping` | `congestion` | `metrics` | Notes |
|---|---|---|---|---|---|
| `congestion_heuristics.yaml` | ❌ | ✅ | ✅ (with the obsolete keys from section 6) | ✅ (only `density`) | The most complete in terms of grouping/congestion; no risk, so all agents start with risk 0. |
| `management_building.yaml` | ✅ | ❌ | ❌ | ❌ | Uses node/edge capacities "as-is" (implicit 1.0 multiplier) and no grouping — each source is a single group. |
| `study.yaml` | ✅ | ❌ | ❌ | ❌ | Same as `management_building.yaml`. |
| `thesis.yaml` | ✅ | ❌ | ❌ | ❌ | Same as `management_building.yaml`. |

If you want a scenario that combines risk + grouping + congestion + density
metrics all at once, add the missing blocks following the template in
section 9 — there's no incompatibility between them, it's just that no YAML
in the repo has used all of them together so far.
