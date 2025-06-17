import pandas as pd

def ensure_utc(ts):
    """
    Toma un datetime/string/Timestamp y devuelve un pd.Timestamp con tz=UTC.

    - Si viene sin zona horaria (“naïve”), **asume Europe/Madrid** antes de convertir.
    - Si ya viene con cualquier tz, simplemente lo convierte a UTC.

    :param ts: datetime, pd.Timestamp o str en formato ISO o similar.
    :return: pd.Timestamp con tzinfo UTC.
    """
    ts = pd.to_datetime(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("Europe/Madrid")
    return ts.tz_convert("UTC")
