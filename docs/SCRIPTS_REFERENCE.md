# Evacuation Simulation — Referencia de Scripts y Pipeline

Documento de referencia completo para todos los scripts del proyecto `evac-sim`.
Explica el propósito de cada script, cómo invocarlo, todos los parámetros que acepta,
las salidas que produce y cómo encajan en el pipeline de simulación.

---

## Índice

1. [Arquitectura del proyecto](#1-arquitectura-del-proyecto)
2. [Pipeline completo](#2-pipeline-completo)
3. [Formato de configuración YAML](#3-formato-de-configuración-yaml)
4. [Scripts de ejecución principal](#4-scripts-de-ejecución-principal)
   - [evac-sim run / python -m evac_sim](#41-evac-sim-run--python--m-evac_sim)
5. [Scripts de inspección de entornos](#5-scripts-de-inspección-de-entornos)
   - [inspect_grid_layout](#51-inspect_grid_layout)
   - [inspect_walkable_area](#52-inspect_walkable_area)
   - [generate_layout](#53-generate_layout)
6. [Scripts de utilidad (nuevos)](#6-scripts-de-utilidad-nuevos)
   - [validate_scenario_config](#61-validate_scenario_config)
   - [run_scenario](#62-run_scenario)
7. [Herramientas de análisis (tools/)](#7-herramientas-de-análisis-tools)
   - [run_all_congestion_heuristics](#71-run_all_congestion_heuristics)
   - [generate_random_congestion_yaml](#72-generate_random_congestion_yaml)
   - [build_derived_metrics](#73-build_derived_metrics)
   - [compare_congestion_heuristics](#74-compare_congestion_heuristics)
   - [compare_congestion_by_scenario](#75-compare_congestion_by_scenario)
   - [diagnose_h2_k](#76-diagnose_h2_k)
   - [profile_single_congestion_case](#77-profile_single_congestion_case)
8. [Estructura de salidas](#8-estructura-de-salidas)
9. [Entornos disponibles](#9-entornos-disponibles)
10. [Diagnóstico: agentes atascados en management_building](#10-diagnóstico-agentes-atascados-en-management_building)

---

## 1. Arquitectura del proyecto

```
evac_sim/
├── cli.py                        # Punto de entrada: "evac-sim run"
├── runner.py                     # Lógica de ejecución única y en batch
├── orchestration/                # Setup de experimentos, modelos, configuración
├── simulation/                   # Bucle de simulación frame a frame
│   └── scripts/
│       └── run_scenario.py       # [NUEVO] Ejecución con salida JSON estructurada
├── routing/                      # Algoritmos de routing (none/h1/h2/h3)
├── risk/                         # Simulación y validación de riesgos
├── envs/                         # Entornos y layout
│   ├── environment_factory.py    # Registro de entornos
│   ├── environment_data/         # Geometría y grafos de cada entorno
│   ├── layout_creation.py        # Algoritmos greedy/quadtree/navmesh
│   ├── layout_io.py              # Serialización JSON de layouts
│   └── scripts/
│       ├── inspect_grid_layout.py       # Inspección visual + exportación
│       ├── inspect_walkable_area.py     # Visualización del área caminable
│       ├── generate_layout.py           # Generación de layouts
│       └── validate_scenario_config.py  # [NUEVO] Validación de configuraciones
├── db/                           # Persistencia SQLite
├── analysis/ y metrics/          # Métricas post-simulación
└── viz/                          # Visualizaciones (animaciones, plots)

tools/
├── run_all_congestion_heuristics.py
├── generate_random_congestion_yaml.py
├── build_derived_metrics.py
├── compare_congestion_heuristics.py
├── compare_congestion_by_scenario.py
├── diagnose_h2_k.py
└── profile_single_congestion_case.py

configs/
├── defaults.yaml                 # Valores por defecto para todos los casos
├── study.yaml                    # Casos del estudio principal
├── management_building.yaml      # Casos del edificio de gestión
├── congestion_heuristics.yaml    # Casos de congestión
└── metrics/default_metrics.yaml  # Configuración de métricas
```

---

## 2. Pipeline completo

```
                    ┌─────────────────────────────────────────────────┐
                    │              FASE 0 (opcional)                  │
                    │   generate_random_congestion_yaml.py            │
                    │   → genera configs/random_*.yaml automáticamente│
                    └──────────────────┬──────────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────────┐
                    │              FASE 1 (validación)                │
                    │   validate_scenario_config                      │
                    │   → configs/generated/<scenario>.validated.yaml │
                    └──────────────────┬──────────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────────┐
                    │              FASE 2 (simulación)                │
                    │   evac-sim run   ó   run_scenario               │
                    │   ó run_all_congestion_heuristics               │
                    └──────────────────┬──────────────────────────────┘
                                       │
               ┌───────────────────────┼───────────────────────┐
               ▼                       ▼                       ▼
   artifacts/db/simulation.db   trajectory*.sqlite      result.json
   artifacts/csv/*.csv          metadata.json           agents.csv
               │
               ▼
       ┌───────────────────────────────────────────────────────┐
       │              FASE 3 (métricas derivadas)              │
       │   build_derived_metrics.py                            │
       │   → comparison_metrics.csv, density_metrics.csv, ...  │
       └──────────────────┬────────────────────────────────────┘
                          │
       ┌──────────────────▼────────────────────────────────────┐
       │              FASE 4 (informes)                        │
       │   compare_congestion_heuristics.py                    │
       │   compare_congestion_by_scenario.py                   │
       │   → comparison_report.md, scenario_strategy_report.md │
       └───────────────────────────────────────────────────────┘
```

---

## 3. Formato de configuración YAML

Cada escenario en un archivo YAML tiene la siguiente estructura:

```yaml
nombre_del_caso:
  environment: "nombre_del_entorno"    # ver sección 9
  sources: ["id1", "id2"]             # nodos de origen (IDs de waypoints)
  agents: [N1, N2]                    # agentes por cada source (misma longitud)
  targets: ["id3", "id4"]             # nodos destino
  mode_type: 0                        # 0=Eficiente, 1=Centralidad, 2-5=mixtos
  master_seed: 233                    # semilla maestra de aleatoriedad
  risk:
    enabled: true
    risk_iterations: 7000             # frames totales de simulación de riesgo
    risk_increase_chance: 0.0005      # probabilidad de propagación [0,1]
    starting_risks:                   # riesgo inicial por nodo [[id, valor],...]
      - ["8", 1.0]
    risk_overrides:                   # cambios de riesgo en frames concretos
      - [2200, "153", 0.6]            # [frame, nodo, valor]
    risk_threshold: 0.5               # umbral para considerar nodo peligroso
    propagation_threshold: 0.5        # umbral de propagación entre vecinos
  gamma: 0.3                          # peso del riesgo en el coste de rutas
  stairs_max_speed: 0.6               # velocidad máxima en escaleras (m/s)
  normal_max_speed: 1.2               # velocidad máxima en pasillos (m/s)
  every_nth_frame_simulation: 3       # submuestra de frames para el routing
  every_nth_frame_animation: 50       # submuestra de frames para animación
  danger_visualization_frame: 2200    # frame para captura de mapa de riesgo
  # Opcionales:
  group_split_threshold: 5            # tamaño mínimo para dividir grupos
  distance_to_agents: 0.4             # separación entre agentes al posicionarlos
  distance_to_polygon: 0.5            # separación mínima de paredes al posicionar
```

Los valores no especificados se toman de `configs/defaults.yaml`.

---

## 4. Scripts de ejecución principal

### 4.1 `evac-sim run` / `python -m evac_sim`

**Propósito:** Ejecutar uno o varios casos de simulación definidos en un archivo YAML.

**Invocación:**
```bash
evac-sim run --config study.yaml --case corridor_case_1
evac-sim run --config management_building.yaml --environment management_building_basement
python -m evac_sim run --config study.yaml --case corridor_case_1
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | `study.yaml` | Nombre del archivo YAML dentro de `./configs/` |
| `--case` | str | None | ID del caso a ejecutar (excluyente con `--environment`) |
| `--scenario` | str | None | Alias de `--case` |
| `--environment` | str | None | Ejecutar todos los casos con ese entorno |
| `--project-root` | str | `.` | Directorio raíz del proyecto |
| `--out-dir` | str | None | Directorio de salida (solo para un caso; default: `./runs/<ts>_<case>`) |
| `--output-dir` | str | None | Alias de `--out-dir` |
| `--output-format` | str | None | Si se especifica (o si se usa `--scenario`), además de la simulación escribe `result.json`/CSVs/animaciones HTML como `run_scenario` (ver [6.2](#62-run_scenario)); valores: `json`, `csv`, `html` separados por coma. Requiere un único caso (no compatible con `--environment`) |
| `-v` / `--verbose` | flag | False | Logs detallados |
| `--heuristic` | choice | `none` | Heurística de routing: `none`, `h1`, `h2`, `h3` |
| `--horizon-k` | int | 6 | Horizonte de reserva de aristas para heurística `h2` |
| `--congestion-reroute-epsilon` | float | 0.1 | Umbral de mejora para desvío por congestión |

**Salidas (en `./runs/<timestamp>_<case>/`):**
```
config_resolved.yaml          # configuración final con defaults aplicados
metadata.json                 # timestamp, git commit, plataforma, heurística
logs/run.log                  # log completo de ejecución
artifacts/db/simulation.db    # base de datos SQLite con métricas y trayectorias de grupos
artifacts/db/<env>_mode_<n>.sqlite   # trayectorias JuPedSim por modo
artifacts/csv/experiments.csv        # resumen de experimentos
artifacts/csv/experiment_metrics.csv # métricas por grupo de agentes
artifacts/images/             # capturas de animación y mapa de riesgo
```

> Si se usa `--scenario`/`--output-format`, también se escriben `result.json`,
> `agents.csv`/`summary.csv` y (con `html`) `artifacts/animations/<env>_mode_<n>.html`
> directamente bajo `--output-dir` — ver [6.2 `run_scenario`](#62-run_scenario).

---

## 5. Scripts de inspección de entornos

### 5.1 `inspect_grid_layout`

**Módulo:** `evac_sim.envs.scripts.inspect_grid_layout`

**Propósito:** Inspeccionar visualmente el layout de un entorno: área caminable,
waypoints/nodos, edges/conexiones, capacidades y áreas específicas. Ahora también
permite exportar la imagen y los datos del layout.

**Invocación:** también disponible como `evac-sim inspect ...` (reenvía todos los
argumentos tal cual a este script).
```bash
evac-sim inspect \
    --env management_building_basement \
    --layout-source current \
    --show-node-id \
    --show-edge-weights \
    --output-image results/layouts/basement.png \
    --output-data results/layouts/basement_layout.json

evac-sim inspect \
    --env corridor \
    --method greedy \
    --min-cell-size 1.0 \
    --print-waypoints \
    --no-plot
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--env` | str | `corridor` | Nombre del entorno (ver sección 9) |
| `--method` | choice | `greedy` | Algoritmo de celdas: `greedy`, `quadtree`, `convex_navmesh` |
| `--layout-source` | choice | `computed` | `computed` = calcular; `current` = usar datos del entorno |
| `--refresh-current-edges` | flag | False | Recalcular distancias de edges en layout `current` |
| `--refresh-current-node-capacities` | flag | False | Recalcular capacidades de nodos desde áreas |
| `--print-node-capacities` | flag | False | Imprimir `node_capacities` como dict Python |
| `--node-density-agents-per-m2` | float | 2.0 | Densidad para calcular capacidad de nodos |
| `--edge-flow-agents-per-meter` | float | 4.0 | Flujo por metro de ancho para capacidad de edges |
| `--fallback-edge-width` | float | 1.0 | Ancho fallback para edges sin frontera medible |
| `--min-cell-size` | float | 1.0 | Tamaño mínimo de celda |
| `--max-cell-size` | float | None | Tamaño máximo de celda (quadtree) |
| `--accept-partial-min-cells` | flag | False | Quadtree: aceptar celdas parciales por centro |
| `--greedy-min-square-size` | float | None | Greedy: tamaño mínimo de cuadrado a conservar |
| `--greedy-center-within` | flag | False | Greedy: aceptar celdas por centro en vez de cobertura total |
| `--waypoint-radius-mode` | choice | `largest` | Modo de radio: `largest` (máximo inscrito) o `ratio` |
| `--radius` | float | None | Radio fijo de waypoints |
| `--radius-ratio` | float | 0.25 | Radio como fracción del tamaño de celda |
| `--max-waypoint-radius` | float | 0.35 | Radio máximo de waypoints |
| `--show-node-id` | flag | False | Mostrar IDs de nodos en el plot |
| `--show-cell-id` | flag | False | Mostrar IDs de celdas en el plot |
| `--show-cell-size` | flag | False | Mostrar tamaño de cada celda |
| `--show-edge-weights` | flag | False | Mostrar pesos de edges |
| `--no-plot` | flag | False | No mostrar el plot interactivo |
| `--print-summary` | flag | False | Imprimir resumen del layout |
| `--print-waypoints` | flag | False | Imprimir waypoints como dict Python |
| `--print-edges` | flag | False | Imprimir edges como lista Python |
| `--print-specific-areas` | flag | False | Imprimir polígonos de celdas como dict Python |
| `--navmesh-min-area` | float | 1 | Área mínima de triángulo (navmesh) |
| `--navmesh-max-area` | float | 5 | Área máxima antes de subdividir (navmesh) |
| **`--output-image`** | str | None | **[NUEVO]** Guardar el plot en archivo (PNG, SVG, PDF...) |
| **`--output-data`** | str | None | **[NUEVO]** Exportar layout (waypoints, edges, áreas) a JSON |

**Salidas:**
- Plot interactivo matplotlib (a menos que `--no-plot`)
- `<output-image>` si se especifica: imagen del layout
- `<output-data>` si se especifica: JSON con `waypoints`, `edges`, `specific_areas`, `nodes`, `metadata`

---

### 5.2 `inspect_walkable_area`

**Módulo:** `evac_sim.envs.scripts.inspect_walkable_area`

**Propósito:** Visualizar únicamente el polígono del área caminable de un entorno.
Útil para verificar rápidamente la geometría antes de generar un layout.

**Invocación:**
```bash
python -m evac_sim.envs.scripts.inspect_walkable_area --env management_building_floor_1
python -m evac_sim.envs.scripts.inspect_walkable_area --env corridor
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--env` | str | `management_building_floor_1` | Nombre del entorno a visualizar |

**Salidas:** Plot matplotlib del área caminable con obstáculos.

---

### 5.3 `generate_layout`

**Módulo:** `evac_sim.envs.scripts.generate_layout`

**Propósito:** Generar un layout JSON editable y una imagen de previsualización
a partir del área caminable de un entorno, usando uno de los tres algoritmos de
descomposición de celdas disponibles.

**Invocación:**
```bash
python -m evac_sim.envs.scripts.generate_layout \
    --env management_building_basement \
    --algorithm greedy \
    --min-cell-size 1.0 \
    --show-node-id

python -m evac_sim.envs.scripts.generate_layout \
    --env corridor \
    --algorithm quadtree \
    --min-cell-size 0.5 \
    --max-cell-size 2.0
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--env` | str | **requerido** | Nombre del entorno |
| `--algorithm` / `--method` | choice | **requerido** | `greedy`, `quadtree`, `convex_navmesh` |
| `--output-root` | str | `../generated_layouts` | Carpeta raíz para la salida |
| `--min-cell-size` | float | 1.0 | Tamaño base (greedy) o mínimo (quadtree) de celda |
| `--max-cell-size` | float | None | Tamaño máximo inicial (quadtree) |
| `--accept-partial-min-cells` | flag | False | Quadtree: aceptar celdas mínimas parciales |
| `--greedy-min-square-size` | float | None | Greedy: tamaño mínimo a conservar |
| `--greedy-center-within` | flag | False | Greedy: criterio centro-dentro para celdas base |
| `--navmesh-min-area` | float | 0.02 | Descartar triángulos menores que esto |
| `--navmesh-max-area` | float | 0.35 | Subdividir triángulos mayores que esto (≤0 desactiva) |
| `--waypoint-radius` | float | None | Radio fijo de waypoints |
| `--radius-ratio` | float | None | Radio como fracción del tamaño de celda |
| `--min-waypoint-radius` | float | 0.10 | Radio mínimo de waypoints |
| `--max-waypoint-radius` | float | None | Radio máximo de waypoints |
| `--show-cell-id` / `--hide-cell-id` | flag | True/False | Mostrar IDs de celdas en previsualización |
| `--show-node-id` / `--hide-node-id` | flag | True/False | Mostrar IDs de nodos |
| `--show-edge-weights` | flag | False | Mostrar pesos de edges |
| `--dpi` | int | 220 | Resolución de la imagen de previsualización |

**Salidas (en `<output-root>/<env>_<algo>_<timestamp>/`):**
- `layout.json` — layout serializado (waypoints, edges, specific_areas, graph)
- `preview.png` — imagen de previsualización del layout

---

## 6. Scripts de utilidad (nuevos)

### 6.1 `validate_scenario_config`

**Módulo:** `evac_sim.envs.scripts.validate_scenario_config`

**Propósito:** Validar una configuración de escenario antes de ejecutar la simulación.
Comprueba que fuentes, destinos, agentes, parámetros de riesgo y conectividad
son coherentes. Si es válida, escribe un YAML normalizado.

**Invocación:** también disponible como `evac-sim validate ...`.
```bash
evac-sim validate \
    --config configs/management_building.yaml \
    --scenario basement \
    --output configs/generated/basement.validated.yaml

evac-sim validate \
    --config configs/study.yaml \
    --scenario corridor_case_1
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | **requerido** | Ruta al YAML (relativa a `--project-root` o absoluta) |
| `--scenario` | str | **requerido** | Clave del escenario dentro del YAML |
| `--output` | str | None | Ruta del YAML validado (solo se escribe si es válido) |
| `--project-root` | str | `.` | Directorio raíz del proyecto |

**Validaciones realizadas:**
1. El entorno existe y se puede cargar
2. Todos los `sources` existen como nodos del grafo del entorno
3. Todos los `targets` existen como nodos del grafo
4. `len(agents) == len(sources)` y todos los valores de agentes > 0
5. `mode_type` ∈ {0, 1, 2, 3, 4, 5}
6. `master_seed` presente (genera uno aleatorio si falta, con warning)
7. Parámetros numéricos: `gamma`, `stairs_max_speed`, `normal_max_speed` > 0
8. `every_nth_frame_simulation`, `every_nth_frame_animation`, `danger_visualization_frame` > 0
9. Parámetros de riesgo: `risk_increase_chance`, `risk_threshold`, `propagation_threshold` ∈ [0,1]
10. Nodos en `starting_risks` y `risk_overrides` existen en el grafo
11. Al menos un target es alcanzable desde cada source (conectividad de grafo)
12. **Warning** si algún waypoint tiene radio < 0.15 m y ≤ 2 edges (posible paso estrecho)

**Salida en consola:**
```
Scenario: basement
Status:   VALID

Warnings (1):
  - 'master_seed' was missing; assigned random seed 482931.

Validated YAML written to: configs/generated/basement.validated.yaml
```

```
Scenario: basement
Status:   INVALID

Errors (2):
  - source '999' does not exist in environment 'management_building_basement'.
  - target '5' is unreachable from source '278'.
```

**Código de salida:** 0 si válido, 1 si hay errores.

---

### 6.2 `run_scenario`

**Módulo:** `evac_sim.simulation.scripts.run_scenario`

**Propósito:** Ejecutar un escenario validado y producir salida estructurada en
JSON y CSV, apta para integración con aplicaciones externas. Envuelve el runner
estándar y post-procesa las bases de datos SQLite de JuPedSim.

**Invocación:** también disponible como `evac-sim run --scenario ... --output-format ...`
(alias de `--case`/`--out-dir`; ver [4.1](#41-evac-sim-run--python--m-evac_sim)).
```bash
evac-sim run \
    --config configs/management_building.yaml \
    --scenario basement \
    --output-dir results/api/basement \
    --output-format json,csv,html

evac-sim run \
    --config configs/study.yaml \
    --scenario corridor_case_1 \
    --heuristic h1 \
    --verbose
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | `study.yaml` | Nombre del YAML en `./configs/` o ruta absoluta |
| `--scenario` | str | None | Clave del escenario en el YAML |
| `--output-dir` | str | None | Directorio de salida (sin él no se genera `result.json`) |
| `--output-format` | str | `json,csv` | Formatos: `json`, `csv`, `html` (separados por coma) |
| `--project-root` | str | `.` | Directorio raíz |
| `--heuristic` | choice | `none` | Heurística de routing: `none`, `h1`, `h2`, `h3` |
| `--horizon-k` | int | 6 | Horizonte de reserva para heurística `h2` |
| `--congestion-reroute-epsilon` | float | 0.1 | Umbral de mejora para desvío por congestión |
| `-v` / `--verbose` | flag | False | Logs detallados |

**Salidas (en `--output-dir`):**

Además de todos los archivos generados por `evac-sim run` (ver sección 4.1),
produce `result.json` y `agents.csv` / `summary.csv`. Con `--output-format`
incluyendo `html`, además produce `artifacts/animations/<env>_mode_<n>.html`:
un replay interactivo (Plotly, autocontenido, sin dependencias externas) con
controles de play y slider de frame, uno por cada modo de enrutamiento —
la misma animación que genera `Notebooks/replay_existing_run.ipynb`.

`result.json` — estructura completa:
```json
{
  "scenario_name": "basement",
  "environment": "management_building_basement",
  "status": "completed",
  "timestamp": "2026-07-01T12:00:00",
  "config": { ... },
  "summary": {
    "total_agents": 11,
    "evacuated_agents": 11,
    "not_evacuated_agents": 0,
    "evacuation_time": 142.3,
    "average_evacuation_time": 89.5,
    "max_evacuation_time": 142.3,
    "total_frames": 4560,
    "groups": [...]
  },
  "agents": [
    {
      "agent_id": 1,
      "mode": 0,
      "evacuated": true,
      "evacuation_time": 95.2,
      "trajectory": [
        {"frame": 0, "x": 1.4, "y": 3.4, "node": "278"},
        {"frame": 3, "x": 1.6, "y": 3.5}
      ]
    }
  ],
  "risks": [
    {"frame": 0, "node": "8", "risk": 1.0}
  ],
  "events": [],
  "diagnostics": {
    "blocked_agents": [],
    "congestion_points": [],
    "warnings": []
  }
}
```

Si la simulación falla, `status` es `"failed"` y se añade:
```json
{
  "status": "failed",
  "error": {
    "type": "ValueError",
    "message": "...",
    "traceback": "..."
  }
}
```

**Código de salida:** 0 si la simulación se completó, 1 si falló.

---

## 7. Herramientas de análisis (tools/)

### 7.1 `run_all_congestion_heuristics`

**Propósito:** Ejecutar todos los casos de un YAML con todas las heurísticas
(none/h1/h2/h3) de forma sistemática, generando una estructura de resultados
organizada por heurística y caso.

**Invocación:**
```bash
python tools/run_all_congestion_heuristics.py \
    --config congestion_heuristics.yaml \
    --runs-dir runs/congestion_heuristics \
    --heuristics none h1 h2 h3 \
    --horizon-k 6
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | `congestion_heuristics.yaml` | YAML de configuración |
| `--runs-dir` | Path | `runs/congestion_heuristics_efficient_high` | Directorio raíz de salida |
| `--cases` | list | None (todos) | Subset de IDs de caso a ejecutar |
| `--heuristics` | list | `none h1 h2 h3` | Heurísticas a ejecutar |
| `--mode-type` | int | 5 | `mode_type` forzado para todos los casos |
| `--horizon-k` | int | 6 | Horizonte de reserva para h2 |
| `--congestion-reroute-epsilon` | float | 0.15 | Umbral de desvío por congestión |
| `--baseline` | choice | `none` | Heurística de referencia para comparativas |
| `--continue-on-error` | flag | False | No abortar ante fallos individuales |
| `--dry-run` | flag | False | Crear manifiesto sin ejecutar simulaciones |
| `--skip-comparison` | flag | False | Omitir informe de comparación |
| `--skip-scenario-report` | flag | False | Omitir informe por escenario |
| `--with-visual-pdfs` | flag | False | Generar PDFs de trayectorias/densidad |

**Salidas:** Árbol de directorios bajo `--runs-dir`:
```
runs-dir/
├── run_manifest.json
├── none/<case_id>/...
├── h1/<case_id>/...
├── h2/<case_id>/...
└── h3/<case_id>/...
```

---

### 7.2 `generate_random_congestion_yaml`

**Propósito:** Generar automáticamente configuraciones YAML con casos aleatorios
reproducibles (fuentes, destinos y número de agentes aleatorios por escenario).

**Invocación:**
```bash
python tools/generate_random_congestion_yaml.py \
    --base-config congestion_heuristics.yaml \
    --output-config random_efficient_high_congestion.yaml \
    --configs-per-scenario 5 \
    --master-seed 1234
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--base-config` | str | `congestion_heuristics.yaml` | Config base dentro de `configs/` |
| `--output-config` | str | `random_efficient_high_congestion.yaml` | Nombre del YAML de salida |
| `--configs-per-scenario` | int | 5 | Número total de casos por escenario |
| `--master-seed` | int | 1234 | Semilla maestra para reproducibilidad |
| `--agents-per-source-min` | int | 20 | Mínimo de agentes por nodo fuente |
| `--agents-per-source-max` | int | 80 | Máximo de agentes por nodo fuente |
| `--sources-per-case-min` | int | 1 | Mínimo de fuentes por caso |
| `--sources-per-case-max` | int | 4 | Máximo de fuentes por caso |
| `--targets-per-case-min` | int | 1 | Mínimo de destinos por caso |
| `--targets-per-case-max` | int | 3 | Máximo de destinos por caso |
| `--required-sources` | list | `[]` | Nodos forzados como fuente (`escenario:n1,n2`) |
| `--required-targets` | list | `[]` | Nodos forzados como destino (`escenario:n1,n2`) |
| `--scenarios` | list | todos | Escenarios a incluir |
| `--include-base-config` / `--no-base-config` | flag | True | Incluir caso base original |

**Salidas:**
- `configs/<output-config>` — YAML con todos los casos generados
- `configs/<output-config>.metadata.json` — metadatos de la generación

---

### 7.3 `build_derived_metrics`

**Propósito:** Post-procesar los archivos `simulation.db` generados por las
simulaciones para calcular métricas derivadas (densidad, tiempos de evacuación,
métricas de riesgo acumulado) y exportarlas a CSV.

**Invocación:**
```bash
python tools/build_derived_metrics.py \
    --runs-dir runs/congestion_heuristics_efficient_high \
    --metrics-config configs/metrics/default_metrics.yaml
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--runs-dir` | Path | `runs/congestion_heuristics_efficient_high` | Directorio con archivos `simulation.db` |
| `--metrics-config` | Path | `configs/metrics/default_metrics.yaml` | Config de métricas |
| `--simulation-config` | Path | None | YAML con overrides de métricas por caso |
| `--case` | list | `[]` | Filtrar a IDs de caso específicos (repetible) |
| `--dry-run` | flag | False | Mostrar qué se procesaría sin escribir |

**Salidas (junto a cada `simulation.db`):**
- `density_metrics.csv`
- `evacuation_metrics.csv`
- `comparison_metrics.csv`

---

### 7.4 `compare_congestion_heuristics`

**Propósito:** Generar un informe de comparación entre heurísticas para cada
caso de simulación, mostrando deltas de métricas respecto a una baseline.

**Invocación:**
```bash
python tools/compare_congestion_heuristics.py \
    --runs-dir runs/congestion_heuristics_efficient_high \
    --baseline none \
    --heuristics none h1 h2 h3
```

**Parámetros clave:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--runs-dir` | Path | `runs/congestion_heuristics_efficient_high` | Directorio raíz de runs |
| `--out-dir` | Path | `<runs-dir>/comparison` | Directorio de salida |
| `--metrics-config` | Path | `configs/metrics/default_metrics.yaml` | Config de métricas |
| `--heuristics` | list | `none h1 h2 h3` | Heurísticas a comparar |
| `--cases` | list | None (todos) | Filtrar casos |
| `--baseline` | choice | `none` | Heurística de referencia para deltas |
| `--metric` | str | None | Métrica principal para el resumen en terminal |
| `--require-all-heuristics` | flag | False | Saltar casos sin todas las heurísticas |
| `--skip-visual-pdfs` | flag | False | Omitir generación de PDFs visuales |
| `--density-frame-step` | int | 500 | Paso de frames para páginas de densidad |

**Salidas:**
- `comparison/comparison_report.md`
- `comparison/comparison_metrics_summary.csv`
- `comparison/visual_snapshots/<case>_trajectory.pdf` (si habilitado)

---

### 7.5 `compare_congestion_by_scenario`

**Propósito:** Agregar y comparar resultados a nivel de escenario (agrupando
todos los casos de un mismo escenario), produciendo estadísticas y rankings.

**Invocación:**
```bash
python tools/compare_congestion_by_scenario.py \
    --run-root runs/congestion_heuristics_efficient_high \
    --baseline none
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--run-root` | Path | `runs/congestion_heuristics_efficient_high` | Raíz con subdirectorios por heurística |
| `--output-dir` | Path | `<run-root>/comparison/scenario_strategy` | Directorio de salida |
| `--exclude-base` | flag | False | Excluir casos `base_*` de las estadísticas |
| `--baseline` | choice | `none` | Heurística base para calcular deltas |

**Salidas:**
- `scenario_strategy_report.md`
- `scenario_strategy_summary.csv`
- `scenario_deltas.csv`
- `scenario_composite_scores.csv`
- (y otros CSVs de ranking)

---

### 7.6 `diagnose_h2_k`

**Propósito:** Diagnóstico del parámetro `k` (horizonte de reserva) de la
heurística `h2`. Ejecuta el mismo conjunto de casos con distintos valores de k
y agrega los resultados para encontrar el valor óptimo.

**Invocación:**
```bash
python tools/diagnose_h2_k.py \
    --config congestion_heuristics.yaml \
    --k-values 2 3 4 6 8 10 \
    --runs-dir runs/h2_k_diagnostic
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | **requerido** | YAML de configuración |
| `--k-values` | list[int] | **requerido** | Valores de k a probar |
| `--cases` | list | None (todos) | Filtrar a casos específicos |
| `--runs-dir` | Path | `runs/h2_k_diagnostic` | Directorio raíz de salida |
| `--continue-on-error` | flag | False | No abortar ante fallos |

**Salidas:** Árbol de resultados por valor de k, más un resumen comparativo.

---

### 7.7 `profile_single_congestion_case`

**Propósito:** Ejecutar un solo caso con validación previa (preflight check) y
opcionalmente con `cProfile` para análisis de rendimiento.

**Invocación:**
```bash
python tools/profile_single_congestion_case.py \
    --config congestion_heuristics.yaml \
    --case congestion_parallel_corridors_base \
    --heuristic h3 \
    --profile
```

**Parámetros:**

| Argumento | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--config` | str | **requerido** | YAML de configuración |
| `--case` | str | **requerido** | ID del caso a ejecutar |
| `--heuristic` | choice | `h3` | Heurística: `none`, `h1`, `h2`, `h3` |
| `--horizon-k` | int | 6 | Horizonte de reserva para h2 |
| `--congestion-reroute-epsilon` | float | 0.15 | Umbral de desvío por congestión |
| `--out-dir` | Path | None | Directorio de salida |
| `--profile` | flag | False | Activar cProfile y escribir `profile_cumtime.txt` |

---

## 8. Estructura de salidas

### Ejecución individual (`evac-sim run` / `run_scenario`)

```
runs/<timestamp>_<case>/
├── config_resolved.yaml          # configuración final con defaults aplicados
├── metadata.json                 # info del run: timestamp, git, plataforma
├── logs/
│   └── run.log                   # log completo
└── artifacts/
    ├── db/
    │   ├── simulation.db         # SQLite con tablas:
    │   │                         #   experiments, experiment_metrics
    │   │                         #   agent_area_data, risk_data
    │   │                         #   group_path_data, paths
    │   └── <env>_mode_<n>.sqlite # trayectorias JuPedSim (frame, id, pos_x, pos_y)
    ├── csv/
    │   ├── experiments.csv
    │   └── experiment_metrics.csv
    └── images/
        └── ...                   # capturas de animación y mapa de riesgo
```

Si se usa `evac-sim run --scenario ... --output-format ...` (alias de `run_scenario`,
ver [6.2](#62-run_scenario)) con `--output-dir`:
```
<output-dir>/
├── [todo lo anterior]
├── result.json         # salida JSON estructurada completa
├── agents.csv          # tabla de agentes (agent_id, mode, evacuated, evacuation_time)
├── summary.csv         # resumen de métricas clave
└── artifacts/animations/<env>_mode_<n>.html   # solo si --output-format incluye "html"
```

### Tablas en `simulation.db`

| Tabla | Columnas clave | Descripción |
|-------|---------------|-------------|
| `experiments` | `case_name, source_nodes, agents_per_source, random_seed` | Configuración del experimento |
| `experiment_metrics` | `experiment_id, agent_group_id, algorithm, avg_time, max_time, ...` | Métricas por grupo |
| `agent_area_data` | `case_name, mode, frame, agent_id, area, risk_level` | Posición de agentes por frame |
| `risk_data` | `case_name, frame, area, risk_level` | Nivel de riesgo por nodo y frame |
| `group_path_data` | `case_name, mode, frame, group_id, algorithm, current_area, next_path, ...` | Decisiones de routing |

---

## 9. Entornos disponibles

| Nombre | Descripción |
|--------|-------------|
| `corridor` | Pasillo simple |
| `cruise_ship` | Buque de crucero (versión original) |
| `cruise_ship_v2` | Buque de crucero (versión 2, más compleja) |
| `cruise_ship_new` | Buque de crucero (versión nueva) |
| `mall` | Centro comercial |
| `simple_3x3` | Grid 3×3 de prueba |
| `theme_park` | Parque temático |
| `management_building_basement` | Sótano del edificio de gestión |
| `management_building_floor_0` | Planta baja del edificio de gestión |
| `management_building_floor_1` | Primera planta del edificio de gestión |
| `parallel_corridors` | Escenario de congestión: pasillos paralelos |
| `two_exits` | Escenario de congestión: dos salidas |
| `short_vs_wide` | Escenario de congestión: ruta corta vs. ancha |
| `comparing_algorithms` | Entorno para comparar algoritmos |

---

## 10. Diagnóstico: agentes atascados en management_building

### Descripción del problema

En los escenarios del edificio de gestión (`management_building_basement`,
`management_building_floor_0`, `management_building_floor_1`), algunos agentes
pueden quedar atascados o en colas muy largas en zonas estrechas.

### Análisis de causas

**Causa 1 — Capacidad de flujo uniforme (flow_capacity = 1)**

Casi todos los edges del grafo del management_building tienen `flow_capacity = 1`.
Esto significa que, cuando se usan heurísticas de reserva de capacidad (h2/h3),
cada edge solo permite pasar 1 agente por ciclo de reserva.

En corredores que físicamente tendrían anchura > 1 m (capacidad real para 2-3
agentes simultáneos), esta limitación crea colas artificiales. Los agentes de
source "278" (posición x=1.4, y=3.4) que necesitan recorrer ~25 metros hasta
target "5" (x=25.9, y=12.9) cruzan decenas de edges con flow_capacity=1.

```
Impacto: con heuristic=none → no hay reservas, el atasco es puramente físico
         con heuristic=h2/h3 → el routing dispersa agentes pero la capacidad 1
         crea colas en puntos de paso obligatorio (puertas, esquinas)
```

**Causa 2 — Pasillos estrechos en la geometría**

La definición de obstáculos incluye segmentos muy delgados (del orden de 0.09 m)
que representan los marcos de puertas en el plano del edificio. Ejemplos:

- En obstacle 2: gap de x=5.61..5.70 (ancho=0.09 m) — posible marco de puerta
- En obstacle 1: segmentos de y=11.7..11.8 y x=8.03..8.18

Estos artefactos geométricos reducen el espacio caminable efectivo cerca de
algunos waypoints, haciendo que JuPedSim tenga dificultad para planificar
trayectorias físicamente factibles.

**Causa 3 — Radios de waypoints uniformes de 0.25 m**

Con un radio de aceptación de 0.25 m, los agentes consideran que han llegado
al waypoint cuando están a menos de 0.25 m del centro. En zonas donde dos
waypoints están a 0.87 m de distancia (valor mínimo encontrado: edge con
cost=0.86..0.87), el radio de aceptación representa el 28% de la distancia
entre nodos, lo que puede causar interferencia entre waypoints.

**Causa 4 — Concentración de rutas**

Con `mode_type=0` (routing Eficiente, dijkstra), todos los agentes de un grupo
toman exactamente la misma ruta. Grupos de 5-25 agentes convergiendo sobre el
mismo pasillo crean congestión física independiente de la heurística.

### Diagnóstico automático con validate_scenario_config

El nuevo script `validate_scenario_config` detecta automáticamente estos warnings:

```bash
evac-sim validate \
    --config configs/management_building.yaml \
    --scenario floor_1

# Output esperado:
# Warnings:
#   - Node '...' has a very small radius (0.150 m) and only 2 edge(s) — possible narrow passage.
```

### Soluciones recomendadas

**Solución 1 (recomendada): Aumentar flow_capacity en corredores anchos**

En `management_building.py`, los edges de nodos hub (con radio=0.5 o 1.0) y
de los corredores principales deberían tener `flow_capacity=2` o superior.

Ejemplo de corrección en los edges del basement:
```python
# Antes (todos los edges):
("18", "29", 2.0, 1),   # edge largo entre zonas → flow_capacity=1

# Después:
("18", "29", 2.0, 4),   # corredor 2m ancho → capacidad 4 agentes
```

Los edges que conectan nodos hub (radios 0.5 o 1.0 m) con su entorno deberían
tener `flow_capacity` proporcional al ancho del pasillo: `floor(width × 4)`.

**Solución 2: Ajustar parámetros de JuPedSim**

Reducir `distance_to_polygon` de 0.5 a 0.3 m en `configs/management_building.yaml`
para que los agentes puedan posicionarse más cerca de paredes sin solapamiento:
```yaml
distance_to_polygon: 0.3
```

**Solución 3: Usar heurística h1 con congestion_reroute_epsilon bajo**

La heurística h1 con epsilon=0.05 distribuye mejor los agentes entre rutas
alternativas, reduciendo la congestión en pasos obligatorios:
```bash
python -m evac_sim.simulation.scripts.run_scenario \
    --config configs/management_building.yaml \
    --scenario floor_1 \
    --heuristic h1 \
    --congestion-reroute-epsilon 0.05 \
    --output-dir results/api/floor_1_h1
```

**Nota importante:** No se recomienda ampliar la geometría del entorno ni
reubicar waypoints sin verificar primero con `inspect_grid_layout` que el
problema es geométrico y no de routing. Los artefactos de marcos de puertas
(~0.09 m) son parte del plano arquitectónico y no deben modificarse.

---

*Documento generado automáticamente — `docs/SCRIPTS_REFERENCE.md`*
