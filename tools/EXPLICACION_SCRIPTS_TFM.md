# Explicación de los scripts utilizados en los experimentos del TFM

Este documento describe la función de los scripts empleados para generar configuraciones experimentales, ejecutar simulaciones, analizar resultados y diagnosticar errores durante el desarrollo del TFM.

Se asume que todos los comandos se ejecutan desde la rama `main` y desde la raíz del repositorio:

```text
C:\GitHub\Evacuation_Simulation
```

> English version: `tools/SCRIPTS_EXPLANATION_TFM.md`. Keep both files in sync when the scripts change.

---

## 1. Visión general del flujo experimental

El flujo completo de trabajo se estructura en cinco fases:

```text
1. Definición de escenarios base
2. Generación de configuraciones random reproducibles
3. Ejecución de simulaciones con las estrategias none, h1, h2 y h3
4. Cálculo automático de métricas de tiempo y congestión
5. Generación de informes comparativos por simulación y por escenario
```

Los scripts principales se encuentran en la carpeta:

```text
tools/
```

y se apoyan en módulos auxiliares situados en:

```text
tools/random_experiments/
tools/congestion_analysis/
```

---

## 2. Scripts principales

Los scripts principales que forman el flujo de trabajo son:

```text
tools/generate_random_congestion_yaml.py
tools/run_all_congestion_heuristics.py
tools/compare_congestion_heuristics.py
tools/compare_congestion_by_scenario.py
tools/diagnose_h2_k.py
tools/profile_single_congestion_case.py
```

Cada uno de ellos tiene una responsabilidad concreta, de forma que el proceso experimental sea reproducible, modular y fácil de depurar.

---

## 3. `generate_random_congestion_yaml.py`

### Objetivo

Este script genera un archivo YAML con distintas configuraciones experimentales para cada escenario. Parte de una configuración base y crea nuevas variantes aleatorias, manteniendo la reproducibilidad mediante una semilla fija.

El resultado es un archivo de configuración que posteriormente puede ejecutarse de forma completa con las cuatro estrategias de guiado.

### Entrada

El script toma como entrada:

```text
configs/congestion_heuristics.yaml
configs/defaults.yaml
tools/random_experiments/scenario_space.py
```

El archivo `scenario_space.py` define, para cada escenario, los nodos candidatos que pueden actuar como orígenes y salidas.

### Salida

Genera normalmente:

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

El archivo YAML contiene las configuraciones finales que se van a simular. El archivo `.metadata.json` guarda información sobre la semilla, los escenarios generados, los nodos obligatorios y los casos incluidos.

### Funcionamiento general

Para cada escenario se seleccionan:

```text
- nodos de origen
- nodos de salida
- número de agentes por origen
- nodos intermedios que deben permanecer transitables
```

Cuando un nodo candidato a salida no es seleccionado como salida en una configuración concreta, se mantiene como waypoint para que pueda seguir formando parte de rutas válidas.

### Nodos obligatorios

El script permite fijar nodos que deben aparecer siempre como orígenes o salidas en los casos random.

Ejemplo:

```powershell
python .\tools\generate_random_congestion_yaml.py `
  --required-sources short_vs_wide:34 `
  --required-targets short_vs_wide:37
```

Esto resulta útil cuando se quiere asegurar que determinadas zonas del escenario estén siempre representadas en las configuraciones experimentales.

---

## 4. `run_all_congestion_heuristics.py`

### Objetivo

Este es el script principal de ejecución. Ejecuta todas las simulaciones definidas en un YAML con las estrategias:

```text
none
h1
h2
h3
```

### Entrada

Recibe como entrada un YAML de configuración, normalmente:

```text
configs/random_efficient_high_congestion.yaml
```

### Salida

Genera una estructura de resultados en:

```text
runs/congestion_heuristics_efficient_high/
```

Dentro de esta carpeta se crean subcarpetas por heurística y caso:

```text
runs/congestion_heuristics_efficient_high/
├── none/
├── h1/
├── h2/
└── h3/
```

Cada simulación genera sus propios artefactos, métricas y logs.

### Progreso en consola

Durante la ejecución muestra el avance de forma incremental:

```text
[1/60] RUN  case=... heuristic=...
[1/60] OK   case=... heuristic=...
```

Esto permite comprobar en tiempo real qué simulación se está ejecutando y si alguna falla.

### Informes automáticos

Al finalizar las simulaciones, el script puede generar automáticamente:

```text
comparison_report.md
scenario_strategy_report.md
```

