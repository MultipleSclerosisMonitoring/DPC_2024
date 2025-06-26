.. _find_gait:

find_gait
=============

Utilidad para detectar y almacenar marchas efectivas a partir de segmentos
de la tabla ``activity_all``.

**Ubicación:** ``ms_monitoring/find_gait.py``

Parámetros
----------

- **IDs concretos**  
  - ``-i, --ids``  
    Lista JSON de ``activity_all`` IDs. Ej: ``"[12,34,56]"``  

Además, estos parámetros opcionales:

- ``-c, --config``  
  Ruta al fichero YAML de configuración.  
- ``-l, --lang``  
  Idioma de la interfaz (``es``, ``en``, …).  
- ``-o, --output``  
  Ruta para salida XLSX (opcional).  
- ``-v, --verbose``  
  Nivel de verbosidad (0: ninguno, 1: básico, 2: detallado).  
- ``--head-rows``  
  Número de filas a mostrar en el nivel de verbosidad 2 (por defecto: 5).  

Ejemplos
--------

Llamada por **IDs** concretos::

  $ python -m ms_monitoring.find_gait \
      -i "[12,34,56]" \
      -c config.yaml \
      -l es \
      --save \
      -v 2

Ejemplo con verbosidad detallada y mostrando solo 3 filas de salida::

  $ python -m ms_monitoring.find_gait \
      -i "[12,34,56]" \
      -c config.yaml \
      -v 2 \
      --head-rows 3
