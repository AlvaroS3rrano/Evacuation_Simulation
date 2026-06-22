# Congestion Heuristic Scripts Usage Guide

This document explains the purpose of each script used in the congestion heuristic evaluation workflow, the recommended execution order, and example commands.

The general workflow is:

1. Run simulations.
2. Build derived metrics from the simulation databases.
3. Compare heuristics against each other and against `none`.
4. Review the generated reports.

---

## 1. `tools/run_all_congestion_heuristics.py`

### Purpose

This script automatically runs multiple scenarios with multiple congestion heuristics.

It is normally used to execute the main congestion experiments with:

- `none`
- `h1`
- `h2`
- `h3`

across all cases defined in the configuration file, for example:

- `congestion_parallel_corridors`
- `congestion_short_vs_wide`
- `congestion_two_exits`

It can also force a specific `mode_type` for all scenarios, such as an efficient pathfinding mode with high situational awareness.

### When to use it

Use this script when you want to generate a complete set of simulation results for heuristic comparison.

This is the main script for producing the outputs that will later be analyzed.

### Example command

```powershell
python tools\run_all_congestion_heuristics.py --config congestion_heuristics.yaml --mode-type 5 --heuristics none h1 h2 h3 --beta 1.0 --horizon-k 6 --runs-dir runs\congestion_heuristics_efficient_high
```

### Important parameters

```text
--config
```

YAML scenario configuration file located in `configs/`.

```text
--mode-type
```

Evacuation mode forced for all cases. For example, `5` can be used for efficient pathfinding with high awareness, if that mode exists in the project.

```text
--heuristics
```

List of heuristics to run.

```text
--beta
```

Weight parameter used by the congestion heuristics.

```text
--horizon-k
```

Horizon used by `h2`.

```text
--runs-dir
```

Directory where all results will be saved.

### Expected output

Each run generates a directory similar to:

```text
runs/congestion_heuristics_efficient_high/h3/congestion_short_vs_wide/
```

Inside that directory, the simulation artifacts are stored:

```text
artifacts/db/simulation.db
artifacts/csv/experiment_metrics.csv
```

---

## 2. `tools/diagnose_congestion_heuristics.py`

### Purpose

This script runs one or more heuristics on a specific scenario and produces a detailed diagnostic report.

It is used to detect potential issues during simulation, such as:

- stopped groups;
- groups that never resume;
- capacity blocking events;
- queue events;
- reroute backtracks;
- possible stuck groups;
- errors or tracebacks in logs.

Unlike `run_all_congestion_heuristics.py`, this script is mainly intended for debugging and validation.

### When to use it

Use this script after modifying the simulation or congestion logic, especially changes related to:

- capacity reservations;
- spatial queues;
- route selection;
- group movement logic;
- dynamic group splitting.

### Example command

```powershell
python tools\diagnose_congestion_heuristics.py --config congestion_heuristics.yaml --case congestion_two_exits --heuristics none h1 h2 h3 --beta 1.0 --out-root .\runs\diagnostics_congestion_two_exits -v --extra-arg=--horizon-k --extra-arg 6
```

### Important parameters

```text
--case
```

Specific scenario to diagnose.

```text
--heuristics
```

Heuristics to run for that scenario.

```text
--out-root
```

Directory where logs and diagnostic reports will be stored.

```text
-v
```

Enables verbose logging.

```text
--extra-arg
```

Allows passing additional arguments to the main simulation CLI.

### Expected output

The script generates:

```text
diagnostics_report.md
diagnostics_report.json
source_checks.json
*.log
```

The most useful file is usually:

```text
diagnostics_report.md
```

---

## 3. `tools/build_derived_metrics.py`

### Purpose

This script builds derived metrics from existing `simulation.db` databases.

It does not rerun simulations. Instead, it reads previously stored simulation data and computes additional metrics.

Its main purpose is to generate metrics that can be compared across `none`, `h1`, `h2`, and `h3`, especially density-based congestion metrics.

### Why this script is important

Congestion metrics based only on capacity events are not directly comparable with `none`, because `none` does not use capacity reservations.

For that reason, this script calculates congestion from the physical state of the agents, using data such as:

```text
frame
agent_id
area
```

From this information, it computes density by area and frame.

### Metrics generated

The script can generate files such as:

```text
density_metrics.csv
evacuation_metrics.csv
comparison_metrics.csv
```

Relevant metrics include:

```text
avg_density_exposure
p90_density_exposure
max_density_exposure
peak_area_density
high_density_agent_ratio
high_density_frame_ratio
congestion_density_score
avg_evac_time
p90_evac_time
max_evac_time
avg_path_cost
```

### When to use it

Run this script after generating simulation results with `tools/run_all_congestion_heuristics.py`.

### Example command

```powershell
python tools\build_derived_metrics.py --runs-dir runs\congestion_heuristics_efficient_high --simulation-config congestion_heuristics.yaml
```

### Important parameters

```text
--runs-dir
```

Directory containing the simulation runs.

```text
--metrics-config
```

YAML file containing the default metrics configuration.

If omitted, it uses:

```text
configs/metrics/default_metrics.yaml
```

```text
--simulation-config
```

Scenario YAML configuration file. It is used to read per-case metric overrides.

```text
--case
```

Processes only a specific case. This option can be passed multiple times.

Example:

```powershell
python tools\build_derived_metrics.py --runs-dir runs\congestion_heuristics_efficient_high --simulation-config congestion_heuristics.yaml --case congestion_two_exits
```

### Expected output

For each simulation run, the script generates:

```text
artifacts/csv/density_metrics.csv
artifacts/csv/evacuation_metrics.csv
artifacts/csv/comparison_metrics.csv
```

It also generates a global manifest:

```text
runs/congestion_heuristics_efficient_high/derived_metrics_manifest.json
```

