Usage
=====

.. _installation:

Installation
------------

To use MS_Activity_Movement, first install it from github:

.. code-block:: console

    git clone https://github.com/MultipleSclerosisMonitoring/DPC_2024
    # Activate your python virtual environment
    . path/to/your/own/venv/bin/activate
    (.yourvenv) $ pip install -r requirements.txt
    (.yourvenv) $ pip wheel . --no-index --disable-pip-version-check --no-deps --wheel-dir dist --no-build-isolation
    (.yourvenv) $ pip install dist/*.wh

.. _start:

Start
-----

.. code-block:: console

    (.yourvenv) $ python find_mscodeids.py [-f "datetime"  -u "datetime"]
