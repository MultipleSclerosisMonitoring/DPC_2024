.. _find_activityall:

find_activityall
================

Utilidad para extraer IDs de la tabla ``activity_all`` que 
intersectan una ventana de tiempo y, opcionalmente, filtrar
por patrón de CodeID.

**Ubicación:** ``ms_monitoring/find_activityall.py``

Parámetros
----------

- ``-f, --from``  
  Fecha/hora inicio (YYYY-MM-DD HH:MM:SS).  
- ``-u, --until``  
  Fecha/hora fin (YYYY-MM-DD HH:MM:SS).  
- ``-c, --config``  
  Ruta al YAML de configuración.  
- ``-p, --pattern``  
  Regex para filtrar CodeIDs (opcional).  
- ``-q, --quiet``  
  Sólo devuelve JSON con la lista de IDs.  
- ``-v, --verbose``  
  Nivel de verbosidad (0–2).  
- ``-l, --lang``  
  Idioma (``es``, ``en``, …).

Ejemplos
--------

Extracción **sin filtro**, modo detallado::

  $ python -m ms_monitoring.find_activityall \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-30 23:59:59" \
      -c config.yaml

Extracción **silenciosa** con **filtro regex**::

  $ python -m ms_monitoring.find_activityall \
      -f "2024-06-01 00:00:00" \
      -u "2024-06-30 23:59:59" \
      -c config.yaml \
      -p "^WALK" \
      -q

