# Comandos utilizados para la realización del TFM

Este documento recoge, en el orden en que se utilizaron, los comandos principales empleados para la realización de los experimentos del TFM.

Se asume que se trabaja desde la rama `main` y desde la raíz del repositorio:

```text
C:\GitHub\Evacuation_Simulation
```

---

## 1. Diagnóstico del parámetro `k` para la estrategia `h2`

En primer lugar, se ejecutó un diagnóstico del parámetro `k` para analizar el comportamiento de la estrategia `h2` con distintos horizontes de reserva.

```powershell
python .\tools\diagnose_h2_k.py `
  --config random_efficient_high_congestion.yaml `
  --k-values 2 3 4 5 6 8 10
```

Este comando genera los resultados del diagnóstico en:

```text
runs/h2_k_diagnostic/
```

Archivos principales generados:

```text
runs/h2_k_diagnostic/h2_k_diagnostic_summary.csv
runs/h2_k_diagnostic/h2_k_diagnostic_report.md
```

---

## 2. Generación del YAML random de escenarios de congestión

A continuación, se generó el archivo YAML con las configuraciones experimentales random utilizadas en las simulaciones principales.

```powershell
python .\tools\generate_random_congestion_yaml.py `
  --output-config random_efficient_high_congestion.yaml `
  --configs-per-scenario 5 `
  --master-seed 1234
```

Este comando genera:

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

---

## 3. Ejecución de todas las simulaciones con las estrategias de guiado

Una vez generado el YAML experimental, se ejecutaron todas las simulaciones con las cuatro estrategias de guiado:

```text
none
h1
h2
h3
```

El valor de horizonte utilizado fue:

```text
k = 6
```

Comando utilizado:

```powershell
python .\tools\run_all_congestion_heuristics.py `
  --config random_efficient_high_congestion.yaml `
  --heuristics none h1 h2 h3 `
  --horizon-k 6 `
  --runs-dir runs/congestion_heuristics_efficient_high
```

Los resultados se guardan en:

```text
runs/congestion_heuristics_efficient_high/
```

Archivo principal de seguimiento:

```text
runs/congestion_heuristics_efficient_high/run_manifest.json
```

---

## 4. Construcción de métricas derivadas

Tras ejecutar las simulaciones, se calcularon las métricas derivadas de evacuación, congestión y ruta.

```powershell
python .\tools\build_derived_metrics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --simulation-config random_efficient_high_congestion.yaml
```

Este comando genera, para cada simulación, archivos como:

```text
artifacts/csv/evacuation_metrics.csv
artifacts/csv/density_metrics.csv
artifacts/csv/comparison_metrics.csv
```

---

## 5. Comparación de heurísticas por simulación

Después de generar las métricas derivadas, se construyó el informe comparativo por simulación.

```powershell
python .\tools\compare_congestion_heuristics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --baseline none `
  --heuristics none h1 h2 h3 `
  --simulation-config random_efficient_high_congestion.yaml `
  --skip-visual-pdfs
```

Salida principal:

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

---

## 6. Comparación agregada por escenario

Finalmente, se generó el informe comparativo agregado por escenario.

```powershell
python .\tools\compare_congestion_by_scenario.py `
  --run-root .\runs\congestion_heuristics_efficient_high `
  --baseline none
```

Salida principal:

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

Este informe agrega las distintas configuraciones pertenecientes a cada escenario y calcula métricas como:

```text
mean
std
cv_pct
delta_pct_mean
win_rate_vs_baseline_pct
```

para las métricas principales de tiempo y congestión.

---

## 7. Generación de PDFs visuales para los casos base

De forma posterior a la ejecución de las simulaciones y a la construcción de las métricas derivadas, se generaron los PDFs visuales correspondientes a los casos base de cada escenario.

Los casos base considerados fueron:

```text
base_short_vs_wide
base_two_corridors
base_two_exits
```

Comando utilizado:

```powershell
python .\tools\compare_congestion_heuristics.py `
  --runs-dir .\runs\congestion_heuristics_efficient_high `
  --baseline none `
  --heuristics none h1 h2 h3 `
  --cases base_short_vs_wide base_two_corridors base_two_exits `
  --simulation-config random_efficient_high_congestion.yaml `
  --density-frame-step 500
```

Los PDFs se generan en:

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

Estos PDFs permiten comparar visualmente, para cada caso base, las trayectorias y los mapas de densidad obtenidos con las distintas estrategias de guiado.

