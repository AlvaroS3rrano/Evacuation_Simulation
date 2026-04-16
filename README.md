# Evac-Sim - Evacuation Simulation Framework

Simulation framework for pedestrian evacuation scenarios based on
**JuPedSim**, designed to support research on evacuation dynamics,
risk propagation, and intelligent routing strategies.

The framework enables the simulation of complex evacuation scenarios,
analysis of agent behavior under different levels of environmental
awareness, and systematic comparison of routing strategies.

This project is developed in the context of academic research on
evacuation dynamics and intelligent environments.

------------------------------------------------------------------------

## 📌 Project Overview

The goal of this project is to simulate evacuation processes in complex
environments, analyzing different routing strategies and levels of
environmental awareness.

The framework allows:

-   Agent-based pedestrian simulation using **JuPedSim**
-   Definition of custom environments and walkable areas
-   Risk computation per agent and per frame
-   Visualization of trajectories and risk evolution
-   Storage and analysis of simulation results

A key aspect of the framework is the modeling of different levels of
agent environmental awareness, distinguishing between **high-awareness**
and **low-awareness** agents, as well as comparing multiple routing
strategies.

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
    │ └── experiments.ipynb
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
.venv\Scripts\activate

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
configs/study.yaml
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

Simulation cases are defined in YAML files under:

    configs/

Example:

``` yaml
corridor_case_1:
  environment: corridor
  sources: [A]
  targets: [B]
  agents: [50]
  risk_seed: 42
  risk_iterations: 3000
  gamma: 0.5
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

## 👤 Author

Álvaro Serrano\
Bachelor's Thesis / Research Project\
Evacuation simulation and intelligent environments