El primero compara estrategias por simulación. El segundo agrega los resultados por escenario.

### PDFs visuales

Por defecto, los PDFs visuales no se generan para evitar tiempos de ejecución excesivos. Pueden activarse con:

```powershell
--with-visual-pdfs
```

Estos PDFs permiten comparar visualmente trayectorias y mapas de congestión.

---

## 5. `compare_congestion_heuristics.py`

### Objetivo

Este script genera el informe comparativo por simulación o caso individual.

Sirve para comparar, para cada configuración concreta, el rendimiento de:

```text
none
h1
h2
h3
```

### Entrada

Lee los resultados generados en:

```text
runs/congestion_heuristics_efficient_high/
```

y extrae los archivos de métricas:

```text
artifacts/csv/comparison_metrics.csv
```

### Salida

Genera:

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

Opcionalmente también genera PDFs comparativos en:

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

Además, y también de forma opcional (activadas por defecto, se pueden desactivar por separado), genera:

```text
runs/congestion_heuristics_efficient_high/comparison/trajectory_time_evolution/
  {case_id}_trajectories_time_evolution.png

runs/congestion_heuristics_efficient_high/comparison/congestion_gifs/{case_id}/
  {case_id}_congestion.gif
  {case_id}_frame_{frame:06d}.png   (solo si se piden frames concretos)
```

- **Imagen de trayectorias coloreada por tramo temporal** (`trajectory_time_evolution/`): una imagen por caso con la trayectoria de cada agente coloreada según el tramo de frames en el que ocurrió (p. ej. frames 0-500 de un color, 500-1000 de otro, etc.). El tamaño del tramo se controla con `--trajectory-time-bin-size` (por defecto 500 frames), independiente del `--density-frame-step` usado en los PDFs de densidad.
- **GIF de congestión** (`congestion_gifs/{case_id}/{case_id}_congestion.gif`): animación por caso, con un panel por heurística, que muestra la evolución de la densidad de Voronoi por agente (`pedpy.compute_individual_voronoi_polygons` + `plot_voronoi_cells`) a lo largo de la simulación. La escala de color es fija en toda la animación para que la congestión sea comparable entre frames. Se controla con `--gif-max-frames`, `--gif-frame-step`, `--gif-fps`, `--voronoi-cutoff-radius` y `--gif-cmap`.
- **Snapshots de frames concretos** (`--congestion-highlight-frames <frame1> <frame2> ...`): además del GIF, guarda una imagen PNG independiente por cada frame solicitado (con el mismo estilo que el GIF), útil para incluir un instante concreto en la memoria sin depurar el GIF completo.

Estas tres salidas nuevas pueden desactivarse con `--skip-trajectory-time-evolution` y `--skip-congestion-gifs` si solo interesa el informe de métricas o el PDF de densidad por área.

> Requisito: estas salidas necesitan el archivo `.sqlite` con las trayectorias por agente (`artifacts/db/<entorno>_mode_<n>.sqlite`, generado por JuPedSim), no solo el `simulation.db` con las métricas de riesgo/densidad. Si ese `.sqlite` no existe para algún caso/heurística, el panel correspondiente se muestra vacío con el aviso "No trajectory data".

### Relación con `tools/congestion_analysis`

Este script no implementa directamente toda la lógica de análisis. Utiliza los módulos internos:

```text
tools/congestion_analysis/comparison.py
tools/congestion_analysis/report.py
tools/congestion_analysis/visualization.py
tools/congestion_analysis/congestion_gif.py
```

Esto permite separar la interfaz de ejecución de la lógica de análisis y visualización.

---

## 6. `compare_congestion_by_scenario.py`

### Objetivo

Este script genera un informe agregado por escenario. En lugar de comparar cada simulación por separado, agrupa todas las configuraciones pertenecientes al mismo escenario.

Por ejemplo, agrupa casos como:

```text
base_short_vs_wide
random_short_vs_wide_002
random_short_vs_wide_003
random_short_vs_wide_004
random_short_vs_wide_005
```

bajo el escenario:

```text
short_vs_wide
```

### Métricas principales

El informe se centra en las siguientes métricas:

```text
avg_evac_time
p90_evac_time
max_evac_time
avg_density_exposure
high_density_agent_ratio
```

### Estadísticos calculados

Para cada escenario, estrategia y métrica calcula:

```text
mean
std
var
cv_pct
delta_pct_mean
delta_pct_std
win_rate_vs_baseline_pct
```

En el informe principal se priorizan:

```text
mean
std
cv_pct
delta_pct_mean
win_rate_vs_baseline_pct
```

