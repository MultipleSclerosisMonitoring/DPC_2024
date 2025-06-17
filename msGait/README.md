# msGait

Procesamiento de señal de marcha: detección, clasificación y análisis.

## Descripción

El paquete `msGait` forma parte de la suite **MS Monitoring**. Proporciona funcionalidades para:
- Identificar segmentos de actividad de marcha sincronizados (pie izquierdo + pie derecho).
- Calcular magnitudes y espectros de señal (aceleración, giroscopio).
- Detectar marchas efectivas usando criterios de potencia espectral y duración mínima.

## Instalación

`msGait` se distribuye dentro del paquete `ms_monitoring`. Instálalo con:

```bash
pip install ms_monitoring
```

## Configuración

Define la sección `movement` en tu `config.yaml` (parte relevante):

```yaml
movement:
  freq_band_min: 0.5           # Banda de frecuencia mínima (Hz)
  freq_band_max: 2.0           # Banda de frecuencia máxima (Hz)
  power_threshold: 0.5         # Potencia mínima en la banda
  min_continuous_seconds: 10   # Duración mínima continua (segundos)
```

## Uso en Python

```python
from msTools.data_manager import DataManager
from msGait.movement_detector import MovementDetector

# Carga configuración y conecta a bases de datos
dm = DataManager(config_path='config.yaml')

# Recupera ventanas de actividad desde activity_all
query = "SELECT id, start_time, end_time, duration, codeid_ids, codeleg_ids, active_legs FROM activity_all;"
df_windows = dm.fetch_data(query)

# Inicializa el detector de movimiento
detector = MovementDetector(
    data_manager=dm,
    sampling_rate=50,    # frecuencia de muestreo en Hz
    sect='movement',     # sección en config.yaml
    verbose=1            # nivel de verbosidad
)

# Detectar marchas efectivas
df_effective = detector.detect_effective_movement(
    activity_windows=df_windows,
    nomf='output.xlsx',  # opcional: exportar datos brutos a Excel
    vb=2                  # nivel detallado
)

# Guardar resultados en PostgreSQL
detector.save_to_postgresql('effective_movement', df_effective)
```

## Línea de comandos

Aunque `msGait` se usa desde código, también puedes invocar la utilidad completa con el script CLI:

```bash
python -m ms_monitoring.find_activity   -c config.yaml   -f "2024-01-01 00:00:00"   -u "2024-01-02 00:00:00"   -v 2   --head-rows 5   -o output.xlsx
```

## Estructura del paquete

```
msGait/
├── __init__.py
├── movement_detector.py
└── models.py
```

## Documentación

La documentación detallada de cada módulo está en `docs/msGait.rst`. Para generarla:

```bash
cd docs
make html
```

## Contribuir

1. Haz un fork del repositorio.
2. Crea una rama: `git checkout -b feature/mi-mejora`.
3. Realiza tus cambios y comités.
4. Envía un pull request.

## Licencia

MIT License. Véase el archivo `LICENSE` en la raíz del proyecto.
