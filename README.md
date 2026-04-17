# Evac-Sim - Evacuation Simulation Framework

**Evac-Sim** is a research-oriented framework for simulating pedestrian evacuation scenarios with **JuPedSim**.
It is designed to support experimentation on evacuation dynamics, risk propagation, situational awareness,
and routing strategies in complex environments.

The project combines agent-based simulation, configurable scenario definitions, trajectory generation, risk modeling,
and post-run analysis artifacts in a reproducible workflow.

------------------------------------------------------------------------

## 📌 Project Overview

The main goal of this project is to study how different evacuation conditions affect agent behavior and evacuation outcomes.
In particular, the framework focuses on:

- agent-based pedestrian evacuation simulation using **JuPedSim**
- custom environments and walkable area definitions
- dynamic risk computation during the evacuation process
- comparison of routing strategies under different conditions
- analysis of how environmental awareness influences decision-making
- storage of simulation outputs for later inspection and visualization

A central research aspect of the framework is the distinction between agents with different levels of environmental
awareness, and the comparison between efficient routing and centrality-based routing strategies.

------------------------------------------------------------------------

## ✨ Main Features

-   Agent-based evacuation simulation
-   Multiple routing strategies
-   Risk modeling during evacuation
-   Interactive animations using Plotly
-   SQLite-based storage of simulation data
-   Modular and extensible architecture
-   Modeling of different levels of agent environmental awareness
-   Comparison of routing strategies:
    -   Efficient routing based on *k-shortest paths*
    -   Centrality-based routing strategies (agile routing)

------------------------------------------------------------------------

## 🗂 Project Structure

    Evacuation_Simulation/
    ├── configs/
    │ └── study.yaml
    │
    ├── Notebooks/
    │ └── main.ipynb
    │
    ├── results/
    │ └── images/
    │     └── readme/
    │
    ├── runs/
    │ └── <timestamp>_<case_name>/
    │   ├── config_resolved.yaml
    │   ├── metadata.json
    │   ├── logs/
    │   │   └── run.log
    │   └── artifacts/
    │       ├── images/
    │       ├── db/
    │       └── csv/
    │
    ├── src/
    │ └── evac_sim/
    │   ├── analysis/
    │   ├── core/
    │   ├── db/
    │   ├── envs/
    │   ├── io/
    │   ├── orchestration/
    │   ├── risk/
    │   ├── routing/
    │   ├── simulation/
    │   ├── viz/
    │   ├── cli.py
    │   └── runner.py
    │
    ├── tests/
    │
    ├── pyproject.toml
    └── README.md

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

Verbose batch execution:

```bash
evac-sim run --config study.yaml --environment corridor -v
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

These notebooks are located in:

```text
Notebooks/
```

They can be useful for:
- Inspecting simulation trajectories
- Visualizing risk evolution over time
- Generating interactive plots and animations
- Exploring experimental results

To launch Jupyter from the project root:
````bash
jupyter notebook
````

Then open one of the available notebooks, such as:
- Notebooks/main.ipynb – interactive simulation workflow
- Notebooks/experiments.ipynb – execution and analysis of experimental scenarios

> Note
> The recommended and reproducible way to run simulations is via the CLI (evac-sim).
> Notebooks are provided mainly for exploration, visualization, and analysis of results.

------------------------------------------------------------------------

## ⚙️ Configuration

Simulation cases are defined as YAML entries. A case usually specifies:

- `environment`: scenario/layout to simulate
- `sources`: origin nodes or spawning points
- `agents`: number of agents spawned at each source
- `targets`: destination nodes or exits
- `mode_type`: routing/behavior mode
- `master_seed`: seed for reproducibility
- `risk_iterations`: number of risk propagation iterations
- `risk_increase_chance`: probability used in risk progression
- `starting_risks`: initial risky locations
- `risk_overrides`: risk changes injected at specific frames
- `risk_threshold`: threshold that marks a risky condition for decisions
- `propagation_threshold`: threshold used by the propagation model
- `gamma`: routing or scoring parameter used in strategy selection
- `stairs_max_speed` / `normal_max_speed`: movement parameters
- `every_nth_frame_simulation`: simulation frame subsampling
- `every_nth_frame_animation`: animation frame subsampling
- `danger_visualization_frame`: frame chosen for danger visualization

Example:

```yaml
corridor_case_1:
  environment: "corridor"
  sources: ["16"]
  agents: [5]
  targets: ["1", "14"]
  mode_type: 0
  master_seed: 1001
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
