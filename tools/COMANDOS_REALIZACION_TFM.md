# Commands used to run the TFM experiments

This document lists, in the order they were used, the main commands run to carry out the TFM experiments.

All commands assume the `main` branch and the repository root as the working directory:

```text
C:\GitHub\Evacuation_Simulation
```

> For what each script does and what it produces, see `tools/SCRIPTS_EXPLANATION_TFM.md`. This document only records the commands and their main output paths.

---

## 1. `k` parameter diagnostic for the `h2` strategy

First, a diagnostic run over the `k` parameter analyzed how the `h2` strategy behaves under different reservation horizons.

```powershell
python .\tools\diagnose_h2_k.py `
  --config random_efficient_high_congestion.yaml `
  --k-values 2 3 4 5 6 8 10
```

Output:

```text
runs/h2_k_diagnostic/h2_k_diagnostic_summary.csv
runs/h2_k_diagnostic/h2_k_diagnostic_report.md
```

---

## 2. Random congestion-scenario YAML generation

Next, the YAML file with the random experimental configurations used in the main simulations was generated.

```powershell
python .\tools\generate_random_congestion_yaml.py `
  --output-config random_efficient_high_congestion.yaml `
  --configs-per-scenario 5 `
  --master-seed 1234 `
  --required-targets two_exits:17
```

Output:

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

---

## 3. Running all simulations across the guidance strategies

Once the experimental YAML was generated, every simulation was run with the four guidance strategies:

```text
none
h1
h2
h3
```

using a reservation horizon of:

```text
k = 6
```

```powershell
python .\tools\run_all_congestion_heuristics.py `
  --config random_efficient_high_congestion.yaml `
  --heuristics none h1 h2 h3 `
  --horizon-k 6 `
  --runs-dir runs/congestion_heuristics_efficient_high
```

Output:

```text
runs/congestion_heuristics_efficient_high/
runs/congestion_heuristics_efficient_high/run_manifest.json
```

---

## 4. Derived metrics

After running the simulations, the derived evacuation, congestion, and route metrics were computed.

```powershell
python .\tools\build_derived_metrics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --simulation-config random_efficient_high_congestion.yaml
```

For each simulation, this generates files such as:

```text
artifacts/csv/evacuation_metrics.csv
artifacts/csv/density_metrics.csv
artifacts/csv/comparison_metrics.csv
```

---

## 5. Per-simulation heuristic comparison

With the derived metrics in place, the per-simulation comparison report was built.

```powershell
python .\tools\compare_congestion_heuristics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --baseline none `
  --heuristics none h1 h2 h3 `
  --simulation-config random_efficient_high_congestion.yaml `
  --skip-visual-pdfs
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

---

## 6. Aggregated per-scenario comparison

Finally, the aggregated per-scenario comparison report was generated.

```powershell
python .\tools\compare_congestion_by_scenario.py `
  --run-root .\runs\congestion_heuristics_efficient_high `
  --baseline none
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

---

## 7. Visual PDFs for the base cases

After running the simulations and building the derived metrics, the visual PDFs for each scenario's base case were generated.

Base cases considered:

```text
base_short_vs_wide
base_two_corridors
base_two_exits
```

```powershell
python .\tools\compare_congestion_heuristics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --baseline none `
  --heuristics none h1 h2 h3 `
  --cases base_short_vs_wide base_two_corridors base_two_exits `
  --simulation-config random_efficient_high_congestion.yaml `
  --density-frame-step 500 `
  --congestion-highlight-frames 1000 3000 `
  --time-unit seconds
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

These PDFs allow visually comparing, for each base case, the trajectories and density maps obtained with the different guidance strategies.

`--time-unit seconds` labels density frames, the trajectory time-evolution image, and the congestion GIF/snapshots in real time (`t=...s`) instead of raw frame numbers, converted using each case's simulation fps (see `tools/SCRIPTS_EXPLANATION_TFM.md` for details); it falls back to frame labels per case if fps can't be read. Highlight frames beyond a case's terminal frame (e.g. `3000` for the shorter `base_two_corridors`/`base_two_exits` runs) are skipped automatically.

---

## 8. Mean walking-speed statistics

Once the per-scenario report existed (step 6), per-agent walking-speed statistics were computed from the raw trajectory data.

```powershell
python .\tools\compute_mean_speed_by_scenario.py `
  --run-root .\runs\congestion_heuristics_efficient_high
```

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_case_values.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_summary.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_delta_vs_baseline.csv
```

---

## 9. Thesis result tables

With the per-scenario report (step 6) and the mean-speed statistics (step 8) available, the tables used in Chapter 7 of the thesis were built.

```powershell
python .\tools\build_thesis_result_tables.py `
  --run-root .\runs\congestion_heuristics_efficient_high
```

This command does not re-read the simulations: it reuses the CSVs already produced in steps 6 and 8.

Output:

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/diff_time_density_vs_baseline.csv
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/mean_results_by_scenario.csv
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/best_strategy_by_scenario.csv
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/robustness_cv.csv
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/mean_speed_by_scenario.csv
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/thesis_tables_report.md
```

---

## 10. Thesis result figures

Finally, the figures included in Chapter 7 were generated.

```powershell
python .\tools\build_thesis_result_figures.py `
  --run-root .\runs\congestion_heuristics_efficient_high
```

Like the previous script, this reuses the CSVs already produced in steps 6 and 8 and does not re-run any simulation.

Output (vector PDF for the thesis + PNG preview):

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/mean_comparison.{pdf,png}
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/delta_vs_baseline.{pdf,png}
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/tradeoff_scatter.{pdf,png}
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/dispersion_outliers.{pdf,png}
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/mean_speed_comparison.{pdf,png}
```

The PDF files were copied into the thesis project's `figures/` folder and are referenced from `07_analisis_resultados.tex` via `\includegraphics`.
