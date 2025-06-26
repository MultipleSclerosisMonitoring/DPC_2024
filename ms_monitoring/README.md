# ms_monitoring

Scripts de línea de comandos para extracción y procesamiento de datos de actividad.

## Flujo de procesamiento (paso a paso)

1. **Extracción de CodeIDs y ventanas de actividad**  
  Ejecuta `find_mscodeids` para extraer identificadores de dispositivo y generar tablas 
  `activity_leg` y `activity_all` en PostgreSQL.  

  ```bash
  python -m ms_monitoring.find_mscodeids \
    -f "YYYY-MM-DD HH:MM:SS" \
    -u "YYYY-MM-DD HH:MM:SS" \
    -c config.yaml \
    -v 2
  ```

2. **Detección de marchas efectivas**  
  Ejecuta `find_gait` para analizar los segmentos de `activity_all`,  
  generar `effective_movement` y `effective_gait` y guardarlos (opcional).  

  ```bash
  python -m ms_monitoring.find_gait \
    -i "[ID1,ID2,...]" \
    -c config.yaml \
    -l es \
    --head-rows 8 \
    --output salida.xlsx \
    --save \
    -v 2
  ```

## Esquema de tablas relevantes

Además de las tablas habituales (`codeids`, `activity_all`, `activity_leg`, `effective_movement`), se ha añadido:

```sql
CREATE TABLE IF NOT EXISTS effective_gait (
  id SERIAL PRIMARY KEY,
  codeid_id INT REFERENCES codeids(id),
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  end_time   TIMESTAMP WITH TIME ZONE NOT NULL,
  duration   NUMERIC NOT NULL
);
CREATE INDEX idx_effective_gait_codeid ON effective_gait(codeid_id);
```

## Requisitos

- Python 3.12+
- `config.yaml` en el directorio raíz con las conexiones a InfluxDB y PostgreSQL.

## Uso

### find_mscodeids

```bash
python -m ms_monitoring.find_mscodeids \
  -c config.yaml \
  [-f "YYYY-MM-DD HH:MM:SS"] \
  [-u "YYYY-MM-DD HH:MM:SS"] \
  [-v 1]
```

- `-c, --config`: Ruta al fichero de configuración YAML.
- `-f, --from`: Fecha y hora de inicio (por defecto: ayer a medianoche).
- `-u, --until`: Fecha y hora de fin (por defecto: ahora).
- `-v, --verbose`: Nivel de verbosidad.

### find_gait

```bash
python -m ms_monitoring.find_gait \
  -c config.yaml \
  -i "[ID1,ID2,...]" \
  -l es \
  [--output salida.xlsx] \
  [--head-rows N] \
  [--save] \
  [-v N]

```

- `-c, --config`: Ruta al fichero de configuración YAML.
- `-i, --ids`: Lista JSON de IDs de `activity_all`.
- `-l, --lang`: Idioma de la interfaz (es por defecto).
- `--output`: Fichero Excel de salida (para datos RAW de sensores).
- `--head-rows`: Filas a mostrar con `-v >=2` (por defecto: 5).
- `--save`: Si se especifica, guarda también los resultados en la tabla `effective_gait`.
- `-v, --verbose`: Nivel de verbosidad.

## Licencia

MIT. Véase `LICENSE`.
