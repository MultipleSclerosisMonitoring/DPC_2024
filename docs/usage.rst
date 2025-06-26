Start
-----

Una vez instalado como paquete, los scripts se ejecutan con `-m`:

.. code-block:: console

    # Encontrar y almacenar msCodeIDs (por rango de fechas opcional)
    (.yourvenv) $ python -m ms_monitoring.find_mscodeids \
        -c config.yaml \
        [-f "2024-01-01 00:00:00" -u "2024-12-31 23:59:59"] \
        [-v 1]

    # Detectar marchas efectivas (por IDs o ventana temporal)
    (.yourvenv) $ python -m ms_monitoring.find_gait \
        -c config.yaml \
        -i "[12,34,56]" \
        [-v 2]