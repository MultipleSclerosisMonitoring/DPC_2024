msGait package
==============

The ``msGait`` package implements the movement and gait detection stage of the
repository.

Its role is to retrieve raw inertial and GPS data for previously identified
semantic windows, detect effective movement at leg level, derive bilateral gait
episodes, and enrich those gait intervals with GPS-based metrics before
optional storage in PostgreSQL.

Responsibilities
----------------

The package centers on the ``MovementDetector`` class, which is responsible for:

- retrieving bilateral candidate windows from ``activity_all``
- expanding those windows into one row per leg
- fetching raw inertial data from InfluxDB for each leg
- resampling inertial signals to a fixed temporal grid
- computing acceleration and gyroscope magnitudes
- detecting ``effective_movement`` using spectral and temporal criteria
- deriving bilateral ``effective_gait`` from left/right overlap
- enriching gait intervals with GPS-derived metrics
- storing ``effective_movement`` and ``effective_gait`` in PostgreSQL

Core component
--------------

``MovementDetector`` (``movement_detector.py``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main public methods include:

- ``__init__(config_file: str, sampling_rate: float | None = None, sect: str = "movement", fstart: str | None = None, fend: str | None = None, ids: list[int] | None = None, verbose: int = 1) -> None``
- ``fetch_sensor_data(start_time: str, end_time: str, codeid_id: int, foot: str) -> pandas.DataFrame``
- ``fetch_gps_data(start_time: str, end_time: str, codeid_id: int) -> pandas.DataFrame``
- ``resample_sensor_data(df: pandas.DataFrame, target_hz: float) -> pandas.DataFrame``
- ``calculate_magnitude(df: pandas.DataFrame) -> pandas.DataFrame``
- ``is_effective_by_welch(signal: numpy.ndarray, power_threshold: float, sampling_rate: float) -> bool``
- ``is_effective_by_time(signal: numpy.ndarray, threshold: float) -> bool``
- ``detect_effective_movement(activity_windows: pandas.DataFrame, output_filename: str | None = None, verbose: int = 0) -> pandas.DataFrame``
- ``detect_effective_gait(df_effective: pandas.DataFrame, verbose: int = 0) -> pandas.DataFrame``
- ``validate_gait_with_gps(df_gait: pandas.DataFrame, verbose: int = 0) -> pandas.DataFrame``
- ``save_to_postgresql(table_name: str, df: pandas.DataFrame, verbose: int = 0) -> None``
- ``close() -> None``

Detection pipeline
------------------

The current gait-detection flow is:

1. Read previously built bilateral activity windows from ``activity_all``.
2. Expand each bilateral window into leg-specific rows using ``recover_activity_all``.
3. Fetch raw inertial signals (``Ax``, ``Ay``, ``Az``, ``Gx``, ``Gy``, ``Gz``) from InfluxDB.
4. Resample each segment to a fixed frequency (``resample_hz``) to reduce timing irregularities and packet-loss effects before spectral analysis.
5. Compute acceleration and gyroscope magnitudes.
6. Split the resampled signal into fixed-size analysis windows.
7. Detect ``effective_movement`` using:

   - Welch band-power criteria
   - temporal continuity/activity criteria

8. Merge temporally adjacent valid windows and filter by minimum duration.
9. Derive ``effective_gait`` from the temporal overlap between left and right ``effective_movement`` periods.
10. Enrich gait rows with GPS-derived metrics:

   - ``gps_points``
   - ``gps_distance_m``
   - ``gps_elapsed_sec``
   - ``gps_avg_speed_m_s``
   - ``gps_validated``

How it fits into the repository workflow
----------------------------------------

The repository is divided into two main stages.

Stage 1: semantic construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handled by ``msCodeID`` and ``find_mscodeids``.

This first stage builds:

- ``codeids``
- ``activity_leg``
- ``activity_all``

Stage 2: movement and gait detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handled by ``msGait`` and ``find_gait``.

This second stage consumes ``activity_all`` and produces:

- ``effective_movement``
- ``effective_gait``
- GPS-enriched gait metrics

Configuration
-------------

``msGait`` reads its parameters from the ``movement`` section of ``config.yaml``. Connection values can be overridden through ``.env`` using the keys documented in ``.env.example``.

Example:

.. code-block:: yaml

   movement:
     accel_threshold:            0.2
     gyro_threshold:             60
     accel_power_threshold:      0.125
     gyro_power_threshold:       1000
     freq_band_min:              0.4
     freq_band_max:              1.6
     min_continuous_hits:        3
     sampling_rate:              47.0
     resample_hz:                100.0
     window_size_samples:        256
     min_window_fraction:        0.5
     min_effective_duration_sec: 6.0
     min_gait_duration_sec:      6.0
     gps_resample_seconds:       10
     gps_padding_seconds:        15
     gps_min_points:             2
     gps_min_distance_m:         3.0
     gps_min_speed_m_s:          0.2
     gps_max_speed_m_s:          3.0

Parameter notes
~~~~~~~~~~~~~~~

- ``sampling_rate`` is the nominal acquisition-rate reference.
- ``resample_hz`` is the fixed interpolation/alignment frequency used before segment windowing and Welch analysis.
- ``window_size_samples`` controls the analysis-window length in samples.
- ``min_window_fraction`` allows preserving the last partial segment when large enough.
- ``min_effective_duration_sec`` filters short leg-specific detections.
- ``min_gait_duration_sec`` filters short bilateral overlaps.
- ``gps_resample_seconds`` controls the temporal step used when GPS points are regularized.
- ``gps_padding_seconds`` expands the gait interval slightly when querying GPS.
- ``gps_min_points``, ``gps_min_distance_m``, ``gps_min_speed_m_s``, and ``gps_max_speed_m_s`` define the GPS plausibility rules used to set ``gps_validated``.

Python usage
------------

.. code-block:: python

   from msGait.movement_detector import MovementDetector

   detector = MovementDetector(
       config_file="config.yaml",
       ids=[152],
       verbose=1,
   )

   df_effective = detector.detect_effective_movement(
       activity_windows=detector.df_legs,
       output_filename=None,
       verbose=1,
   )

   df_gait = detector.detect_effective_gait(df_effective, verbose=1)
   df_gait = detector.validate_gait_with_gps(df_gait, verbose=1)

   detector.save_to_postgresql("effective_movement", df_effective, verbose=1)
   detector.save_to_postgresql("effective_gait", df_gait, verbose=1)

   detector.close()

Command-line usage
------------------

From the project root:

.. code-block:: bash

   # Process explicit activity_all IDs
   python -m ms_monitoring.find_gait \
     -c config.yaml \
     -i 152,153 \
     --save 1 \
     -v 2

   # Or process the last N hours if --ids is omitted
   python -m ms_monitoring.find_gait \
     -c config.yaml \
     --hours-back 48 \
     --save 0 \
     -v 1

Main CLI options
~~~~~~~~~~~~~~~~

- ``-c, --config``: YAML configuration path
- ``-i, --ids``: range/list of ``activity_all`` IDs such as ``1-10`` or ``1,5,10-15``
- ``--hours-back``: fallback time window when ``--ids`` is omitted
- ``-o, --output``: optional XLSX export of raw inertial windows
- ``--save``: persist results into PostgreSQL (``0`` or ``1``)
- ``-v, --verbose``: verbosity level

Stored outputs
--------------

``effective_movement``
~~~~~~~~~~~~~~~~~~~~~~

Per-leg movement detections with:

- ``codeid_id``
- ``start_time``
- ``end_time``
- ``duration``
- ``leg``

``effective_gait``
~~~~~~~~~~~~~~~~~~

Bilateral gait detections with:

- ``codeid_id``
- ``start_time``
- ``end_time``
- ``duration``
- ``gps_points``
- ``gps_distance_m``
- ``gps_elapsed_sec``
- ``gps_avg_speed_m_s``
- ``gps_validated``

Notes
-----

- inertial analysis is performed on resampled data
- the final partial analysis window may be kept when large enough
- GPS enrichment is part of the final pipeline before storing ``effective_gait``
- this package depends on ``msTools`` for shared infrastructure and database access

API reference
-------------

.. automodule:: msGait.movement_detector
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: msGait.models
   :members:
   :undoc-members:
   :show-inheritance: