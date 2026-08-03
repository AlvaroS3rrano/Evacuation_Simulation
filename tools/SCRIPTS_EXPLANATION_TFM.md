# Explanation of the scripts used for the TFM experiments

This document describes the purpose of the scripts used to generate experimental configurations, run simulations, analyze results, and diagnose errors during the development of the TFM (Master's Thesis).

All commands are assumed to be run from the `main` branch and from the repository root:

```text
C:\GitHub\Evacuation_Simulation
```

> See `tools/COMANDOS_REALIZACION_TFM.md` for the exact commands run, in chronological order, to reproduce the TFM experiments.

---

## 1. Overview of the experimental workflow

The full workflow is structured in five phases:

```text
1. Definition of base scenarios
2. Generation of reproducible random configurations
3. Execution of simulations with the none, h1, h2, and h3 strategies
4. Automatic computation of time and congestion metrics
5. Generation of comparison reports per simulation and per scenario
```

The main scripts live in:

```text
tools/
```

and rely on helper modules located in:

```text
tools/random_experiments/
tools/congestion_analysis/
```

---

## 2. Main scripts

The main scripts that make up the workflow are:

```text
tools/generate_random_congestion_yaml.py
tools/run_all_congestion_heuristics.py
tools/compare_congestion_heuristics.py
tools/compare_congestion_by_scenario.py
tools/diagnose_h2_k.py
tools/profile_single_congestion_case.py
```

Each one has a specific responsibility, so that the experimental process stays reproducible, modular, and easy to debug.

---

## 3. `generate_random_congestion_yaml.py`

### Purpose

This script generates a YAML file with several experimental configurations for each scenario. It starts from a base configuration and creates new random variants, keeping reproducibility through a fixed seed.

The result is a configuration file that can later be run end to end with the four guidance strategies.

### Input

The script takes as input:

```text
configs/congestion_heuristics.yaml
configs/defaults.yaml
tools/random_experiments/scenario_space.py
```

The `scenario_space.py` file defines, for each scenario, the candidate nodes that can act as sources and exits.

### Output

It typically generates:

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

The YAML file contains the final configurations to be simulated. The `.metadata.json` file stores information about the seed, the generated scenarios, the required nodes, and the included cases.

### General behavior

For each scenario, the script selects:

```text
- source nodes
- exit nodes
- number of agents per source
- intermediate nodes that must remain transitable
```

When a candidate exit node is not selected as an exit in a particular configuration, it is kept as a waypoint so it can still be part of valid routes.

### Required nodes

The script allows fixing nodes that must always appear as sources or exits in the random cases.

Example:

```powershell
python .\tools\generate_random_congestion_yaml.py `
  --required-sources short_vs_wide:34 `
  --required-targets short_vs_wide:37
```

This is useful when you want to make sure certain zones of the scenario are always represented in the experimental configurations.

---

## 4. `run_all_congestion_heuristics.py`

### Purpose

This is the main execution script. It runs every simulation defined in a YAML with the strategies:

```text
none
h1
h2
h3
```

### Input

It takes a configuration YAML as input, typically:

```text
configs/random_efficient_high_congestion.yaml
```

### Output

It generates a results structure under:

```text
runs/congestion_heuristics_efficient_high/
```

Inside this folder, subfolders are created per heuristic and case:

```text
runs/congestion_heuristics_efficient_high/
├── none/
├── h1/
├── h2/
└── h3/
```

Each simulation generates its own artifacts, metrics, and logs.

### Console progress

During execution, it shows incremental progress:

```text
[1/60] RUN  case=... heuristic=...
[1/60] OK   case=... heuristic=...
```

This makes it possible to check in real time which simulation is running and whether any of them fail.

### Automatic reports

Once the simulations finish, the script can automatically generate:

```text
comparison_report.md
scenario_strategy_report.md
```

The first one compares strategies per simulation. The second one aggregates the results per scenario.

### Visual PDFs

By default, visual PDFs are not generated, to avoid excessive runtimes. They can be enabled with:

```powershell
--with-visual-pdfs
```

These PDFs allow visually comparing trajectories and congestion maps.

---

## 5. `compare_congestion_heuristics.py`

### Purpose

This script generates the comparison report per simulation, i.e., per individual case.

It is used to compare, for each specific configuration, the performance of:

```text
none
h1
h2
h3
```

### Input

It reads the results generated under:

```text
runs/congestion_heuristics_efficient_high/
```

and extracts the metrics files:

```text
artifacts/csv/comparison_metrics.csv
```

### Output

It generates:

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

Optionally, it also generates comparison PDFs under:

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

In addition, also optionally (enabled by default, each can be disabled separately), it generates:

```text
runs/congestion_heuristics_efficient_high/comparison/trajectory_time_evolution/
  {case_id}_trajectories_time_evolution.png

runs/congestion_heuristics_efficient_high/comparison/congestion_gifs/{case_id}/
  {case_id}_congestion.gif
  {case_id}_frame_{frame:06d}.png   (only if specific frames are requested; {case_id}_t{seconds}.png with --time-unit seconds)
```

- **Trajectory image colored by time bin** (`trajectory_time_evolution/`): one image per case with every agent's trajectory colored by the frame bin it occurred in (e.g. frames 0-500 one color, 500-1000 another, etc.). The bin width is controlled by `--trajectory-time-bin-size` (default 500 frames), independent of the `--density-frame-step` used for the density PDFs.
- **Congestion GIF** (`congestion_gifs/{case_id}/{case_id}_congestion.gif`): a per-case animation, one panel per heuristic, showing the evolution of per-agent Voronoi density (`pedpy.compute_individual_voronoi_polygons` + `plot_voronoi_cells`) over the course of the simulation. The color scale is fixed across the whole animation so congestion stays comparable between frames. Controlled via `--gif-max-frames`, `--gif-frame-step`, `--gif-fps`, `--voronoi-cutoff-radius`, and `--gif-cmap`.
- **Specific-frame snapshots** (`--congestion-highlight-frames <frame1> <frame2> ...`): in addition to the GIF, saves a standalone PNG for each requested frame (same visual style as the GIF), useful for including a specific instant in the write-up without embedding the whole GIF.
- **Display unit** (`--time-unit {frame,seconds}`, default `frame`): controls how time is *labeled* across the density PDFs, the trajectory time-evolution image, and the congestion GIFs/snapshots — titles, colorbars, highlight-frame filenames, and the per-panel `agents=N ...` annotation (`frames=700` in frame mode vs. `duration=209.7s` in seconds mode, using each panel's own terminal frame). This is purely a display setting — the values passed to `--density-frames`, `--trajectory-time-bin-size`, `--gif-frame-step`, and `--congestion-highlight-frames` are always raw frame numbers regardless of `--time-unit`. Converting to seconds requires the simulation's frame rate, read from the `fps` entry in the trajectory `.sqlite`'s `metadata` table; if it can't be read for a given case, that case's output falls back to frame labels with a console warning instead of failing.

These outputs can be disabled with `--skip-trajectory-time-evolution` and `--skip-congestion-gifs` if only the metrics report or the area-density PDF is needed.

> Requirement: these outputs need the per-agent trajectory `.sqlite` file (`artifacts/db/<env_name>_mode_<n>.sqlite`, written by JuPedSim), not just the `simulation.db` that holds the risk/density metrics. If that `.sqlite` is missing for a given case/heuristic, the corresponding panel is rendered empty with a "No trajectory data" note.

### Relationship with `tools/congestion_analysis`

This script does not directly implement all of the analysis logic. It uses the internal modules:

```text
tools/congestion_analysis/comparison.py
tools/congestion_analysis/report.py
tools/congestion_analysis/visualization.py
tools/congestion_analysis/congestion_gif.py
```

This keeps the execution interface separate from the analysis and visualization logic.

---

## 6. `compare_congestion_by_scenario.py`

### Purpose

This script generates an aggregated report per scenario. Instead of comparing each simulation individually, it groups every configuration belonging to the same scenario.

For example, it groups cases such as:

```text
base_short_vs_wide
random_short_vs_wide_002
random_short_vs_wide_003
random_short_vs_wide_004
random_short_vs_wide_005
```

under the scenario:

```text
short_vs_wide
```

### Main metrics

The report focuses on the following metrics:

```text
avg_evac_time
p90_evac_time
max_evac_time
avg_density_exposure
high_density_agent_ratio
```

### Computed statistics

For each scenario, strategy, and metric it computes:

```text
mean
std
var
cv_pct
delta_pct_mean
delta_pct_std
win_rate_vs_baseline_pct
```

The main report prioritizes:

```text
mean
std
cv_pct
delta_pct_mean
win_rate_vs_baseline_pct
```

The variance is kept in the CSV files, but it is not considered the most interpretable metric for the main table in the write-up.

### Output

It generates:

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

and several auxiliary CSV files:

```text
scenario_case_metric_values.csv
scenario_case_metric_values_long.csv
scenario_metric_summary.csv
scenario_delta_vs_baseline.csv
scenario_case_composite_scores.csv
scenario_composite_summary.csv
```

---

## 6b. `build_thesis_result_tables.py` and `build_thesis_result_figures.py`

### Purpose

These two scripts do not run simulations or recompute metrics: they read the CSV files already generated by `compare_congestion_by_scenario.py` (`scenario_metric_summary.csv`, `scenario_delta_vs_baseline.csv`, `scenario_case_metric_values.csv`) and reorganize them into the tables and figures used directly in the thesis write-up (Chapter 7). If `compute_mean_speed_by_scenario.py` (section 6c below) has also been run, they additionally pick up its `scenario_mean_speed_*.csv` files to produce a speed table/figure; otherwise that table/figure is skipped with a console note, without affecting the rest.

They must be run **after** `compare_congestion_by_scenario.py`, for example:

```powershell
python tools/build_thesis_result_tables.py --run-root runs/congestion_heuristics_efficient_high
python tools/build_thesis_result_figures.py --run-root runs/congestion_heuristics_efficient_high
```

### `build_thesis_result_tables.py`

Generates five tables (CSV + one combined Markdown report):

```text
diff_time_density_vs_baseline  -> mean Tevac and D per strategy, and % change vs. the baseline
mean_results_by_scenario       -> mean of every metric per scenario (equivalent to tables 7.1-7.3)
best_strategy_by_scenario      -> heuristic with the best mean value per metric and scenario (table 7.4)
robustness_cv                  -> CV % of Tevac/D and % of configurations where each heuristic reduces density (table 7.5)
mean_speed_by_scenario          -> per-agent walking speed statistics (mean/median/std/min/p10/p90/max, in m/s)
                                   per strategy and scenario, with % change vs. the baseline for the mean and
                                   the minimum (the worst-case/congestion tail). Requires
                                   compute_mean_speed_by_scenario.py to have been run first; skipped otherwise.
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/
```

### `build_thesis_result_figures.py`

Generates five figures (vector PDF for `\includegraphics` + PNG preview):

```text
dispersion_outliers   -> one point per configuration (Tevac and D), mean ± standard deviation, and the
                          most extreme configuration in each group labeled by its suffix (useful for
                          identifying outlier cases, e.g. a single configuration driving up the CV)
mean_comparison        -> grouped bars with the mean of Tevac and D per strategy and scenario, with
                           error bars (±1 standard deviation)
delta_vs_baseline      -> percentage change of Tevac and D for h1/h2/h3 relative to the baseline strategy
tradeoff_scatter        -> Tevac vs. D per configuration, with each strategy's mean highlighted,
                           illustrating the speed/congestion trade-off
mean_speed_comparison   -> grouped bars of mean per-agent walking speed per strategy and scenario, with
                           ±1 std error bars plus a thin whisker showing the mean of each run's own
                           min-max speed range. Same optional dependency on
                           compute_mean_speed_by_scenario.py as the table above.
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/
```

The color palette is fixed across all five charts (`none` in neutral gray, since it's the reference; `h1`, `h2`, `h3` in blue, teal, and orange respectively), so that the figures stay consistent with each other when included in the thesis.

All figures produced by `build_thesis_result_figures.py` are labeled in English (titles, axis labels, legend). The tables produced by `build_thesis_result_tables.py` deliberately stay in Spanish (`Tevac`, `D`, `Vmed`, ... matching the thesis body text) — only the figures were asked to be translated.

---

## 6c. `compute_mean_speed_by_scenario.py`

### Purpose

Optional additional step that computes real per-agent walking speed statistics — mean, median, std, min, p10, p90, max, all in m/s — directly from the raw JuPedSim trajectory `.sqlite` files (`artifacts/db/<env>_mode_<n>.sqlite`, the same files used by `congestion_analysis/congestion_gif.py`), aggregated by scenario.

It is a deliberately separate step, outside `build_thesis_result_tables.py` / `build_thesis_result_figures.py`: those two only ever read small, already-aggregated CSVs and never re-read the simulation databases, and walking speed cannot be derived from those aggregated files. In particular, `avg_path_cost` is a time-averaged *remaining* route distance, not a total distance travelled, so `avg_path_cost / avg_evac_time` would not be a physically meaningful speed — the real per-agent trajectories have to be read instead.

Must run **after** `compare_congestion_by_scenario.py` and **before** `build_thesis_result_tables.py` / `build_thesis_result_figures.py`, for example:

```powershell
python tools/compute_mean_speed_by_scenario.py --run-root runs/congestion_heuristics_efficient_high
```

On the full `congestion_heuristics_efficient_high` run (60 case/heuristic combinations) this takes under a minute.

### Output

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_case_values.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_summary.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_delta_vs_baseline.csv
```

These feed the `mean_speed_by_scenario` table and `mean_speed_comparison` figure described in section 6b above. If this script hasn't been run yet, both are skipped gracefully (with a console message pointing here) rather than failing the rest of the pipeline.

---

## 7. `diagnose_h2_k.py`

### Purpose

This script is used to study the effect of the `k` parameter on the `h2` strategy.

The `h2` strategy uses a reservation/anticipation horizon. It is therefore necessary to justify that the selected value, e.g. `k=6`, produces reasonable behavior.

### Behavior

It runs the same configuration multiple times with different values of `k`:

```text
k = 2, 3, 4, 5, 6, 8, 10
```

and compares the results obtained.

### Output

It generates:

```text
runs/h2_k_diagnostic/h2_k_diagnostic_summary.csv
runs/h2_k_diagnostic/h2_k_diagnostic_report.md
```

### Use in the TFM

This script is used to justify the choice of `k=6` by showing how the main metrics vary as the decision horizon is changed.

---

## 8. `profile_single_congestion_case.py`

### Purpose

This script allows running and diagnosing a single simulation. It replaces ad hoc scripts such as `profile_h3_short_vs_wide.py`, offering a generic tool instead.

### Usage

It allows checking:

```text
- whether the YAML loads correctly
- whether the case exists
- which environment is used
- which sources, targets, and agents it has
- whether the nodes exist in the graph
- whether the simulation fails
- at which point the error occurs
```

### Output

It stores the results under:

```text
runs/profile_single/<heuristic>/<case>/
```

If it fails, it generates:

```text
error_traceback.txt
```

If profiling is enabled, it generates:

```text
profile_cumtime.txt
```

### Use in debugging

It is the recommended script for checking a single case before launching every simulation.

---

## 9. Helper modules in `tools/random_experiments`

### `case_generation.py`

Contains the logic for building the random cases. Among other tasks it:

```text
- selects sources
- selects targets
- assigns agents
- adjusts agent counts if they don't physically fit in the initial area
- keeps unselected targets as waypoints
- writes the final YAML
```

This module is not normally run directly. It is used by `generate_random_congestion_yaml.py`.

### `scenario_space.py`

Defines the scenario space. For each scenario it specifies:

```text
- base template
- environment used
- possible source nodes
- possible exit nodes
```

It should be considered the primary source for knowing which nodes can be selected during random generation.

---

## 10. Helper modules in `tools/congestion_analysis`

The `tools/congestion_analysis` folder contains the internal logic for analyzing results.

### `comparison.py`

Locates and processes the metrics files generated by each simulation. It is used to build comparison tables between strategies.

### `report.py`

Generates the per-simulation Markdown report:

```text
comparison_report.md
```

This report compares each case against the baseline strategy `none`.

### `visualization.py`

Generates visual comparison PDFs (trajectories and area-density maps), as well as the trajectory image colored by time bin (`generate_trajectory_time_evolution_images`). It also contains `choose_trajectory_db`, the function that locates each case's trajectory `.sqlite` file (looks for both `*.db` and `*.sqlite` under `artifacts/db/`), used by both the PDFs and the congestion-GIF module.

### `congestion_gif.py`

Generates the per-agent Voronoi-density congestion GIFs (`generate_congestion_gifs`), reusing `pedpy.compute_individual_voronoi_polygons` and `pedpy.plot_voronoi_cells`. To keep the computation affordable on runs with thousands of frames and hundreds of agents, Voronoi density is only ever computed for the subset of frames that actually get rendered (never at the simulation's full resolution). It also generates, when requested, the standalone PNG snapshots for specific frames, reusing the same renderer as the GIF.

These modules should not be removed even though they are not run directly from the console, since they are used by `compare_congestion_heuristics.py`.

---

## 11. Relevant generated files

The experimental workflow generates several files that matter for reproducibility and analysis.

### Configurations

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

### Results

```text
runs/congestion_heuristics_efficient_high/
```

### Run manifest

```text
runs/congestion_heuristics_efficient_high/run_manifest.json
```

### Per-simulation report

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

### Per-scenario report

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

### Visual PDFs

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

### Trajectory image colored by time bin

```text
runs/congestion_heuristics_efficient_high/comparison/trajectory_time_evolution/
```

### Congestion GIFs and specific-frame snapshots

```text
runs/congestion_heuristics_efficient_high/comparison/congestion_gifs/
```

### Mean-speed statistics

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_summary.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_delta_vs_baseline.csv
```

---

## 12. Summary of responsibilities

| Script or module | Responsibility |
|---|---|
| `generate_random_congestion_yaml.py` | Generate a reproducible random YAML |
| `run_all_congestion_heuristics.py` | Run every simulation |
| `compare_congestion_heuristics.py` | Compare strategies per simulation |
| `compare_congestion_by_scenario.py` | Compare strategies per scenario |
| `build_thesis_result_tables.py` | Thesis tables (Tevac/D differences, synthesis, CV, mean speed) |
| `build_thesis_result_figures.py` | Thesis figures (dispersion, means, deltas, trade-off, mean speed) |
| `compute_mean_speed_by_scenario.py` | Per-agent walking speed statistics from raw trajectories |
| `diagnose_h2_k.py` | Diagnose the `k` value in `h2` |
| `profile_single_congestion_case.py` | Debug and profile a specific simulation |
| `tools/random_experiments/case_generation.py` | Internal case-generation logic |
| `tools/random_experiments/scenario_space.py` | Scenario and candidate-node definitions |
| `tools/congestion_analysis/comparison.py` | Internal metrics processing |
| `tools/congestion_analysis/report.py` | Per-simulation report generation |
| `tools/congestion_analysis/visualization.py` | Visual PDF generation and trajectory time-bin image |
| `tools/congestion_analysis/congestion_gif.py` | Congestion GIF (Voronoi) and specific-frame snapshot generation |

---

## 13. Core design idea

The goal of this structure is for the TFM to be reproducible. Starting from a fixed seed and an automatically generated YAML, the same scenarios can be rebuilt, the same strategies run, and the same comparison reports obtained.

The workflow clearly separates:

```text
configuration generation
simulation execution
per-case analysis
per-scenario analysis
diagnosis and debugging
```

This makes both experimentation and the methodological justification in the TFM write-up easier.
