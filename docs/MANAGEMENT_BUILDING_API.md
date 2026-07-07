# Management Building — Guía de ejecución para integración de interfaz

Esta guía explica exactamente qué comandos ejecutar, qué parámetros configurar y qué salida esperar al correr los escenarios de evacuación del `management_building`. Está pensada para alguien que va a construir una interfaz y no conoce el proyecto internamente.

---

## Requisitos previos

El proyecto usa un entorno virtual Python localizado en `.venv/`. Todos los comandos deben ejecutarse **desde la raíz del proyecto**:

```
C:\GitHub\Evacuation_Simulation\
```

Activar el entorno (opcional si se llama con ruta completa):
```bash
.venv\Scripts\activate
```

O usar siempre la ruta completa al intérprete:
```
.venv\Scripts\python.exe
```

Con el paquete instalado (`pip install -e .`), todos los comandos de esta guía están
disponibles también como el ejecutable `evac-sim` (más corto que `.venv\Scripts\python.exe
-m evac_sim...`). Ambas formas son equivalentes; esta guía usa `evac-sim`.

---

## Flujo completo (resumen rápido)

```
1. [Opcional] Escribir YAML mínimo con los campos obligatorios
        ↓
2. validate_scenario_config --output → genera YAML normalizado con semilla y defaults
        ↓
3. run_scenario --config <yaml_generado> → ejecuta simulación y escribe result.json
```

---

## Paso 0 — Generar un config YAML válido desde una plantilla mínima

`validate_scenario_config` con el flag `--output` actúa como **generador de config**: toma un YAML mínimo (con los campos obligatorios), lo valida, rellena los valores que falten (como `master_seed`) y escribe un YAML normalizado listo para simular.

### YAML mínimo de entrada

Crear un archivo, por ejemplo `configs/mi_escenario.yaml`, con solo los campos obligatorios:

```yaml
mi_escenario:
  environment: "management_building_floor_0"
  sources: ["1", "25"]
  agents: [8, 4]
  targets: ["11", "139", "17", "47"]
  mode_type: 5  # ver "Valores de mode_type" 
  gamma: 0.2
  stairs_max_speed: 0.6
  normal_max_speed: 1.2
  every_nth_frame_simulation: 3
  every_nth_frame_animation: 50
  danger_visualization_frame: 2500
  risk:
    enabled: true
    risk_iterations: 7000
    risk_increase_chance: 0.005
    risk_threshold: 0.5
    propagation_threshold: 0.5
  distance_to_agents: 0.3
  distance_to_polygon: 0.1
```

> `master_seed` es el único campo que puede omitirse — el script lo genera automáticamente.

### Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `environment` | string | Nombre del entorno registrado |
| `sources` | lista de strings | IDs de nodos de inicio |
| `agents` | lista de int | Nº de agentes por source (mismo orden) |
| `targets` | lista de strings | IDs de nodos de salida |
| `mode_type` | int (0–5) | Modo de enrutamiento (ver [Valores de `mode_type`](#valores-de-mode_type); se recomienda `5`) |
| `gamma` | float > 0 | Peso del riesgo en la ruta |
| `stairs_max_speed` | float > 0 | Velocidad en escaleras (m/s) |
| `normal_max_speed` | float > 0 | Velocidad normal (m/s) |
| `every_nth_frame_simulation` | int > 0 | Cada cuántos frames se registra posición |
| `every_nth_frame_animation` | int > 0 | Cada cuántos frames se guarda animación |
| `danger_visualization_frame` | int > 0 | Frame para calcular visualización de riesgo |
| `risk.enabled` | bool | Activar propagación de riesgo |
| `risk.risk_iterations` | int > 0 | Frames de precalentamiento del riesgo |
| `risk.risk_increase_chance` | float [0,1] | Probabilidad de incremento del riesgo por frame |
| `risk.risk_threshold` | float [0,1] | Umbral para desviar agentes |
| `risk.propagation_threshold` | float [0,1] | Umbral de propagación a vecinos |

### Comando

```bash
evac-sim validate `
    --config configs/mi_escenario.yaml `
    --scenario mi_escenario `
    --output configs/mi_escenario_validated.yaml
```

### Salida en consola

```
Scenario: mi_escenario
Status:   VALID

Warnings (1):
  - 'master_seed' was missing; assigned random seed 700899.

Validated YAML written to: configs/mi_escenario_validated.yaml
```

El YAML generado en `configs/mi_escenario_validated.yaml` tiene todos los campos normalizados y la semilla fijada:

```yaml
mi_escenario:
  environment: management_building_floor_0
  sources:
  - '1'
  - '25'
  agents:
  - 8
  - 4
  targets:
  - '11'
  - '139'
  - '17'
  - '47'
  mode_type: 0  # ver "Valores de mode_type" más abajo — se recomienda 5
  gamma: 0.2
  stairs_max_speed: 0.6
  normal_max_speed: 1.2
  every_nth_frame_simulation: 3
  every_nth_frame_animation: 50
  danger_visualization_frame: 2500
  risk:
    enabled: true
    risk_iterations: 7000
    risk_increase_chance: 0.005
    risk_threshold: 0.5
    propagation_threshold: 0.5
  distance_to_agents: 0.3
  distance_to_polygon: 0.1
  master_seed: 700899
```

### Simular directamente desde el YAML generado

```bash
evac-sim run `
    --config configs/mi_escenario_validated.yaml `
    --scenario mi_escenario `
    --output-dir results/api/mi_escenario `
    --output-format json,csv,html
```

> Añadir `html` a `--output-format` genera, además de `result.json`/CSVs, una
> animación interactiva (Plotly, con controles de play y slider de frame) por
> cada modo de enrutamiento simulado — ver [artifacts/animations/](#estructura-de-salida).

Salida en `results/api/mi_escenario/result.json`:

```json
{
  "scenario_name": "mi_escenario",
  "environment": "management_building_floor_0",
  "status": "completed",
  ...
}
```

---

## Paso 1 — Validar un escenario antes de ejecutarlo

### Comando

```bash
evac-sim validate `
    --config configs/management_building.yaml `
    --scenario <NOMBRE_ESCENARIO>
```

### Parámetros

| Parámetro | Obligatorio | Descripción |
|-----------|-------------|-------------|
| `--config` | ✅ | Ruta al fichero YAML. Para management_building: `configs/management_building.yaml` |
| `--scenario` | ✅ | Clave del escenario dentro del YAML. Valores válidos: `basement`, `floor_0`, `floor_1` |
| `--output` | ❌ | Ruta de salida para guardar el YAML validado/normalizado (opcional) |

### Salida en consola

```
Scenario: basement
Status:   VALID
```

Si hay errores:
```
Scenario: basement
Status:   INVALID

Errors (1):
  - source '999' does not exist in environment 'management_building_basement'
```

### Códigos de salida

| Código | Significado |
|--------|-------------|
| `0` | Escenario válido |
| `1` | Escenario inválido (ver errores en consola) |

### Ejemplos para los tres escenarios

```bash
# Basement
evac-sim validate --config configs/management_building.yaml --scenario basement

# Planta baja
evac-sim validate --config configs/management_building.yaml --scenario floor_0

# Primera planta
evac-sim validate --config configs/management_building.yaml --scenario floor_1
```

---

## Paso 2 — Ejecutar la simulación

### Comando

```bash
evac-sim run `
    --config configs/management_building.yaml `
    --scenario <NOMBRE_ESCENARIO> `
    --output-dir <DIRECTORIO_SALIDA> `
    --output-format json,csv,html
```

### Parámetros

| Parámetro | Obligatorio | Default | Descripción |
|-----------|-------------|---------|-------------|
| `--config` | ✅ | — | Ruta al YAML de configuración |
| `--scenario` | ✅ | — | Clave del escenario: `basement`, `floor_0` o `floor_1` |
| `--output-dir` | ❌ | `runs/<timestamp>_<scenario>` | Carpeta donde se guardan todos los resultados. Si existe debe estar vacía |
| `--output-format` | ❌ | `json,csv` | Formatos de salida separados por coma: `json`, `csv`, `html`, o cualquier combinación (p. ej. `json,csv,html`) |
| `--heuristic` | ❌ | `none` | Algoritmo de enrutamiento extra: `none`, `h1`, `h2`, `h3` |
| `--horizon-k` | ❌ | `6` | Solo con `--heuristic h2`: número de edges reservados |
| `--verbose` | ❌ | `false` | Mostrar logs detallados de la simulación |

> `evac-sim run` acepta `--scenario`/`--output-dir`/`--output-format` como alias
> amigables de las opciones internas `--case`/`--out-dir` que ya usaban otras
> herramientas del proyecto — ambos nombres funcionan igual.

### Ejemplos para cada escenario

```bash
# Basement → resultados en results/api/basement/
evac-sim run `
    --config configs/management_building.yaml `
    --scenario basement `
    --output-dir results/api/basement `
    --output-format json,csv,html

# Planta baja → resultados en results/api/floor_0/
evac-sim run `
    --config configs/management_building.yaml `
    --scenario floor_0 `
    --output-dir results/api/floor_0 `
    --output-format json,csv,html

# Primera planta → resultados en results/api/floor_1/
evac-sim run `
    --config configs/management_building.yaml `
    --scenario floor_1 `
    --output-dir results/api/floor_1 `
    --output-format json,csv,html
```

### Códigos de salida

| Código | Significado |
|--------|-------------|
| `0` | Simulación completada. `result.json` tiene `"status": "completed"` |
| `1` | Simulación fallida. `result.json` tiene `"status": "failed"` con `error_info` |

> **Nota de tiempo**: El basement tarda ~18 s, floor_0 ~30 s, floor_1 ~50 s en hardware de desarrollo.

---

## Estructura de salida

Todos los archivos se guardan en el `--output-dir` especificado:

```
<output-dir>/
├── result.json                        ← Resultado principal (JSON completo)
├── summary.csv                        ← Resumen numérico (CSV plano)
├── agents.csv                         ← Un agente por fila con tiempo de evacuación
├── config_resolved.yaml               ← Configuración efectiva usada
├── metadata.json                      ← Metadatos de la ejecución
├── logs/
│   └── run.log                        ← Log completo de la simulación
└── artifacts/
    ├── csv/
    │   ├── experiments.csv            ← Una fila por modo de enrutamiento
    │   └── experiment_metrics.csv     ← Métricas detalladas por grupo de agentes
    ├── db/
    │   ├── simulation.db              ← Base de datos SQLite con todos los datos
    │   ├── <env>_mode_0.sqlite        ← Trayectorias JuPedSim, modo 0
    │   ├── <env>_mode_1.sqlite        ← Trayectorias JuPedSim, modo 1
    │   ├── <env>_mode_2.sqlite        ← Trayectorias JuPedSim, modo 2
    │   └── <env>_mode_3.sqlite        ← Trayectorias JuPedSim, modo 3
    ├── images/
    │   ├── <env>_mode_0_density.png        ← Mapa de densidad (modo 0)
    │   ├── <env>_mode_0_trajectories.png   ← Mapa de trayectorias (modo 0)
    │   ├── <env>_mode_1_density.png
    │   ...
    └── animations/                          ← Solo si --output-format incluye "html"
        ├── <env>_mode_0.html                ← Replay interactivo (Plotly) del modo 0
        ├── <env>_mode_1.html
        ...
```

---

## Descripción de archivos de salida

### `result.json` — Resultado principal

Archivo JSON con toda la información del experimento. La interfaz debe leer principalmente este fichero.

```json
{
  "scenario_name": "basement",
  "environment": "management_building_basement",
  "status": "completed",
  "timestamp": "2026-07-01T12:07:42",

  "config": {
    "environment": "management_building_basement",
    "sources": ["24", "21", "1"],
    "agents": [2, 5, 5],
    "targets": ["41", "3"],
    "mode_type": 0,
    "master_seed": 233,
    "distance_to_agents": 0.3,
    "distance_to_polygon": 0.1,
    "risk": {
      "enabled": true,
      "risk_iterations": 7000,
      "risk_increase_chance": 0.005,
      "risk_threshold": 0.5,
      "propagation_threshold": 0.5
    },
    "gamma": 0.2,
    "normal_max_speed": 1.2
  },

  "summary": {
    "total_agents": 12,
    "evacuated_agents": 348,
    "not_evacuated_agents": 0,
    "evacuation_time": 29.97,
    "average_evacuation_time": 19.753,
    "max_evacuation_time": 29.97,
    "total_frames": 999,
    "groups": [
      {
        "group_id": "24",
        "algorithm": "Efficient",
        "n_evacuated": 9,
        "avg_time": 11.535,
        "median_time": 11.535,
        "p90_time": 12.099,
        "min_time": 10.83,
        "max_time": 12.24,
        "cumulative_risk_exposure": 0.0
      }
    ]
  },

  "agents": [
    {
      "agent_id": 1,
      "mode": 0,
      "evacuated": true,
      "evacuation_time": 12.24,
      "trajectory": [
        {"frame": 0, "x": 19.15, "y": 2.65, "node": "1"},
        {"frame": 3, "x": 19.22, "y": 2.71, "node": "1"},
        ...
      ]
    }
  ],

  "risks": [
    {"frame": 0, "node": "41", "risk": 0.0},
    {"frame": 50, "node": "41", "risk": 0.12}
  ],

  "events": [],

  "diagnostics": {
    "blocked_agents": [],
    "congestion_points": [],
    "warnings": []
  }
}
```

#### Campos del `summary`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `total_agents` | int | Número de agentes lanzados |
| `evacuated_agents` | int | Agentes que llegaron a un target (suma de todos los modos) |
| `not_evacuated_agents` | int | Agentes que no evacuaron |
| `evacuation_time` | float | Tiempo del último agente en evacuar (segundos) |
| `average_evacuation_time` | float | Media de tiempos de evacuación (segundos) |
| `max_evacuation_time` | float | Tiempo máximo individual (segundos) |
| `total_frames` | int | Frames totales de la simulación |
| `groups[].algorithm` | string | Algoritmo usado: `Efficient`, `Centrality`, `Mixed`, etc. |
| `groups[].n_evacuated` | int | Agentes evacuados del grupo (en todos los modos) |
| `groups[].avg_time` | float | Tiempo promedio de evacuación del grupo |
| `groups[].cumulative_risk_exposure` | float | Exposición acumulada al riesgo |

#### Campos de `agents[]`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `agent_id` | int | Identificador único del agente |
| `mode` | int | Modo de enrutamiento (0=Efficient, 1=Centrality, 2-5=mixed) |
| `evacuated` | bool | Si el agente alcanzó un nodo target |
| `evacuation_time` | float | Segundos hasta evacuar (null si no evacuó) |
| `trajectory[].frame` | int | Número de frame |
| `trajectory[].x` | float | Coordenada X en metros |
| `trajectory[].y` | float | Coordenada Y en metros |
| `trajectory[].node` | string | ID del nodo del grafo más cercano |

#### Campos de `risks[]`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `frame` | int | Frame en que se registra el riesgo |
| `node` | string | ID del nodo |
| `risk` | float | Nivel de riesgo (0.0 = sin riesgo, 1.0 = máximo) |

---

### `summary.csv` — Resumen plano

Una columna `field` y una columna `value`. Útil para mostrar en dashboards.

```
field,value
total_agents,12
evacuated_agents,348
not_evacuated_agents,0
evacuation_time,29.97
average_evacuation_time,19.753
max_evacuation_time,29.97
total_frames,999
```

---

### `agents.csv` — Por agente

Una fila por agente con su resultado individual.

```
agent_id,mode,evacuated,evacuation_time
1,0,True,12.24
2,0,True,10.83
3,0,True,16.92
```

---

### `artifacts/csv/experiment_metrics.csv` — Métricas detalladas por grupo

Una fila por grupo de agentes y modo de enrutamiento.

| Columna | Descripción |
|---------|-------------|
| `experiment_id` | ID del experimento (1 por modo) |
| `agent_group_id` | ID del grupo (coincide con el nodo source) |
| `algorithm` | Nombre del algoritmo de enrutamiento |
| `awareness` | Nivel de conciencia del riesgo (0.0–1.0) |
| `n_records` | Número de registros de trayectoria del grupo |
| `avg_time` | Tiempo medio de evacuación (s) |
| `median_time` | Mediana del tiempo de evacuación (s) |
| `p90_time` | Percentil 90 del tiempo de evacuación (s) |
| `min_time` | Tiempo mínimo (s) |
| `max_time` | Tiempo máximo (s) |
| `mean_remaining_path_risk` | Riesgo medio del camino restante |
| `cumulative_risk_exposure` | Exposición total al riesgo acumulada |

---

### `artifacts/db/<env>_mode_N.sqlite` — Trayectorias brutas

Base de datos SQLite con las trayectorias frame a frame de JuPedSim. Para leer:

```python
import sqlite3
conn = sqlite3.connect("artifacts/db/management_building_basement_mode_0.sqlite")

# Metadatos (FPS de la simulación)
fps = conn.execute("SELECT value FROM metadata WHERE key='fps'").fetchone()[0]

# Trayectorias: frame, agent_id, pos_x, pos_y
rows = conn.execute(
    "SELECT frame, id, pos_x, pos_y FROM trajectory_data ORDER BY frame, id"
).fetchall()
```

### `artifacts/db/simulation.db` — Base de datos interna

SQLite con tablas: `experiments`, `experiment_metrics`, `agent_area_data`, `risk_data`, `group_path_data`, `paths`.

---

### `artifacts/animations/<env>_mode_N.html` — Replay interactivo

Solo se genera cuando `--output-format` incluye `html`. Es un archivo HTML autocontenido
(no requiere conexión a internet ni servidor: el JavaScript de Plotly va embebido) con
la misma animación que produce `Notebooks/replay_existing_run.ipynb` — trayectorias de
los agentes coloreadas por velocidad, con botón de play y slider para navegar frame a
frame. Se genera un archivo por cada modo de enrutamiento simulado. La interfaz puede
simplemente ofrecer este fichero para abrir en una pestaña del navegador.

---

## Configuración YAML — Variables que puede cambiar la interfaz

El archivo `configs/management_building.yaml` contiene los tres escenarios. La interfaz puede modificar las siguientes variables antes de llamar al script:

### Variables de escenario (por escenario)

```yaml
basement:
  environment: "management_building_basement"   # NO cambiar
  sources: ["24", "21", "1"]                    # IDs de nodos de inicio
  agents: [2, 5, 5]                             # Nº agentes por source (mismo orden)
  targets: ["41", "3"]                          # IDs de nodos de salida/evacuación
  mode_type: 0                                  # Modo de enrutamiento (ver tabla, se recomienda 5)
  master_seed: 233                              # Semilla aleatoria (int, null = aleatorio)
```

### Variables de física del agente

```yaml
  distance_to_agents: 0.3     # Distancia mínima entre agentes (metros). Rango: 0.2–0.8
  distance_to_polygon: 0.1    # Distancia mínima a las paredes (metros). Rango: 0.05–0.5
  normal_max_speed: 1.2       # Velocidad máxima de un agente (m/s). Típico: 0.8–1.5
  stairs_max_speed: 0.6       # Velocidad en escaleras (m/s). Típico: 0.3–0.8
  gamma: 0.2                  # Peso del riesgo en la ruta (0.0=ignora riesgo, 1.0=máximo peso)
```

### Variables de riesgo

```yaml
  risk:
    enabled: true              # true/false — activar propagación de riesgo
    risk_iterations: 7000      # Frames de simulación de riesgo previos
    risk_increase_chance: 0.005  # Probabilidad de que el riesgo aumente por frame
    risk_threshold: 0.5        # A partir de qué nivel de riesgo se activa el desvío
    propagation_threshold: 0.5 # Umbral de propagación a nodos vecinos
    starting_risks: null       # Riesgos iniciales por nodo (null = ninguno)
    risk_overrides: null       # Sobreescritura manual de riesgos por nodo
```

### Valores de `mode_type`

`mode_type` controla con qué estrategia de enrutamiento se mueven los agentes. Cada estrategia combina dos ejes:

- **Algoritmo de ruta**: `shortest path` (Dijkstra, siempre el camino más corto/rápido) o `centrality` (prioriza nodos de alta centralidad para repartir el flujo entre varias rutas).
- **Nivel de conocimiento (`awareness`)**: `bajo` (el grupo solo recalcula su ruta cuando el **siguiente** nodo se vuelve peligroso) o `alto` (el grupo conoce el riesgo de **todo el camino restante** y recalcula en cuanto cualquier nodo por delante se vuelve peligroso — es decir, tiene conocimiento completo del entorno).

`mode_type` selecciona qué combinación(es) se simulan; la simulación ejecuta una pasada completa por cada modo incluido:

| `mode_type` | Algoritmo | Awareness | Descripción |
|-------|--------|--------|-------------|
| `0` | ambos | ambos | Ejecuta las 4 combinaciones (shortest/bajo, shortest/alto, centrality/bajo, centrality/alto) |
| `1` | shortest path | bajo y alto | Dos grupos con estrategia distinta asignada por índice de source |
| `2` | shortest path | bajo y alto | Compara awareness bajo vs. alto usando siempre la ruta más corta |
| `3` | centrality | bajo y alto | Compara awareness bajo vs. alto usando siempre centralidad |
| `4` | centrality | bajo | Solo centralidad con conocimiento bajo |
| `5` | shortest path | **alto** | Todos los agentes usan siempre la ruta más rápida y tienen conocimiento completo del entorno |

> **Recomendado: `mode_type: 5`.** Para estas simulaciones se recomienda este valor porque los agentes tienen conocimiento completo de su entorno (recalculan la ruta en cuanto cualquier nodo del camino restante se vuelve peligroso) y siempre usan el camino más rápido disponible (Dijkstra).

### Nodos disponibles por escenario

Los nodos se identifican con IDs numéricos (strings). Para saber qué nodos existen y sus posiciones:

```bash
# Ver el escenario en una ventana interactiva con los waypoints y sus node id
# (útil para elegir a mano los nodos source/target al crear la configuración)
evac-sim inspect `
    --env management_building_basement `
    --layout-source current `
    --show-node-id
```

Cambia `--env` por `management_building_floor_0` o `management_building_floor_1` según la planta que quieras inspeccionar.

```bash
# Alternativa sin ventana: genera imagen + JSON con todos los nodos (headless)
evac-sim inspect `
    --env management_building_basement `
    --layout-source current `
    --no-plot `
    --show-node-id `
    --output-image layout_basement.png `
    --output-data  layout_basement.json
```

> `evac-sim inspect` reenvía todos sus argumentos directamente a
> `inspect_grid_layout` — consulta `python -m evac_sim.envs.scripts.inspect_grid_layout --help`
> para ver la lista completa de flags disponibles.

#### Nodos source/target recomendados por planta

**Basement** (283 nodos, entorno `management_building_basement`):

| Zona | Nodo | Posición (x,y) | Capacidad | Uso típico |
|------|------|-----------------|-----------|------------|
| Esquina inferior izquierda | `278` | (1.4, 3.4) | 8 | source |
| Zona central superior | `27` | (19.4, 13.4) | 8 | source |
| Zona central inferior | `111` | (19.4, 3.4) | 8 | source |
| Salida derecha | `5` | (25.9, 12.9) | 2 | target |
| Salida izquierda | `174` | (1.4, 13.4) | 8 | target |

**floor_0** (212 nodos, entorno `management_building_floor_0`):

| Zona | Nodo | Posición (x,y) | Capacidad | Uso típico |
|------|------|-----------------|-----------|------------|
| Gran sala derecha | `39` | (50.4, 14.0) | 32 | source grande |
| Corredor superior | `129` | (15.4, 17.0) | 7 | source medio |
| Salida A | `107` | (33.4, 1.0) | 8 | target |
| Salida B | `27` | (62.9, 10.5) | 2 | target |
| Salida C | `108` | (31.4, 20.9) | 7 | target |
| Salida D | `204` | (7.4, 9.0) | 7 | target |

**floor_1** (501 nodos, entorno `management_building_floor_1`):

| Zona | Nodo | Posición (x,y) | Capacidad | Uso típico |
|------|------|-----------------|-----------|------------|
| Zona derecha | `21` | (58.0, 10.0) | 32 | source grande |
| Zona central | `139` | (43.0, 13.0) | 8 | source medio |
| Sala central | `122` | (50.0, 2.0) | 32 | source grande |
| Lado izquierdo | `498` | (10.0, 2.0) | 32 | source grande |
| Corredor izquierdo | `432` | (10.0, 10.0) | 32 | source grande |
| Salida principal | `224` | (36.4, 7.5) | 1 | target |

---

## Restricción importante: agentes vs. capacidad de nodo

Cada nodo tiene una capacidad máxima (`node_capacity`) basada en el área de la celda. Al configurar `agents`, el número de agentes para cada source **no puede superar su `node_capacity`**.

Para consultar la capacidad de un nodo:

```bash
.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, 'src')
from evac_sim.envs.environment_factory import select_environment
env = select_environment('management_building_basement')
node_id = '24'
cap = env.graph.nodes[node_id]['node_capacity']
area = env.specific_areas[node_id].area
print(f'node {node_id}: area={area:.2f}m², capacity={cap}')
"
```

Como regla práctica: `agents ≤ node_capacity * 0.7` asegura que JuPedSim pueda colocar todos los agentes sin errores.

---

## Flujo completo para la interfaz

```
1. Usuario configura parámetros:
   - Escenario (basement / floor_0 / floor_1) o escenario personalizado
   - Sources y nº de agentes por source
   - Targets
   - mode_type, gamma, velocidades, riesgo (semilla es opcional)

2. Interfaz construye el YAML mínimo con esos parámetros y lo guarda en un fichero temporal

3. Interfaz llama a validate_scenario_config --output <ruta_validated.yaml>:
   → Si INVALID: mostrar errores al usuario y detener
   → Si VALID:   el YAML normalizado (con semilla auto-asignada si faltaba) queda listo

4. Interfaz llama a run_scenario --config <ruta_validated.yaml>:
   → Espera hasta que termine (18–60 s típicamente)
   → Lee result.json del output-dir

5. Interfaz muestra:
   - summary.evacuation_time
   - summary.average_evacuation_time
   - summary.groups[] (métricas por grupo)
   - agents.csv (tabla de agentes)
   - Imágenes PNG de trayectorias y densidad
```

---

## Ejemplo completo de integración (Python)

```python
import subprocess
import json
import yaml
import tempfile
from pathlib import Path

PROJECT_ROOT = Path("C:/GitHub/Evacuation_Simulation")
EVAC_SIM = PROJECT_ROOT / ".venv/Scripts/evac-sim.exe"


def generate_and_validate(scenario_name: str, config: dict, validated_yaml_path: Path) -> tuple[bool, list[str]]:
    """
    Escribe el config mínimo en un YAML temporal, llama a "evac-sim validate"
    con --output para generar el YAML normalizado y devuelve (is_valid, warnings).
    """
    # Paso 1: escribir YAML mínimo
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump({scenario_name: config}, f, allow_unicode=True, sort_keys=False)
        tmp_path = f.name

    # Paso 2: validate + generate
    result = subprocess.run(
        [str(EVAC_SIM), "validate",
         "--config", tmp_path,
         "--scenario", scenario_name,
         "--output", str(validated_yaml_path)],
        cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    Path(tmp_path).unlink(missing_ok=True)

    is_valid = result.returncode == 0
    warnings = [
        line.strip().lstrip("- ")
        for line in result.stdout.splitlines()
        if line.strip().startswith("- ")
    ]
    return is_valid, warnings


def run_simulation(validated_yaml_path: Path, scenario_name: str, output_dir: str) -> dict:
    """Ejecuta la simulación desde el YAML generado y devuelve el result.json."""
    subprocess.run(
        [str(EVAC_SIM), "run",
         "--config", str(validated_yaml_path),
         "--scenario", scenario_name,
         "--output-dir", output_dir,
         "--output-format", "json,csv,html"],
        cwd=PROJECT_ROOT, check=True
    )
    result_path = Path(output_dir) / "result.json"
    with open(result_path, encoding="utf-8") as f:
        return json.load(f)


# --- Uso: escenario configurado desde la interfaz ---

scenario_name = "mi_escenario"
config = {
    "environment": "management_building_floor_0",
    "sources": ["1", "25"],
    "agents": [8, 4],
    "targets": ["11", "139", "17", "47"],
    "mode_type": 0,
    "gamma": 0.2,
    "stairs_max_speed": 0.6,
    "normal_max_speed": 1.2,
    "every_nth_frame_simulation": 3,
    "every_nth_frame_animation": 50,
    "danger_visualization_frame": 2500,
    "risk": {
        "enabled": True,
        "risk_iterations": 7000,
        "risk_increase_chance": 0.005,
        "risk_threshold": 0.5,
        "propagation_threshold": 0.5,
    },
    "distance_to_agents": 0.3,
    "distance_to_polygon": 0.1,
    # master_seed omitido: se genera automáticamente
}

validated_yaml = Path("configs/mi_escenario_validated.yaml")
is_valid, warnings = generate_and_validate(scenario_name, config, validated_yaml)

if not is_valid:
    print("Configuración inválida — revisar errores")
else:
    if warnings:
        print("Avisos:", warnings)
    data = run_simulation(validated_yaml, scenario_name, "results/api/mi_escenario")
    print(f"Status:        {data['status']}")
    print(f"Evacuados:     {data['summary']['evacuated_agents']}")
    print(f"Tiempo total:  {data['summary']['evacuation_time']} s")
    print(f"Tiempo medio:  {data['summary']['average_evacuation_time']} s")
    print(f"Semilla usada: {data['config']['master_seed']}")
```
