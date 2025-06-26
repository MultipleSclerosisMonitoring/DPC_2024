# MS Monitoring

TFG Diego Parrilla Calderón

**MS Monitoring** (`ms_monitoring`) es una colección modular de utilidades en Python para la monitorización de dispositivos wearables (Sensoria, HealthyWear) en estudios de esclerosis múltiple. El proyecto está organizado en cuatro componentes principales (un repositorio y tres paquetes de python):

- **ms_monitoring**: Scripts CLI para flujo completo de análisis 
      (extracción de CodeIDs, segmentos de actividad, detección de marchas efectivas).
- **msTools**: *(Paquete python)* Biblioteca de utilidades compartidas 
      (gestión de base de datos, I18N, modelos de datos, utilidades de tiempo).
- **msCodeID**: *(Paquete python)* Procesamiento de CodeIDs: extracción de datos de InfluxDB y almacenamiento en PostgreSQL de segmentos de actividad.
- **msGait**: *(Paquete python)* Procesamiento de señal de marcha: detección de segmentos, clasificación y análisis de marchas efectivas.

---

## Estructura de directorios

```
root
├── .gitignore
├── config.yaml               # Template configuración de InfluxDB y PostgreSQL
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

Edite `.config.yaml` con los datos de sus servidores. Dispone de un template en `config.yaml` :

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
  # Umbral para el módulo de aceleración (is_effective_by_time)
  accel_threshold: 0.2
  # Umbral para el módulo de giroscopio (is_effective_by_time)
  gyro_threshold: 0.2
  # Threshold de potencia en la banda de frecuencia
  power_threshold: 0.5
  # Banda de frecuencia para Welch (Hz)
  freq_band_min: 0.4
  freq_band_max: 1.4
  # Segundos mínimos continuos sobre el umbral para considerar actividad
  min_continuous_seconds: 10
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
