# Evac-Sim - Evacuation Simulation Framework

**Evac-Sim** is a research-oriented framework for simulating pedestrian evacuation scenarios with **JuPedSim**.
It is designed to support experimentation on evacuation dynamics, risk propagation, situational awareness,
and routing strategies in complex environments.

The project combines agent-based simulation, configurable scenario definitions, trajectory generation, risk modeling,
and post-run analysis artifacts in a reproducible workflow.

This repository is the implementation behind the following peer-reviewed publication:

> Á. Serrano, M. Lujak, G. Vizzari, "When shortest is not safest: Multi-agent evacuation with awareness
> and agile routing in dynamic hazards", *Simulation Modelling Practice and Theory*, vol. 150, 2026, 103294.
> https://doi.org/10.1016/j.simpat.2026.103294

See [Version Used for the SIMPAT Paper](#version-used-for-the-simpat-paper) below to reproduce the exact
code state used in the article, and `docs/` for an executable walkthrough of the project's objectives,
architecture, and representative scenarios (see [Notebooks](#-notebooks-optional)).

------------------------------------------------------------------------

## 📌 Project Overview

The main research question behind this project is whether always routing evacuees along the *shortest*
path is actually the *safest* choice once hazards (fire, smoke, flooding, ...) evolve dynamically and
unpredictably during an evacuation. The framework studies this by simulating pedestrian evacuation under
an ambient-intelligence assumption: sensors detect hazards and pedestrians receive real-time guidance
(variable message panels, mobile apps), and the framework evaluates how that guidance should be computed.

Two things are varied independently:

- **Situational awareness** — how much of the evolving hazard information an evacuee group perceives:
  - *low awareness* (reactive): the group only checks whether the **next** node on its route is dangerous.
  - *high awareness* (anticipatory): the group checks the **entire remaining route** ahead of time and
    reroutes as soon as any future node becomes dangerous.
- **Routing strategy** — how a new route is chosen once rerouting is triggered:
  - *efficient routing*: always the nominally fastest route (shortest path / Dijkstra).
  - *agile (centrality-based) routing*: prefers structurally well-connected, "agile" routes (high
    evacuation-betweenness centrality) that keep more rerouting options open if the hazard keeps spreading.

Crossing these two axes gives the four guidance configurations evaluated throughout the study. Performance
is measured with evacuation-time metrics (max/avg/median/p90) and **remaining-path risk (RPR)** statistics
computed from the time-dependent, node-level risk along each group's remaining route. The central finding
is that high situational awareness consistently improves both speed and safety, and that agile routing is
especially valuable when hazards emerge late or the environment is spatially complex.

------------------------------------------------------------------------

## ✨ Main Features

-   Agent-based evacuation simulation on **JuPedSim**, extended with a custom wayfinding/routing layer
-   Two routing strategies: efficient (shortest-path) and agile (evacuation-betweenness centrality)
-   Two situational-awareness regimes: low (reactive, next-node-only) and high (anticipatory, full remaining route)
-   Dynamic, time-indexed risk/hazard propagation over the environment graph
-   Leader-based group coordination (agents from the same source move and reroute together)
-   Congestion-aware routing heuristics (`h1`/`h2`/`h3`) with node/edge capacity reservations
-   Interactive Plotly animations and static trajectory/density plots
-   SQLite-based storage of trajectories, risk levels, and experiment metrics
-   Structured `result.json`/CSV/HTML export per scenario, suitable for external tooling/UIs
-   Modular, three-layer architecture (Risk / Routing / Agent simulation) mirroring the research design —
  see [Project Structure](#-project-structure)

------------------------------------------------------------------------

## 🗂 Project Structure

    Evacuation_Simulation/
    ├── configs/                    # scenario YAML files (see configs/CONFIG_REFERENCE.md)
    │ ├── study.yaml                #   corridor / cruise_ship / theme_park research scenarios
    │ ├── management_building.yaml  #   basement / floor_0 / floor_1 scenarios
    │ ├── defaults.yaml             #   shared defaults merged into every scenario
    │ └── CONFIG_REFERENCE.md       #   full field-by-field reference for the YAML schema
    │
    ├── docs/                       # extended documentation and executable notebooks
    │ ├── SCRIPTS_REFERENCE.md              # reference for every CLI command / script
    │ ├── MANAGEMENT_BUILDING_API.md        # guide for driving evac-sim from an external UI
    │ └── *.ipynb                           # executable walkthroughs (objectives, structure, scenarios)
    │
    ├── Notebooks/                  # interactive exploration / visualization notebooks
    │ ├── Main.ipynb
    │ ├── experiments.ipynb
    │ └── replay_existing_run.ipynb
    │
    ├── manuals/                    # PDF user manuals
    │
    ├── tools/                      # standalone analysis scripts (congestion heuristics, derived metrics, ...)
    │
    ├── results/ , runs/            # simulation outputs (git-ignored)
    │ └── <timestamp>_<case_name>/
    │   ├── config_resolved.yaml
    │   ├── metadata.json
    │   ├── logs/run.log
    │   └── artifacts/{images,db,csv}/
    │
    ├── src/evac_sim/                # the `evac_sim` package
    │ ├── cli.py                    #   entry point for the `evac-sim` command (run / validate / inspect)
    │ ├── runner.py                 #   orchestrates a full run from a YAML case
    │ ├── envs/                     #   graph-based environment representation + scenario registry
    │ ├── risk/                     #   Risk Simulation Module — hazard propagation over the graph
    │ ├── routing/                  #   Routing Module — efficient & agile path selection, congestion heuristics
    │ ├── simulation/                #   Agent Simulation Module — per-frame JuPedSim movement, group leadership
    │ ├── orchestration/             #   wires risk + routing + simulation together per experiment
    │ ├── core/                     #   shared data model (SimulationConfig, AgentGroup, ...)
    │ ├── db/                       #   SQLite persistence (trajectories, risk, experiment metrics)
    │ ├── analysis/ , metrics/       #   post-hoc computation of evacuation/risk/density metrics
    │ ├── io/                       #   YAML config loading/merging, run-directory & logging setup
    │ └── viz/                      #   Plotly/matplotlib plots and animations
    │
    ├── tests/
    │
    ├── pyproject.toml
    └── README.md

The `risk/`, `routing/`, and `simulation/` packages implement the three-module architecture described in
the paper (Risk Simulation Module, Routing Module, Agent Simulation Module), all operating over the shared
graph-based environment defined in `envs/`. `orchestration/` is the glue layer that builds an experiment
from a YAML case and drives the risk → routing → simulation loop.

------------------------------------------------------------------------

## ⚙️ Installation

### 1. Clone the repository

``` bash
git clone https://github.com/AlvaroS3rrano/Evacuation_Simulation.git
cd Evacuation_Simulation
```

### 2. Create and activate a virtual environment

``` bash
python -m venv .venv

# Windows
.venv/Scripts/activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install the project

``` bash
python -m pip install -U pip
pip install -e .
```

This installs the **evac-sim CLI** used to run simulations.

### 4. Optional development dependencies

``` bash
pip install -e .[dev]
```

------------------------------------------------------------------------

## ▶️ Usage

Experiments are defined in:
````text
./configs
````

The `evac-sim` CLI has three subcommands: `validate`, `run`, and `inspect`. Full flag-by-flag reference:
[`docs/SCRIPTS_REFERENCE.md`](docs/SCRIPTS_REFERENCE.md).

#### Validate a scenario before running it:

```bash
evac-sim validate --config configs/study.yaml --scenario example_case
```

#### Run a simulation:

```bash
evac-sim run --config study.yaml --case corridor_case_1
```

#### Run all cases that share the same environment:
```bash
evac-sim run --config study.yaml --environment corridor
```

#### Verbose execution:

```bash
evac-sim run --config study.yaml --case corridor_case_1 -v
```

#### Structured output for a single scenario (JSON/CSV/HTML, for external tooling or a UI):
```bash
evac-sim run --config study.yaml --scenario example_case \
    --output-dir ./runs/example_case --output-format json,csv,html
```
This writes a self-contained `result.json` (summary metrics, per-agent trajectories, risk levels),
`summary.csv`/`agents.csv`, and — with `html` — an interactive Plotly replay per routing mode. See
[`docs/MANAGEMENT_BUILDING_API.md`](docs/MANAGEMENT_BUILDING_API.md) for the full JSON schema and an
end-to-end example of driving this from an external application.

#### Congestion-aware routing heuristics:
```bash
evac-sim run --config study.yaml --case corridor_case_1 --heuristic h1
```
`--heuristic` accepts `none` (default), `h1`, `h2`, `h3`; `--horizon-k` tunes how many future edges `h2`/`h3`
reserve capacity for.

#### Inspect an environment's graph (nodes, capacities, layout):
```bash
evac-sim inspect --env corridor --layout-source current --show-node-id
```

#### Custom output directory for a single run:
````bash
evac-sim run --config study.yaml --case corridor_case_1 --out-dir ./runs/test_run
````
#### Output structure
Each single run generates:
````text
runs/<timestamp>_<case_name>/
````

Batch execution generates:
````text
runs/<timestamp>_<environment>/
├── batch_metadata.json
├── combined/
│   ├── results.db
│   ├── experiments.csv
│   └── experiment_metrics.csv
└── cases/
    ├── <case_name_1>/
    ├── <case_name_2>/
    └── ...
````
Each case inside a batch run stores its own configuration,
metadata, logs, and artifacts in its corresponding subdirectory
under `cases/`

------------------------------------------------------------------------

## 📓 Notebooks (Optional)

The repository includes several Jupyter notebooks intended for **interactive exploration,
visualization, and result analysis**.

- **`Notebooks/`** — general exploration/analysis notebooks:
  - `Main.ipynb` – interactive simulation workflow
  - `experiments.ipynb` – execution and analysis of experimental scenarios
  - `replay_existing_run.ipynb` – replay a stored run's trajectories as a Plotly animation
  - `centrality_vs_efficient_analysis.ipynb` – comparison of routing strategies

- **`docs/`** — executable documentation notebooks (run top-to-bottom to see real CLI output):
  - `management_building_api_walkthrough.ipynb` – runs and explains every `evac-sim` command against the
    `management_building` scenarios, for anyone integrating the CLI into an external interface
  - `project_overview.ipynb` – project objectives and architecture (as described in the SIMPAT paper),
    plus a run of the `study.yaml` `example_case`/`representative_case`/`representative_case_theme_park`
    scenarios discussed in the paper

To launch Jupyter from the project root:
````bash
jupyter notebook
````

Running notebooks against this project's `.venv` requires `ipykernel` (included in the `dev` extra, see
[Optional development dependencies](#4-optional-development-dependencies)).

> Note
> The recommended and reproducible way to run simulations is via the CLI (evac-sim).
> Notebooks are provided mainly for exploration, visualization, and analysis of results.

------------------------------------------------------------------------

## ⚙️ Configuration

Simulation cases are defined as YAML entries under `configs/`. A case's required fields are:

- `environment`: registered environment/layout to simulate (see `configs/CONFIG_REFERENCE.md` for the full list)
- `sources` / `agents`: origin nodes and how many agents spawn at each (same length, same order)
- `targets`: destination/exit nodes
- `mode_type`: which routing-strategy × awareness-level combination(s) to simulate (0-6)
- `gamma`, `stairs_max_speed`, `normal_max_speed`: routing/movement parameters
- `every_nth_frame_simulation`, `every_nth_frame_animation`, `danger_visualization_frame`: sampling/visualization frames
- `risk`: block enabling and parameterizing hazard propagation (`enabled`, `risk_iterations`,
  `risk_increase_chance`, `risk_threshold`, `propagation_threshold`, `starting_risks`, `risk_overrides`)

`master_seed` is recommended but optional — `evac-sim validate --output <file>` will assign and persist a
random one if it's missing. Optional `grouping`/`congestion`/`metrics` blocks are also available; the
**complete, authoritative field reference (types, defaults, which code reads each field) lives in
[`configs/CONFIG_REFERENCE.md`](configs/CONFIG_REFERENCE.md)** — this section only covers the common case.

Example:

```yaml
corridor_case_1:
  environment: "corridor"
  sources: ["16"]
  agents: [5]
  targets: ["1", "14"]
  mode_type: 0
  master_seed: 1001
  risk:
    enabled: true
    risk_iterations: 2000
    risk_increase_chance: 0.05
    starting_risks:
    risk_overrides:
    risk_threshold: 0.5
    propagation_threshold: 0.5
  gamma: 0.2
  stairs_max_speed: 0.6
  normal_max_speed: 1.2
  every_nth_frame_simulation: 3
  every_nth_frame_animation: 50
  danger_visualization_frame: 500
```

Run it with:

``` bash
evac-sim run --config study.yaml --case corridor_case_1
```

------------------------------------------------------------------------

## 📊 Results

Each execution generates:

    runs/<timestamp>_<case_name>/

Main outputs:

**Logs** - `logs/run.log`

**Resolved configuration and metadata** - `config_resolved,yaml` - `metadata.json`

**CSV summaries** - `experiments.csv` - `experiment_metrics.csv`

**SQLite databases** - `*_risks.db` - `*_paths.db` -
`*_group_paths_mode_X.db` - `agent_area_*_mode_X.db`

**Trajectories** - `*_mode_X.sqlite`

**Images and visual artifacts** - `artifacts/images/`

------------------------------------------------------------------------

## 🔁 Reproducibility

Each run stores:

-   configuration used
-   git commit hash
-   runtime metadata
-   execution logs

------------------------------------------------------------------------

## Version Used for the SIMPAT Paper

For reproducibility, the version of this project used for the **SIMPAT paper** corresponds to the 69th
commit in the repository history (chronological order from the initial commit):

```text
d1098b3
```
To reproduce this version:
```bash
git checkout d1098b3
```
------------------------------------------------------------------------

## 👤 Author

Álvaro Serrano\
Bachelor's Thesis / Research Project\
Evacuation simulation and intelligent environments

Co-authors of the associated SIMPAT publication: Marin Lujak and Giuseppe Vizzari.
