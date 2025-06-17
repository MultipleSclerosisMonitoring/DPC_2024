import pandas as pd
import numpy as np
from pandas import ExcelWriter
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from msTools.data_manager import DataManager
from msTools import i18n
from scipy.signal import welch
from msGait.models import EffectiveMovement
from pydantic import ValidationError
from msTools.timeutils import ensure_utc


class MovementDetector:
    def __init__(
        self,
        config_file: str,
        sampling_rate: float,
        sect: str = "movement",
        fstart: Optional[str] = None,
        fend: Optional[str] = None,
        ids: Optional[List[int]] = None,
        verbose: int = 1
    ) -> None:
        """
        Inicializa el detector:
         - Construye internamente el DataManager.
         - Recupera activity_all (por IDs o ventana de tiempo).
         - Genera df_legs (piernas) a partir de activity_all.
         - Carga parámetros de la sección `sect` del config.yaml.

        :param config_file: Ruta al YAML de configuración.
        :param sampling_rate: Frecuencia de muestreo.
        :param sect: Sección de config para parámetros de movimiento.
        :param fstart: Fecha/hora inicio (si no se pasan ids).
        :param fend: Fecha/hora fin (si no se pasan ids).
        :param ids: Lista de IDs de activity_all.
        :param verbose: Nivel de verbosidad.
        """
        self.verbose = verbose
        self.sampling_rate = sampling_rate

        # 1) DataManager interno
        self.data_manager = DataManager(config_path=config_file)

        # 2) Recuperar activity_all
        self.activity_all = self.data_manager.segments_retrieval(
            fstart=fstart,
            fend=fend,
            ids=ids,
            verbose=verbose
        )
        if self.activity_all.empty and verbose >= 1:
            print(i18n._("FGAIT_NO_WINS"))

        # 3) Generar df_legs
        self.df_legs = self.data_manager.recover_activity_all(
            self.activity_all,
            vb=verbose
        )

        # 4) Parámetros de movimiento
        params = self.data_manager.get_config(sect)
        self.freq_band = (params["freq_band_min"], params["freq_band_max"])
        self.power_threshold = params["power_threshold"]
        self.min_continuous_seconds = params["min_continuous_seconds"]
        self.accel_threshold = params.get("accel_threshold", 0.2)
        self.gyro_threshold  = params.get("gyro_threshold", 0.2)

    def fetch_sensor_data(self, start_time: str, end_time: str,
                          codeid_id: int, foot: str) -> pd.DataFrame:
        try:
            codeid = self.data_manager.get_real_codeid(codeid_id)
        except ValueError as e:
            if self.verbose >= 1:
                print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            return pd.DataFrame()

        # UTC ISO
        start_time = ensure_utc(start_time).isoformat().replace("+00:00", "Z")
        end_time   = ensure_utc(end_time)  .isoformat().replace("+00:00", "Z")

        query = f'''
        from(bucket: "{self.data_manager.bucket}")
            |> range(start: {start_time}, stop: {end_time})
            |> filter(fn: (r) => r["CodeID"] == "{codeid}" and r["Foot"] == "{foot}")            
            |> filter(fn: (r) => r["_field"] == "Ax" or r["_field"] == "Ay" or r["_field"] == "Az" or r["_field"] == "Gx" or r["_field"] == "Gy" or r["_field"] == "Gz")
            |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''

        try:
            result = self.data_manager.influxdb_client.query_api().query(
                query=query,
                org=self.data_manager.config['influxdb']['org']
            )
            data = [record.values for table in result for record in table.records]
            return pd.DataFrame(data)
        except Exception as e:
            msg = str(e)
            # Ignorar rango vacío sin spam en consola
            if "cannot query an empty range" in msg:
                if self.verbose >= 2:
                    print(f"[MovementDetector] empty range for CodeID {codeid}, foot {foot}")
                return pd.DataFrame()
            # Otros errores sí los mostramos si verbose >= 1
            if self.verbose >= 1:
                print(i18n._("INFL-QRY-DATA-ERR").format(e=e))
            return pd.DataFrame()

    def calculate_magnitude(self, df: pd.DataFrame) -> pd.DataFrame:
        if {"Ax", "Ay", "Az", "Gx", "Gy", "Gz"}.issubset(df.columns):
            df["|a|"] = np.sqrt(df["Ax"]**2 + df["Ay"]**2 + df["Az"]**2)
            df["|g|"] = np.sqrt(df["Gx"]**2 + df["Gy"]**2 + df["Gz"]**2)
        else:
            if self.verbose >= 1:
                print(i18n._("MVDET-AG-NODAT"))
        return df

    def is_effective_by_welch(self, signal: np.ndarray) -> bool:
        freqs, power = welch(signal, fs=self.sampling_rate)
        band_power = power[(freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])].sum()
        return band_power >= self.power_threshold

    def is_effective_by_time(self, signal: np.ndarray, threshold: float) -> bool:
        std_signal = np.std(signal)
        if std_signal < 0.01:
            return False
        active = signal > threshold
        consecutive = np.diff(
            np.where(
                np.concatenate(([active[0]], active[:-1] != active[1:], [True]))
            )[0]
        )[::2]
        return any(consecutive >= self.min_continuous_seconds * self.sampling_rate)

    def detect_effective_movement(
        self,
        activity_windows: pd.DataFrame,
        nomf: str = None,
        vb: int = 0
    ) -> pd.DataFrame:
        if "foot" not in activity_windows.columns:
            raise ValueError(i18n._("MVNT-ROOT-MISS"))

        results = []
        writer = ExcelWriter(nomf, engine="xlsxwriter") if nomf else None

        for row in activity_windows.itertuples(index=False):
            try:
                start = ensure_utc(row.start_time)
                end = ensure_utc(row.end_time)
            except Exception:
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            if pd.isnull(start) or pd.isnull(end):
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            codeid_id = row.codeid_id
            foot = row.foot
            cid = getattr(row, "CodeID", codeid_id)

            if vb > 1:
                print(i18n._("MVNT-QRY-DAT").format(
                    cid=cid, frm=start, dur=(end - start).total_seconds()
                ))

            sensor_data = self.fetch_sensor_data(start, end, codeid_id, foot)
            if sensor_data.empty:
                continue

            # Exportar a Excel si corresponde
            if writer:
                sheet_base = f"{codeid_id}_{foot}_{start.strftime('%H%M%S')}"[:25]
                max_rows = 1_000_000
                for i in range((len(sensor_data) - 1) // max_rows + 1):
                    part = sensor_data.iloc[i*max_rows:(i+1)*max_rows].copy()
                    for col in part.select_dtypes(['datetimetz']).columns:
                        part[col] = pd.to_datetime(part[col], utc=True).dt.tz_localize(None)
                    sheet = f"{sheet_base}_{i+1}"
                    part.to_excel(writer, sheet_name=sheet, index=False)
                    if vb > 0:
                        print(i18n._("MVNT-XLSX-DAT").format(shn=sheet, file=nomf))

            if vb > 1:
                print(i18n._("MVNT-QRY-REC").format(ns=sensor_data.shape[0]))

            sensor_data = self.calculate_magnitude(sensor_data)
            if "|a|" not in sensor_data.columns or "|g|" not in sensor_data.columns:
                continue

            acc  = sensor_data["|a|"].to_numpy()
            gyro = sensor_data["|g|"].to_numpy()

            acc_ok  = self.is_effective_by_welch(acc)  and self.is_effective_by_time(acc,  self.accel_threshold)
            gyro_ok = self.is_effective_by_welch(gyro) and self.is_effective_by_time(gyro, self.gyro_threshold)

            if acc_ok or gyro_ok:
                results.append({
                    "codeid_id": codeid_id,
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                    "duration": (end - start).total_seconds(),
                    "leg": foot
                })
                if vb >= 2:
                    print(i18n._("MVNT-WLK-FOOT").format(
                        codeid_id=codeid_id, foot=foot,
                        dur=(end - start).total_seconds()
                    ))

        if writer:
            writer.close()

        try:
            validated = [EffectiveMovement(**r).model_dump() for r in results]
            return pd.DataFrame(validated)
        except ValidationError as e:
            print(i18n._("MVNT-VAL-EFF-ERR").format(e=e))
            return pd.DataFrame()
        
    def detect_effective_gait(self, df_effective: pd.DataFrame) -> pd.DataFrame:
        """
        Determina periodos en que ambos pies realizan marcha efectiva simultáneamente.

        :param df_effective: DataFrame con columnas
                             ['codeid_id','start_time','end_time','duration','leg']
        :return: DataFrame con columnas
                 ['codeid_id','start_time','end_time','duration']
        """
        if df_effective.empty:
            return pd.DataFrame(columns=['codeid_id','start_time','end_time','duration'])

        df = df_effective.copy()
        # Asegurar tipos datetime
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time']   = pd.to_datetime(df['end_time'])

        gait_rows = []
        for codeid, grp in df.groupby('codeid_id'):
            left  = grp[grp['leg'] == 'Left'][['start_time','end_time']]
            right = grp[grp['leg'] == 'Right'][['start_time','end_time']]
            if left.empty or right.empty:
                continue

            # Producto cartesiano por codeid
            left  = left.assign(_key=1)
            right = right.assign(_key=1)
            merged = left.merge(right, on='_key', suffixes=('_L','_R')).drop(columns='_key')

            for _, r in merged.iterrows():
                st = max(r['start_time_L'], r['start_time_R'])
                en = min(r['end_time_L'],   r['end_time_R'])
                if st < en:
                    gait_rows.append({
                        'codeid_id': codeid,
                        'start_time': st,
                        'end_time':   en,
                        'duration':   (en - st).total_seconds()
                    })

        return pd.DataFrame(gait_rows)

    def save_to_postgresql(self, table_name: str, df: pd.DataFrame) -> None:
        if df.empty:
            print(i18n._("PGSQL-INS-TAB-NOD-ERR").format(table_name=table_name))
            return
        try:
            self.data_manager.store_data(table_name, df)
        except Exception as e:
            print(i18n._("PGSQL-INS-TAB-ERR").format(fable_name=table_name, e=e))