---

## 4. `tools/compare_congestion_heuristics.py`

### Purpose

This script compares heuristic results against each other and against a baseline heuristic, usually `none`.

It first looks for:

```text
comparison_metrics.csv
```

If that file is not available, it can fall back to:

```text
experiment_metrics.csv
```

This allows the script to compare both the new derived metrics and the legacy experiment metrics.

### When to use it

Use this script after running `tools/build_derived_metrics.py`.

This script generates the final comparison report.

### Example: compare by evacuation time

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --metric avg_evac_time
```

### Example: compare by congestion score

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --metric congestion_density_score
```

### Example: compare by p90 density exposure

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --metric p90_density_exposure
```

### Important parameters

```text
--runs-dir
```

Base directory containing the simulation results.

```text
--metrics-config
```

YAML file defining the metrics used by default.

```text
--metric
```

Main metric used in the report.

Useful examples:

```text
avg_evac_time
p90_evac_time
max_evac_time
congestion_density_score
p90_density_exposure
peak_area_density
high_density_agent_ratio
avg_path_cost
```

```text
--baseline
```

Baseline heuristic used to compute differences. Default:

```text
none
```

```text
--heuristics
```

Selects which heuristics should be compared.

```text
--cases
```

Compares only selected scenarios.

### Expected output

The script generates a folder:

```text
runs/congestion_heuristics_efficient_high/comparison/
```

with files such as:

```text
comparison_report.md
summary_by_case_heuristic.csv
comparison_vs_baseline.csv
best_by_metric.csv
combined_metrics.csv
```

The main report is:

```text
comparison_report.md
```

---

## 5. `configs/metrics/default_metrics.yaml`

### Purpose

This file defines the default metrics configuration.

The idea is to have a project-wide default configuration and only override it in specific scenarios when necessary.

### Example expected content

```yaml
density:
  enabled: true
  source_table: agent_area_data
  sample_every_frames: 25
  high_density_threshold: 10
  congestion_score_metric: p90_density_exposure

evacuation:
  enabled: true
  source_table: experiment_metrics
  weight_column: n_records

route:
  enabled: true
  source_table: experiment_metrics
  avg_path_cost_column: avg_path_cost

risk:
  enabled: false

comparison:
  main_metrics:
    - avg_evac_time
    - median_evac_time
    - p90_evac_time
    - max_evac_time
    - avg_density_exposure
    - p90_density_exposure
    - peak_area_density
    - high_density_agent_ratio
    - congestion_density_score
    - avg_path_cost

  lower_is_better:
    avg_evac_time: true
    median_evac_time: true
    p90_evac_time: true
    max_evac_time: true
    avg_density_exposure: true
    p90_density_exposure: true
    peak_area_density: true
    high_density_agent_ratio: true
    congestion_density_score: true
    avg_path_cost: true
```

### How to override metrics for a specific case

In the scenario YAML file, for example `congestion_heuristics.yaml`, add:

```yaml
congestion_two_exits:
  metrics:
    density:
      sample_every_frames: 10
      high_density_threshold: 12
```

This changes the density configuration only for `congestion_two_exits`.

All other scenarios continue using the default metrics configuration.

---

## 6. Recommended execution order

The complete recommended workflow is:

### Step 1. Run all simulations

```powershell
python tools\run_all_congestion_heuristics.py --config congestion_heuristics.yaml --mode-type 5 --heuristics none h1 h2 h3 --beta 1.0 --horizon-k 6 --runs-dir runs\congestion_heuristics_efficient_high
```

### Step 2. Build derived metrics

```powershell
python tools\build_derived_metrics.py --runs-dir runs\congestion_heuristics_efficient_high --simulation-config congestion_heuristics.yaml
```

### Step 3. Compare by evacuation time

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --metric avg_evac_time
```

### Step 4. Compare by congestion

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --metric congestion_density_score
```

### Step 5. Review the report

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

---

## 7. Additional useful commands

### Run only one scenario

```powershell
python tools\run_all_congestion_heuristics.py --config congestion_heuristics.yaml --mode-type 5 --cases congestion_two_exits --heuristics none h1 h2 h3 --beta 1.0 --horizon-k 6 --runs-dir runs\congestion_heuristics_efficient_high
```

### Build metrics for only one scenario

```powershell
python tools\build_derived_metrics.py --runs-dir runs\congestion_heuristics_efficient_high --simulation-config congestion_heuristics.yaml --case congestion_two_exits
```

### Compare only one scenario

```powershell
python tools\compare_congestion_heuristics.py --runs-dir runs\congestion_heuristics_efficient_high --cases congestion_two_exits --metric congestion_density_score
```

### Diagnose a specific scenario

```powershell
python tools\diagnose_congestion_heuristics.py --config congestion_heuristics.yaml --case congestion_two_exits --heuristics none h1 h2 h3 --beta 1.0 --out-root .\runs\diagnostics_congestion_two_exits -v --extra-arg=--horizon-k --extra-arg 6
```

---

## 8. Basic interpretation of results

### If `none` is fastest

This does not necessarily mean that the heuristics are worse.

It may mean that `none` evacuates faster because it does not try to distribute flows or avoid dense areas.

For this reason, also check:

```text
avg_density_exposure
p90_density_exposure
peak_area_density
high_density_agent_ratio
congestion_density_score
```

### If a heuristic reduces density but increases evacuation time

This can still be a useful result.

The interpretation is:

```text
The heuristic sacrifices some evacuation time in exchange for lower crowd concentration and better flow distribution.
```

### If a heuristic improves both time and density

This is the strongest result.

For example:

```text
lower avg_evac_time
lower congestion_density_score
lower p90_density_exposure
```

This means the heuristic evacuates faster while also reducing congestion.

