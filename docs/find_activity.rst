.. _find_activity:

find_activity
=============

Utilidad para detectar y almacenar marchas efectivas a partir de segmentos
de la tabla ``activity_all``.

**Ubicación:** ``ms_monitoring/find_activity.py``

Parámetros
----------

Al menos uno de estos dos grupos de argumentos debe proporcionarse:

- **IDs concretos**  
  - ``-i, --ids``  
    Lista JSON de ``activity_all`` IDs. Ej: ``"[12,34,56]"``  

- **Ventana temporal**  
  - ``-f, --from``  
    Fecha/hora inicio (YYYY-MM-DD HH:MM:SS).  
  - ``-u, --until``  
    Fecha/hora fin   (YYYY-MM-DD HH:MM:SS).  

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

  $ python -m ms_monitoring.find_activity \
      -i "[12,34,56]" \
      -c config.yaml

Llamada por **ventana temporal**::

  $ python -m ms_monitoring.find_activity \
      -f "2024-01-01 00:00:00" \
      -u "2024-12-31 23:59:59" \
      -c config.yaml \
      -v 1

Ejemplo con verbosidad detallada y mostrando solo 3 filas de salida::

  $ python -m ms_monitoring.find_activity \
      -i "[12,34,56]" \
      -c config.yaml \
      -v 2 \
      --head-rows 3
