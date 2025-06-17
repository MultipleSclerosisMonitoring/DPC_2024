# msCodeID

msCodeID es un módulo en Python dedicado al procesamiento de identificadores de dispositivo (*CodeIDs*) obtenidos de wearables. Proporciona funcionalidades para:

- **Extracción** de datos de sensores desde InfluxDB.
- **Identificación** de segmentos de actividad basados en umbrales de tiempo.
- **Preparación** de datos para su almacenamiento en PostgreSQL.

## Requisitos

- Python **3.12+**
- Dependencias instaladas en el proyecto principal:
  - `influxdb-client>=1.35.0`
  - `pandas>=2.0.0`
  - `pydantic`
  - `PyYAML`

## Instalación

El módulo se instala como parte del paquete principal **ms_monitoring**:

```bash
# Desde el repositorio raíz o tras publicar en PyPI
pip install ms_monitoring
```

## Configuración

La conexión a InfluxDB se gestiona a través de `config.yaml`. Asegúrate de definir la sección `influxdb` con los siguientes parámetros:

```yaml
influxdb:
  org: 'UPM'
  bucket: 'Gait/autogen'
  measurement: 'Gait'
  url: "https://apiivm78.etsii.upm.es:8086"
  token: '<TU_TOKEN>'
  verify: false
  timeout: 900000
```

## Uso en Python

Puedes usar directamente la clase `CodeIDProcessor` desde tu código:

```python
from msTools.data_manager import DataManager
from msCodeID.codeid_processor import CodeIDProcessor

# Inicializar el gestor de datos
dm = DataManager(config_path="config.yaml")
processor = CodeIDProcessor(dm)

# Recuperar datos de un CodeID en un rango de fechas
df = processor.fetch_codeid_data(
    codeid="DEVICE123",
    start_datetime="2024-01-01 00:00:00",
    end_datetime="2024-01-02 00:00:00"
)

print(df.head())
```

## Uso en línea de comandos

Aunque **msCodeID** no expone un CLI directo, se integra con el script principal `find_mscodeids` del paquete:

```bash
python -m ms_monitoring.find_mscodeids   -c config.yaml   -f "2024-01-01 00:00:00"   -u "2024-01-02 00:00:00"   -v 1
```

Este comando:
1. Extrae los `CodeID` únicos en el rango especificado.
2. Identifica y almacena ventanas de actividad en PostgreSQL.

## Estructura de ficheros

- `codeid_processor.py`: Clase principal `CodeIDProcessor`.
- `__init__.py`

## Contribuciones

Las contribuciones son bienvenidas. Para proponer cambios:
1. Haz un **fork** del repositorio.
2. Crea una rama: `git checkout -b feature/mi-mejora`.
3. Realiza tus cambios y envía un **pull request**.

## Licencia

Proyecto bajo licencia **MIT**. Consulta el archivo `LICENSE` en la raíz del repositorio.
