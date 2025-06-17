# msTools

**Módulo de utilidades compartidas** para MS Monitoring: gestión de configuración YAML, interacción con InfluxDB y PostgreSQL, modelos de datos, internacionalización e utilidades de tiempo.

## Estructura del paquete

- `msTools/data_manager.py`  
  Clase `DataManager` para cargar configuración, conectarse a InfluxDB y PostgreSQL, ejecutar consultas y almacenar datos.

- `msTools/models.py`  
  Modelos Pydantic (`CodeID`, `ActivityLeg`, `ActivityAll`) para validar y tipar los datos antes de persistirlos.

- `msTools/timeutils.py`  
  Función `ensure_utc(ts)` convierte fechas/strings a `pd.Timestamp` en UTC, asumiendo “Europe/Madrid” si vienen naïve.

- `msTools/i18n.py`  
  Inicialización y helper `_()` para traducción de mensajes.

## Instalación

Forma parte del paquete principal **ms_monitoring**. Tras clonar o instalar vía `pip` o `poetry`:

```bash
# Con Poetry
poetry install

# Con pip
pip install ms_monitoring
```

## Uso

### 1. DataManager

Crea instancias de `DataManager` en tu script o REPL:

```python
from msTools.data_manager import DataManager

# Inicializar con tu YAML de configuración
dm = DataManager(config_path='config.yaml')

# Crear/verificar tablas en PostgreSQL
dm.check_and_create_tables('msTools/create_tables.sql')

# Ejecutar una consulta SQL y obtener un DataFrame
df = dm.fetch_data('SELECT * FROM codeids;')
print(df.head())
```

### 2. timeutils.ensure_utc

Normaliza timestamps a UTC:

```python
from msTools.timeutils import ensure_utc

ts_utc = ensure_utc('2024-06-15 12:00:00')
print(ts_utc)  # 2024-06-15 10:00:00+00:00 (asume Europe/Madrid)
```

### 3. Internacionalización (i18n)

Carga traducciones antes de imprimir mensajes:

```python
from msTools import i18n

# Inicializar en inglés
i18n.init_translation('en')

# Usar helper _
print(i18n._("PGSQL-CONN-ERR").format(e="timeout"))
```

### 4. Modelos Pydantic

Define y valida datos de ejemplo:

```python
from msTools.models import ActivityLeg

leg = ActivityLeg(
    codeid_id=1,
    foot='Left',
    start_time='2024-06-15T10:00:00Z',
    end_time='2024-06-15T10:01:00Z',
    duration=60.0,
    total_value=100.0
)
print(leg.json())
```

## Ejecución rápida vía CLI

Aunque msTools no expone un script propio, puedes usarlo en un one‑liner con `python -c`:

```bash
python - << 'EOF'
from msTools.data_manager import DataManager
dm = DataManager('config.yaml')
print(dm.fetch_data('SELECT COUNT(*) FROM codeids;'))
EOF
```

## Contribuciones

1. Haz fork y rama `feature/…`  
2. Añade tests y actualiza `README.md` si procede  
3. Envía pull request

## Licencia

MIT — véase [LICENSE](../LICENSE)
