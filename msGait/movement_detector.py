import pandas as pd
import numpy as np
from pandas import ExcelWriter
from concurrent.futures import ThreadPoolExecutor
from msTools.data_manager import DataManager
from msTools import i18n
from scipy.signal import welch
from msGait.models import EffectiveMovement
from pydantic import ValidationError


class MovementDetector:
    def __init__(self, data_manager : DataManager, sampling_rate: float,
                 sect: str, verbose: int = 1) -> None:
        self.data_manager = data_manager
        self.sampling_rate = sampling_rate
        params = data_manager.get_config(sect)
        frq_band = (params['freq_band_min'],params['freq_band_max'])
        pow_thrs = params['power_threshold']
        self.freq_band = frq_band
        self.power_threshold = pow_thrs
        self.min_continuous_seconds = params['min_continuous_seconds']
        self.verbose = verbose

    def fetch_sensor_data(self, start_time: str, end_time: str, \
                          codeid_id: int, foot: str) -> pd.DataFrame:
        try:
            codeid = self.data_manager.get_real_codeid(codeid_id)
        except ValueError as e:
            print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            return pd.DataFrame()

        # Asegurar timestamps en UTC
        start_time = pd.to_datetime(start_time)
        if start_time.tzinfo is None:
            start_time = start_time.tz_localize("Europe/Madrid")
        start_time = start_time.tz_convert("UTC").isoformat().replace("+00:00", "Z")

        end_time = pd.to_datetime(end_time)
        if end_time.tzinfo is None:
            end_time = end_time.tz_localize("Europe/Madrid")
        end_time = end_time.tz_convert("UTC").isoformat().replace("+00:00", "Z")

        query = f'''
        from(bucket: "{self.data_manager.bucket}")
            |> range(start: {start_time}, stop: {end_time})
            |> filter(fn: (r) => r["CodeID"] == "{codeid}" and r["Foot"] == "{foot}")            
            |> filter(fn: (r) => r["_field"] == "Ax" or r["_field"] == "Ay" or r["_field"] == "Az" or r["_field"] == "Gx" or r["_field"] == "Gy" or r["_field"] == "Gz")
            |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''

        try:
            result = self.data_manager.influxdb_client.query_api().query(
                org=self.data_manager.config['influxdb']['org'], query=query
            )
            data = [record.values for table in result for record in table.records]
            return pd.DataFrame(data)
        except Exception as e:
            print(i18n._("INFL-QRY-DATA-ERR").format(e=e))
            return pd.DataFrame()

    def calculate_magnitude(self, df: pd.DataFrame) -> pd.DataFrame:
        if {"Ax", "Ay", "Az", "Gx", "Gy", "Gz"}.issubset(df.columns):
            df["|a|"] = np.sqrt(df["Ax"]**2 + df["Ay"]**2 + df["Az"]**2)
            df["|g|"] = np.sqrt(df["Gx"]**2 + df["Gy"]**2 + df["Gz"]**2)
        else:
            # print("Faltan datos necesarios para calcular |a| y |g|.")
            print(i18n._("MVDET-AG-NODAT"))
        return df

    def is_effective_by_welch(self, signal: np.ndarray) -> bool:
        freqs, power = welch(signal, fs=self.sampling_rate)
        band_power = power[(freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])].sum()
        return band_power >= self.power_threshold

    def is_effective_by_time(self, signal: np.ndarray) -> bool:
        std_signal = np.std(signal)
        if std_signal < 0.01:
            return False
        active = signal > 0.2
        consecutive = (np.diff(np.where(np.concatenate(([active[0]],
                            active[:-1] != active[1:], [True])))[0])[::2])
        return any(consecutive >= self.min_continuous_seconds * self.sampling_rate)


    def detect_effective_movement(self, activity_windows: pd.DataFrame, \
                                nomf: str = None, vb: int = 0) -> pd.DataFrame:
        if "foot" not in activity_windows.columns:
            raise ValueError(i18n._("MVNT-ROOT-MISS"))

        results = []
        writer = None

        if nomf is not None:
            writer = pd.ExcelWriter(nomf, engine="xlsxwriter")

        for row in activity_windows.itertuples(index=False):
            try:
                start = pd.to_datetime(row.start_time, errors='coerce')
                end = pd.to_datetime(row.end_time, errors='coerce')
            except Exception as e:
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            if pd.isnull(start) or pd.isnull(end):
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            codeid_id = getattr(row, 'codeid_id')
            foot = getattr(row, 'foot')
            cid = getattr(row, 'CodeID', codeid_id)  # fallback

            if vb > 1:
                print(i18n._("MVNT-QRY-DAT").format(cid=cid, frm=start, \
                                                    dur=(end - start).total_seconds()))

            sensor_data = self.fetch_sensor_data(start, end, codeid_id, foot)
            if sensor_data.empty:
                continue

            # Exportar a Excel si corresponde
            if nomf is not None:
                sheet_name = f"{codeid_id}_{foot}_{start.strftime('%H%M%S')}"[:25]
                max_rows = 1000000
                for i in range((len(sensor_data) - 1) // max_rows + 1):
                    part = sensor_data.iloc[i * max_rows:(i + 1) * max_rows].copy()
                    for col in part.select_dtypes(['datetimetz']).columns:
                        part[col] = pd.to_datetime(part[col], utc=True).dt.tz_localize(None)
                    part_name = f"{sheet_name}_{i+1}"
                    part.to_excel(writer, sheet_name=part_name, index=False)
                    if vb > 0:
                        print(i18n._("MVNT-XLSX-DAT").format(shn=part_name, file=nomf))

            if vb > 1:
                print(i18n._("MVNT-QRY-REC").format(ns=sensor_data.shape[0]))

            sensor_data = self.calculate_magnitude(sensor_data)
            if "|a|" not in sensor_data.columns:
                continue

            acc = sensor_data["|a|"].to_numpy()
            if self.is_effective_by_welch(acc) and self.is_effective_by_time(acc):
                results.append({
                    "codeid_id": codeid_id,
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                    "duration": (end - start).total_seconds(),
                    "leg": foot
                })
                if self.verbose >= 2:
                    print(i18n._("MVNT-WLK-FOOT").format(codeid_id=codeid_id, foot=foot, \
                                                    dur=(end - start).total_seconds()))

        if writer:
            writer.close()

        try:
            validated = [EffectiveMovement(**r).dict() for r in results]
            return pd.DataFrame(validated)
        except ValidationError as e:
            print(i18n._("MVNT-VAL-EFF-ERR").format(e=e))
            return pd.DataFrame()


    def save_to_postgresql(self, table_name: str, df: pd.DataFrame) -> None:
        if df.empty:
            print(i18n._("PGSQL-INS-TAB-NOD-ERR").format(table_name=table_name))
            return

        try:
            self.data_manager.store_data(table_name, df)
        except Exception as e:
            print(i18n._("PGSQL-INS-TAB-ERR").format(fable_name=table_name,e=e))