La varianza se conserva en los CSV, pero no se considera la métrica más interpretativa para la tabla principal del artículo.

### Salida

Genera:

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

y varios CSV auxiliares:

```text
scenario_case_metric_values.csv
scenario_case_metric_values_long.csv
scenario_metric_summary.csv
scenario_delta_vs_baseline.csv
scenario_case_composite_scores.csv
scenario_composite_summary.csv
```

---

## 6b. `build_thesis_result_tables.py` y `build_thesis_result_figures.py`

### Objetivo

Estos dos scripts no ejecutan simulaciones ni recalculan métricas: leen los CSV que ya genera `compare_congestion_by_scenario.py` (`scenario_metric_summary.csv`, `scenario_delta_vs_baseline.csv`, `scenario_case_metric_values.csv`) y los reorganizan en las tablas y figuras que se usan directamente en la memoria (Capítulo 7). Si además se ha ejecutado `compute_mean_speed_by_scenario.py` (sección 6c más abajo), también recogen sus CSV `scenario_mean_speed_*.csv` para generar una tabla/figura de velocidad; si no, esa tabla/figura se omite con un aviso por consola, sin afectar al resto.

Deben ejecutarse **después** de `compare_congestion_by_scenario.py`, por ejemplo:

```powershell
python tools/build_thesis_result_tables.py --run-root runs/congestion_heuristics_efficient_high
python tools/build_thesis_result_figures.py --run-root runs/congestion_heuristics_efficient_high
```

### `build_thesis_result_tables.py`

Genera cinco tablas (CSV + un informe Markdown combinado):

```text
diff_time_density_vs_baseline  -> Tevac y D medios por estrategia, y variación % vs. la base
mean_results_by_scenario       -> media de todas las métricas por escenario (equivalente a las tablas 7.1-7.3)
best_strategy_by_scenario      -> heurística con mejor valor medio por métrica y escenario (tabla 7.4)
robustness_cv                  -> CV % de Tevac/D y % de configuraciones en que cada heurística reduce la densidad (tabla 7.5)
mean_speed_by_scenario          -> estadísticas de velocidad por agente (media/mediana/std/mín/p10/p90/máx,
                                   en m/s) por estrategia y escenario, con variación % vs. la base para la
                                   media y el mínimo (la cola de peor congestión). Requiere haber ejecutado
                                   antes `compute_mean_speed_by_scenario.py`; si no, se omite.
```

Salida:

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/
```

### `build_thesis_result_figures.py`

Genera cinco figuras (PDF vectorial para `\includegraphics` + PNG de vista previa):

```text
dispersion_outliers   -> un punto por configuración (Tevac y D), media ± desviación típica, y la
                          configuración más extrema de cada grupo etiquetada por su sufijo (útil para
                          identificar casos atípicos, p. ej. una única configuración disparando el CV)
mean_comparison        -> barras agrupadas con la media de Tevac y D por estrategia y escenario, con
                           barras de error (±1 desviación típica)
delta_vs_baseline      -> variación porcentual de Tevac y D de h1/h2/h3 respecto a la estrategia base
tradeoff_scatter        -> Tevac vs. D por configuración, con la media de cada estrategia destacada,
                           para ilustrar el compromiso rapidez/congestión
mean_speed_comparison   -> barras agrupadas con la velocidad media por agente por estrategia y escenario,
                           con barras de error (±1 desviación típica) y una línea fina que muestra la media
                           del rango mín-máx propio de cada simulación. Misma dependencia opcional de
                           `compute_mean_speed_by_scenario.py` que la tabla anterior.
