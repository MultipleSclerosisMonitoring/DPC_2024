# MS Monitoring

TFG Diego Parrilla Calderón

**MS Monitoring** (`ms_monitoring`) es una colección modular de utilidades en Python para la monitorización de dispositivos wearables (Sensoria, HealthyWear) en estudios de esclerosis múltiple. El proyecto está organizado en cuatro componentes principales:

- **ms_monitoring**: Scripts CLI para flujo completo de análisis (extracción de CodeIDs, segmentos de actividad, detección de marchas efectivas).
- **msTools**: Biblioteca de utilidades compartidas (gestión de base de datos, I18N, modelos de datos, utilidades de tiempo).
- **msCodeID**: Procesamiento de CodeIDs: extracción de datos de InfluxDB y almacenamiento en PostgreSQL de segmentos de actividad.
- **msGait**: Procesamiento de señal de marcha: detección de segmentos, clasificación y análisis de marchas efectivas.

---

## Estructura de directorios

```
C:.
├── .gitignore
├── config.yaml               # Configuración de InfluxDB y PostgreSQL
├── ids.json
├── LICENSE
├── pyproject.toml            # configuración Poetry
├── poetry.lock
├── pyproject.txt             # configuración PEP 621
├── README.md                 # este archivo
├── requirements.txt
├── docs/                     # Documentación Sphinx
├── locales/                  # Archivos de traducción (es/en)
├── msTools/                  # Utilidades compartidas
├── msCodeID/                 # Procesador de CodeIDs
├── msGait/                   # Análisis de señal de marcha
├── ms_monitoring/            # Scripts CLI
└── outs/
```

---

## Requisitos

- Python 3.12+  
- **Poetry** (recomendado) o `pip`  
- Dependencias listadas en `pyproject.toml` 

---

## Instalación

### Con Poetry

```bash
# Instalar Poetry si no lo tienes
curl -sSL https://install.python-poetry.org | python3 -

# Clonar repositorio
git clone https://github.com/MultipleSclerosisMonitoring/DPC_2024.git
cd DPC_2024

# Instalar dependencias y activar entorno
poetry install
poetry shell

# Generar artefactos y construir paquete
poetry build
pip install dist/ms_monitoring-0.1.0-py3-none-any.whl
```

### Con pip

```bash
# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate  # o venv\Scripts\activate en Windows

# Instalar dependencias
pip install -r requirements.txt

# (Opcional) Construir wheel
pip wheel . --no-deps -w dist
pip install dist/ms_monitoring-0.1.0-py3-none-any.whl
```

---

## Configuración

Edite `config.yaml` con los datos de sus servidores:

```yaml
influxdb:
  url: "https://<host>:8086"
  token: "<TOKEN>"
  org: "<ORGANIZATION>"
  bucket: "<BUCKET>"
  measurement: "<MEASUREMENT>"
  verify: false
  timeout: 900000

postgresql:
  host: "<PG_HOST>"
  port: 5432
  user: "<USER>"
  password: "<PASSWORD>"
  database: "<DB_NAME>"

movement:
  freq_band_min: 0.5
  freq_band_max: 2.0
  power_threshold: 0.5
  min_continuous_seconds: 10
```

---

## Uso de los scripts CLI

Tras la instalación, puede usar los siguientes módulos:

### 1. `find_mscodeids`

Extrae CodeIDs únicos de InfluxDB y almacena segmentos de actividad en PostgreSQL.

```bash
python -m ms_monitoring.find_mscodeids   -c config.yaml   [-f "2024-01-01 00:00:00" -u "2024-12-31 23:59:59"]   [-v 1]
```

Opciones:
- `-f, --from`: fecha inicio (YYYY-MM-DD HH:MM:SS).  
- `-u, --until`: fecha fin.  
- `-c, --config`: ruta a `config.yaml`.  
- `-v, --verbose`: nivel de verbosidad.

### 2. `find_activityall`

Busca IDs de `activity_all` que intersectan una ventana temporal y opcionalmente filtra por patrón de CodeID.

```bash
python -m ms_monitoring.find_activityall   -c config.yaml   -f "2024-06-01 00:00:00"   -u "2024-06-30 23:59:59"   [-p "^PATTERN"]   [-q]   [-v 1]
```

- `-p, --pattern`: regex para filtrar CodeIDs.  
- `-q, --quiet`: salida JSON solo de IDs.

### 3. `find_activity`

Detecta y almacena marchas efectivas usando los IDs de `activity_all` o una ventana temporal.

```bash
# Por IDs
python -m ms_monitoring.find_activity   -c config.yaml   -i "[12,34,56]"   [-v 2]

# Por ventana
python -m ms_monitoring.find_activity   -c config.yaml   -f "2024-01-01 00:00:00"   -u "2024-12-31 23:59:59"   [-v 1]
```

---

## Documentación

La documentación completa está en `docs/`. Para generarla:

```bash
cd docs
make html
```

Luego abra `_build/html/index.html`.

---

## Desarrollo y Contribuciones

1. Fork del repositorio.  
2. Crear branch: `git checkout -b feature/nombre`.  
3. Realizar cambios y tests.  
4. Crear pull request.

---

## Licencia

Este proyecto usa la licencia [MIT](LICENSE).  
