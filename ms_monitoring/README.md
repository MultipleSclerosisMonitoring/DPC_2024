# ms_monitoring

Scripts de línea de comandos para extracción y procesamiento de datos de actividad.

Este directorio contiene dos utilidades principales:

- **find_mscodeids**: Extrae CodeIDs de InfluxDB y registra ventanas de actividad en PostgreSQL.
- **find_activity**: Detecta marchas efectivas a partir de IDs de ventanas de actividad o una ventana temporal.

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

### find_activity

```bash
python -m ms_monitoring.find_activity \
  -c config.yaml \
  [-i "[ID1,ID2,...]" | -f "YYYY-MM-DD HH:MM:SS" -u "YYYY-MM-DD HH:MM:SS"] \
  [--output salida.xlsx] \
  [--head-rows N] \
  [--save] \
  [-v N]
```

- `-i, --ids`: Lista JSON de IDs de `activity_all`.
- `-f, --from`, `-u, --until`: Rango de tiempo alternativo a `-i`.
- `--output`: Fichero Excel de salida (para datos RAW de sensores).
- `--head-rows`: Filas a mostrar con `-v >=2` (por defecto: 5).
- `--save`: Si se especifica, guarda también los resultados en la tabla `effective_gait`.
- `-v, --verbose`: Nivel de verbosidad.

## Ejemplo con `leeme.txt`

```bash
while read session; do
  desde=$(echo "$session" | sed -n "s/.*'desde':'\([^']*\)'.*/\1/p")
  hasta=$(echo "$session" | sed -n "s/.*'hasta':'\([^']*\)'.*/\1/p")
  name=$(echo "$session" | sed -n "s/.*'name':'\([^']*\)'.*/\1/p")
  python -m ms_monitoring.find_activity \
    -c config.yaml \
    -f "$desde" -u "$hasta" \
    --save \
    -v 1
done < leeme.txt
```

## Licencia

MIT. Véase `LICENSE`.
