# CodeID

Esta carpeta contiene el módulo encargado de identificar y procesar los `CodeIDs`.

### Módulos:

- **codeid_processor.py**: Proporciona funcionalidades para identificar `CodeIDs` y obtener sus datos asociados desde InfluxDB.

### Ejemplo de uso:

```python
from CodeID.codeid_processor import CodeIDProcessor
from Tools.data_manager import DataManager

# Inicializa el DataManager con la configuración
data_manager = DataManager('config.yaml')

# Crea una instancia de CodeIDProcessor
codeid_processor = CodeIDProcessor(data_manager)

# Identificar nuevos CodeIDs en un rango de fechas
new_codeids = codeid_processor.identify_new_codeids('2024-06-29 10:00:00', '2024-06-29 13:59:59')

