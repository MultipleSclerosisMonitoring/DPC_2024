# Tools

Esta carpeta contiene módulos que pueden ser utilizados en diferentes partes del proyecto.

### Módulos:

- **data_manager.py**: Proporciona la conexión y gestión de datos tanto con InfluxDB como con PostgreSQL.
- **movement_detector.py**: Se encarga de procesar los datos de movimiento asociados a los `CodeIDs` y filtrar los movimientos efectivos.
- **trajectory_analyzer.py**: Proporciona funcionalidad para analizar trayectorias basadas en los datos de movimiento.
- **gait_classifier.py**: Clasifica los patrones de marcha basados en los datos obtenidos.

### Ejemplo de uso:

```python
from Tools.data_manager import DataManager
from Tools.movement_detector import MovementDetector

# Inicializa el DataManager con la configuración
data_manager = DataManager('config.yaml')

# Crea una instancia de MovementDetector
movement_detector = MovementDetector(data_manager)

# Detectar movimientos efectivos
codeids = ['CODEID123', 'CODEID456']
movements = movement_detector.detect_effective_movement(codeids)