```

Salida:

```text
runs/congestion_heuristics_efficient_high/comparison/thesis_tables/figures/
```

La paleta de color es fija en los cinco gráficos (`none` en gris neutro por ser la referencia; `h1`, `h2`, `h3` en azul, verde-azulado y naranja respectivamente), para que las figuras sean consistentes entre sí al incluirlas en la memoria.

Todas las figuras generadas por `build_thesis_result_figures.py` están rotuladas en inglés (títulos, ejes, leyenda). Las tablas generadas por `build_thesis_result_tables.py` se mantienen deliberadamente en español (`Tevac`, `D`, `Vmed`, ... acorde al texto de la memoria) — solo se pidió traducir las figuras.

---

## 6c. `compute_mean_speed_by_scenario.py`

### Objetivo

Paso adicional y opcional que calcula estadísticas reales de velocidad por agente —media, mediana, desviación típica, mínimo, p10, p90 y máximo, todo en m/s— directamente a partir de los archivos `.sqlite` de trayectorias crudas de JuPedSim (`artifacts/db/<entorno>_mode_<n>.sqlite`, los mismos que usa `congestion_analysis/congestion_gif.py`), agregadas por escenario.

Es un paso deliberadamente separado de `build_thesis_result_tables.py` / `build_thesis_result_figures.py`: esos dos scripts solo leen CSV pequeños ya agregados y nunca releen las bases de datos de la simulación, y la velocidad no se puede derivar de esos CSV agregados. En concreto, `avg_path_cost` es una media temporal de la distancia RESTANTE de la ruta, no la distancia total recorrida, por lo que `avg_path_cost / avg_evac_time` no sería una velocidad físicamente correcta — hay que leer las trayectorias reales por agente.

Debe ejecutarse **después** de `compare_congestion_by_scenario.py` y **antes** de `build_thesis_result_tables.py` / `build_thesis_result_figures.py`, por ejemplo:

```powershell
python tools/compute_mean_speed_by_scenario.py --run-root runs/congestion_heuristics_efficient_high
```

Sobre el run completo `congestion_heuristics_efficient_high` (60 combinaciones caso/heurística) tarda menos de un minuto.

### Salida

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_case_values.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_summary.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_delta_vs_baseline.csv
```

Estos CSV alimentan la tabla `mean_speed_by_scenario` y la figura `mean_speed_comparison` descritas en la sección 6b anterior. Si este script no se ha ejecutado todavía, ambas se omiten de forma controlada (con un aviso por consola que señala este script) sin hacer fallar el resto del pipeline.

---

## 7. `diagnose_h2_k.py`

### Objetivo

Este script sirve para estudiar el efecto del parámetro `k` en la estrategia `h2`.

La estrategia `h2` utiliza un horizonte de reserva o anticipación. Por ello, es necesario justificar que el valor seleccionado, por ejemplo `k=6`, produce un comportamiento razonable.

### Funcionamiento

Ejecuta la misma configuración varias veces con diferentes valores de `k`:

```text
k = 2, 3, 4, 5, 6, 8, 10
```

y compara los resultados obtenidos.

### Salida

Genera:

```text
runs/h2_k_diagnostic/h2_k_diagnostic_summary.csv
runs/h2_k_diagnostic/h2_k_diagnostic_report.md
```

### Uso en el TFM

Este script permite justificar la elección de `k=6` mostrando cómo varían las métricas principales al modificar el horizonte de decisión.

---

## 8. `profile_single_congestion_case.py`

### Objetivo

Este script permite ejecutar y diagnosticar una única simulación. Sustituye a scripts específicos como `profile_h3_short_vs_wide.py`, ofreciendo una herramienta genérica.

### Uso

Permite comprobar:

```text
- si el YAML carga correctamente
- si el caso existe
- qué entorno se usa
- qué sources, targets y agentes tiene
- si los nodos existen en el grafo
- si la simulación falla
- en qué punto se produce el error
```

### Salida

Guarda los resultados en:

```text
runs/profile_single/<heuristic>/<case>/
```

Si falla, genera:

```text
error_traceback.txt
```

Si se activa el perfilado, genera:

```text
profile_cumtime.txt
```

### Uso en depuración

Es el script recomendado para comprobar un caso antes de lanzar todas las simulaciones.

---

## 9. Módulos auxiliares en `tools/random_experiments`

### `case_generation.py`

Contiene la lógica para construir los casos random. Entre otras tareas:

```text
- selecciona sources
- selecciona targets
- asigna agentes
- ajusta agentes si no caben físicamente en el área inicial
- conserva como waypoints los targets no seleccionados
- escribe el YAML final
```

Este módulo no se ejecuta normalmente de forma directa. Lo utiliza `generate_random_congestion_yaml.py`.

### `scenario_space.py`

Define el espacio de escenarios. Para cada escenario indica:

```text
- plantilla base
- entorno utilizado
- posibles nodos de origen
- posibles nodos de salida
```

Debe considerarse la fuente principal para saber qué nodos pueden ser seleccionados en la generación random.

---

## 10. Módulos auxiliares en `tools/congestion_analysis`

La carpeta `tools/congestion_analysis` contiene la lógica interna para analizar resultados.

### `comparison.py`

Localiza y procesa los archivos de métricas generados por cada simulación. Permite construir tablas comparativas entre estrategias.

### `report.py`

Genera el informe Markdown por simulación:

```text
comparison_report.md
```

Este informe compara cada caso con la estrategia base `none`.

### `visualization.py`

Genera PDFs visuales de comparación (trayectorias y mapas de densidad por área), así como la imagen de trayectorias coloreada por tramo temporal (`generate_trajectory_time_evolution_images`). También contiene `choose_trajectory_db`, la función que localiza el `.sqlite` de trayectorias de cada caso (busca tanto `*.db` como `*.sqlite` bajo `artifacts/db/`), usada tanto por los PDFs como por el módulo de GIFs de congestión.

### `congestion_gif.py`

Genera los GIFs de congestión basados en densidad de Voronoi por agente (`generate_congestion_gifs`), reutilizando `pedpy.compute_individual_voronoi_polygons` y `pedpy.plot_voronoi_cells`. Para mantener el cómputo asumible en runs con miles de frames y cientos de agentes, la densidad de Voronoi solo se calcula sobre el subconjunto de frames que finalmente se muestran (nunca sobre la resolución completa de la simulación). También genera, si se piden, los snapshots PNG de frames concretos, reutilizando el mismo renderizador que el GIF.

Estos módulos no deberían eliminarse aunque no se ejecuten directamente desde consola, ya que son utilizados por `compare_congestion_heuristics.py`.

---

## 11. Archivos generados relevantes

Durante el flujo experimental se generan archivos importantes para reproducibilidad y análisis.

### Configuraciones

```text
configs/random_efficient_high_congestion.yaml
configs/random_efficient_high_congestion.metadata.json
```

### Resultados

```text
runs/congestion_heuristics_efficient_high/
```

### Manifiesto de ejecución

```text
runs/congestion_heuristics_efficient_high/run_manifest.json
```

### Informe por simulación

```text
runs/congestion_heuristics_efficient_high/comparison/comparison_report.md
```

### Informe por escenario

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_strategy_report.md
```

### PDFs visuales

```text
runs/congestion_heuristics_efficient_high/comparison/visual_snapshots/
```

### Imagen de trayectorias por tramo temporal

```text
runs/congestion_heuristics_efficient_high/comparison/trajectory_time_evolution/
```

### GIFs de congestión y snapshots de frames concretos

```text
runs/congestion_heuristics_efficient_high/comparison/congestion_gifs/
```

### Estadísticas de velocidad media

```text
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_summary.csv
runs/congestion_heuristics_efficient_high/comparison/scenario_strategy/scenario_mean_speed_delta_vs_baseline.csv
```

---

## 12. Resumen de responsabilidades

| Script o módulo | Responsabilidad |
|---|---|
| `generate_random_congestion_yaml.py` | Generar YAML random reproducible |
| `run_all_congestion_heuristics.py` | Ejecutar todas las simulaciones |
| `compare_congestion_heuristics.py` | Comparar estrategias por simulación |
| `compare_congestion_by_scenario.py` | Comparar estrategias por escenario |
| `build_thesis_result_tables.py` | Tablas de la memoria (diferencias Tevac/D, síntesis, CV, velocidad media) |
| `build_thesis_result_figures.py` | Figuras de la memoria (dispersión, medias, deltas, trade-off, velocidad media) |
| `compute_mean_speed_by_scenario.py` | Estadísticas de velocidad por agente a partir de trayectorias crudas |
| `diagnose_h2_k.py` | Diagnosticar el valor de `k` en `h2` |
| `profile_single_congestion_case.py` | Depurar y perfilar una simulación concreta |
| `tools/random_experiments/case_generation.py` | Lógica interna de generación de casos |
| `tools/random_experiments/scenario_space.py` | Definición de escenarios y nodos candidatos |
| `tools/congestion_analysis/comparison.py` | Procesamiento interno de métricas |
| `tools/congestion_analysis/report.py` | Generación del informe por simulación |
| `tools/congestion_analysis/visualization.py` | Generación de PDFs visuales e imagen de trayectorias por tramo temporal |
| `tools/congestion_analysis/congestion_gif.py` | Generación de GIFs de congestión (Voronoi) y snapshots de frames concretos |

---

## 13. Idea principal del diseño

El objetivo de esta estructura es que el TFM sea reproducible. A partir de una semilla fija y de un YAML generado automáticamente, se pueden reconstruir los mismos escenarios, ejecutar las mismas estrategias y obtener los mismos informes comparativos.

El flujo separa claramente:

```text
generación de configuraciones
ejecución de simulaciones
análisis por caso
análisis por escenario
diagnóstico y depuración
```

Esto facilita tanto la experimentación como la justificación metodológica en la memoria del TFM.
