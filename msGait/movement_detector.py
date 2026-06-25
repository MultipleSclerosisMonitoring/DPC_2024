import pandas as pd
import numpy as np
from datetime import datetime

from pandas import ExcelWriter
from pandas.api.types import DatetimeTZDtype

from msTools.data_manager import DataManager
from msTools import i18n
from msTools.timeutils import ensure_utc
from msGait.models import EffectiveMovement

from scipy.signal import welch
from pydantic import ValidationError
from typing import Any, cast


class MovementDetector:
    """Detects effective movement and gait periods using raw sensor data from a data manager."""

    def __init__(
        self,
        config_file: str,
        sampling_rate: float | None = None,
        sect: str = "movement",
        fstart: str | None = None,
        fend: str | None = None,
        ids: list[int] | None = None,
        verbose: int = 1
    ) -> None:
        """Initializes the movement detector, loads configurations and activity data.

        Args:
            config_file (str): Path to the YAML configuration file.
            sampling_rate (float | None): Sampling rate of the sensor data (in Hz). If None, it is read from config.
            sect (str): Section in the YAML config for movement detection parameters.
            fstart (str | None): Optional start timestamp for activity query.
            fend (str | None): Optional end timestamp for activity query.
            ids (list[int] | None): Optional list of segment IDs to retrieve.
            verbose (int): Verbosity level for logging (0 = silent, 1 = info, 2 = debug).
        """
        self.verbose = verbose

        # Initialize DataManager
        self.data_manager = DataManager(config_path=config_file)
        
        self.ids = ids

        if self.ids is None and fstart is not None and fend is not None:
            try:
                resolved_ids = self.data_manager.get_activity_ids_by_start_date_range(fstart, fend)
                if verbose >= 1:
                    if resolved_ids:
                        print(f"[MovementDetector] {len(resolved_ids)} ID(s) found in activity_all for the time window.")
                    else:
                        print("[MovementDetector] No IDs found in activity_all for the requested time window.")
                if resolved_ids:
                    self.ids = resolved_ids
            except Exception as e:
                if verbose >= 1:
                    print(f"[MovementDetector] ID lookup by start_date failed: {e}")

        # Retrieve activity segments based on IDs or time range from activity_all table
        self.activity_all = self.data_manager.segments_retrieval(
            fstart=fstart, fend=fend, ids=self.ids, verbose=verbose
        )
        if self.activity_all.empty and verbose >= 1:
            print(i18n._("FGAIT_NO_WINS"))

        # Retrieve full sensor-linked activity
        self.df_legs = self.data_manager.recover_activity_all(
            self.activity_all, verbose=verbose
        )
        
        # Load detection parameters from config
        params = self.data_manager.get_config(sect)
        if params is None:
            raise ValueError(f"Missing configuration section: {sect}")
        self.sampling_rate = float(
            sampling_rate if sampling_rate is not None else params.get("sampling_rate", 47.0)
        )
        self.resample_hz = float(params.get("resample_hz", 100.0))
        self.window_size_samples = int(params.get("window_size_samples", 256))
        self.min_window_fraction = float(params.get("min_window_fraction", 0.5))
        self.min_effective_duration_sec = float(params.get("min_effective_duration_sec", 6.0))
        self.min_gait_duration_sec = float(params.get("min_gait_duration_sec", 6.0))
        self.freq_band = (params["freq_band_min"], params["freq_band_max"])
        self.min_continuous_hits = params["min_continuous_hits"]
        self.accel_threshold = params.get("accel_threshold", 0.2)
        self.gyro_threshold = params.get("gyro_threshold", 50)
        self.accel_power_threshold = params.get("accel_power_threshold",0.1)
        self.gyro_power_threshold = params.get("gyro_power_threshold",1000)
        self.gps_resample_seconds = int(params.get("gps_resample_seconds", 10))
        self.gps_padding_seconds = int(params.get("gps_padding_seconds", 15))
        self.gps_min_points = int(params.get("gps_min_points", 2))
        self.gps_min_distance_m = float(params.get("gps_min_distance_m", 3.0))
        self.gps_min_speed_m_s = float(params.get("gps_min_speed_m_s", 0.2))
        self.gps_max_speed_m_s = float(params.get("gps_max_speed_m_s", 3.0))

    def close(self) -> None:
        """Closing all the opened connections"""
        self.data_manager.close_all()
        
    def fetch_sensor_data(self, start_time: str | pd.Timestamp | datetime, end_time: str | pd.Timestamp | datetime,
                          codeid_id: int, foot: str) -> pd.DataFrame:
        """Fetches raw sensor data from InfluxDB for a specific time interval and limb.

        Args:
            start_time (str): Start time in ISO format.
            end_time (str): End time in ISO format.
            codeid_id (int): Identifier to map to real CodeID.
            foot (str): 'Left' or 'Right'.

        Returns:
            pd.DataFrame: Sensor data with fields Ax, Ay, Az, Gx, Gy, Gz, and timestamps.
        """
        try:
            codeid = self.data_manager.get_real_codeid(codeid_id)
        except ValueError as e:
            if self.verbose >= 1:
                print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            return pd.DataFrame()

        start_time = ensure_utc(start_time).isoformat().replace("+00:00", "Z")
        end_time = ensure_utc(end_time).isoformat().replace("+00:00", "Z")

        query = f'''
        from(bucket: "{self.data_manager.bucket}")
            |> range(start: {start_time}, stop: {end_time})
            |> filter(fn: (r) => r["CodeID"] == "{codeid}" and r["Foot"] == "{foot}")
            |> filter(fn: (r) => r["_field"] == "Ax" or r["_field"] == "Ay" or r["_field"] == "Az" 
                              or r["_field"] == "Gx" or r["_field"] == "Gy" or r["_field"] == "Gz")
            |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''

        try:
            result = self.data_manager.get_influx_client().query_api().query(
                query=query,
                org=self.data_manager.config['influxdb']['org']
            )
            data = [record.values for table in result for record in table.records]
            return pd.DataFrame(data)
        except Exception as e:
            msg = str(e)
            if "cannot query an empty range" in msg:
                if self.verbose >= 2:
                    print(i18n._("WARN_EMPTY_RANGE").format(codeid=codeid, foot=foot))
                return pd.DataFrame()
            if self.verbose >= 1:
                print(i18n._("INFL-QRY-DATA-ERR").format(e=e))
            return pd.DataFrame()
    

    def fetch_gps_data(
        self,
        start_time: str | pd.Timestamp | datetime,
        end_time: str | pd.Timestamp | datetime,
        codeid_id: int
    ) -> pd.DataFrame:
        """Fetches GPS data from InfluxDB for a specific time interval.

        Args:
            start_time (str): Start time in ISO format.
            end_time (str): End time in ISO format.
            codeid_id (int): Identifier to map to real CodeID.

        Returns:
            pd.DataFrame: GPS data with columns '_time', 'lat', 'lng'.
        """
        try:
            codeid = self.data_manager.get_real_codeid(codeid_id)
        except ValueError as e:
            if self.verbose >= 1:
                print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            return pd.DataFrame(columns=["_time", "lat", "lng"])

        start_time = ensure_utc(start_time).isoformat().replace("+00:00", "Z")
        end_time = ensure_utc(end_time).isoformat().replace("+00:00", "Z")

        query = f'''
        from(bucket: "{self.data_manager.bucket}")
            |> range(start: {start_time}, stop: {end_time})
            |> filter(fn: (r) => r["CodeID"] == "{codeid}")
            |> filter(fn: (r) => r["_field"] == "Ax")
            |> keep(columns: ["_time", "CodeID", "lat", "lng"])
        '''

        try:
            result = self.data_manager.get_influx_client().query_api().query(
                query=query,
                org=self.data_manager.config["influxdb"]["org"]
            )
            data = [record.values for table in result for record in table.records]
            df = pd.DataFrame(data)

            if df.empty:
                return pd.DataFrame(columns=["_time", "lat", "lng"])

            df["_time"] = pd.to_datetime(df["_time"], errors="coerce")
            df = df.dropna(subset=["_time"]).copy()

            if "lat" not in df.columns or "lng" not in df.columns:
                return pd.DataFrame(columns=["_time", "lat", "lng"])

            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
            df["lng"] = pd.to_numeric(df["lng"], errors="coerce")

            df = (
                df.dropna(subset=["lat", "lng"])
                .sort_values("_time")
                .drop_duplicates(subset=["_time", "lat", "lng"])
                .reset_index(drop=True)
            )

            return df[["_time", "lat", "lng"]]

        except Exception as e:
            msg = str(e)
            if "cannot query an empty range" in msg:
                return pd.DataFrame(columns=["_time", "lat", "lng"])
            if self.verbose >= 1:
                print(i18n._("INFL-QRY-DATA-ERR").format(e=e))
            return pd.DataFrame(columns=["_time", "lat", "lng"])
        
    @staticmethod
    def _haversine_distance_m(
        lat1: np.ndarray,
        lon1: np.ndarray,
        lat2: np.ndarray,
        lon2: np.ndarray
    ) -> np.ndarray:
        """Compute haversine distance in meters between consecutive GPS points."""
        earth_radius_m = 6371000.0

        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            np.sin(dlat / 2.0) ** 2
            + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
        return earth_radius_m * c

    @staticmethod
    def _prepare_gps_track(
        df_gps: pd.DataFrame,
        resample_seconds: int
    ) -> pd.DataFrame:
        """Clean and downsample GPS track to a manageable cadence."""
        if df_gps.empty:
            return pd.DataFrame(columns=["_time", "lat", "lng"])

        work = df_gps.copy()
        work["_time"] = pd.to_datetime(work["_time"], errors="coerce", utc=True)
        work["lat"] = pd.to_numeric(work["lat"], errors="coerce")
        work["lng"] = pd.to_numeric(work["lng"], errors="coerce")

        work = work.dropna(subset=["_time", "lat", "lng"]).copy()
        if work.empty:
            return pd.DataFrame(columns=["_time", "lat", "lng"])

        work = (
            work.sort_values("_time")
            .drop_duplicates(subset="_time", keep="last")
            .set_index("_time")
        )

        rule = f"{resample_seconds}s"
        work = work.resample(rule).first().dropna(subset=["lat", "lng"]).reset_index()

        return work[["_time", "lat", "lng"]]

    @classmethod
    def _summarize_prepared_gps_track(
        cls,
        gps_track: pd.DataFrame,
        min_points: int,
        min_distance_m: float,
        min_speed_m_s: float,
        max_speed_m_s: float
    ) -> dict[str, int | float | bool]:
        """Summarize one already-prepared GPS window."""
        if gps_track.empty or len(gps_track) < 2:
            return {
                "gps_points": int(len(gps_track)),
                "gps_distance_m": 0.0,
                "gps_elapsed_sec": 0.0,
                "gps_avg_speed_m_s": 0.0,
                "gps_validated": False,
            }

        lat1 = gps_track["lat"].to_numpy()[:-1]
        lon1 = gps_track["lng"].to_numpy()[:-1]
        lat2 = gps_track["lat"].to_numpy()[1:]
        lon2 = gps_track["lng"].to_numpy()[1:]

        distances = cls._haversine_distance_m(lat1, lon1, lat2, lon2)
        total_distance_m = float(np.nansum(distances))

        elapsed_sec = float(
            (gps_track["_time"].iloc[-1] - gps_track["_time"].iloc[0]).total_seconds()
        )
        avg_speed_m_s = total_distance_m / elapsed_sec if elapsed_sec > 0 else 0.0

        gps_validated = (
            len(gps_track) >= min_points
            and total_distance_m >= min_distance_m
            and min_speed_m_s <= avg_speed_m_s <= max_speed_m_s
        )

        return {
            "gps_points": int(len(gps_track)),
            "gps_distance_m": total_distance_m,
            "gps_elapsed_sec": elapsed_sec,
            "gps_avg_speed_m_s": avg_speed_m_s,
            "gps_validated": gps_validated,
        }

    def validate_gait_with_gps(
        self,
        df_gait: pd.DataFrame,
        verbose: int = 0
    ) -> pd.DataFrame:
        """Validate detected gait episodes against GPS displacement.

        This is an external validation layer. It does not replace inertial gait
        detection; it enriches each gait episode with GPS support metrics.
        """
        if df_gait.empty:
            return df_gait.copy()

        work = df_gait.copy()
        work["start_time"] = pd.to_datetime(work["start_time"], errors="coerce", utc=True)
        work["end_time"] = pd.to_datetime(work["end_time"], errors="coerce", utc=True)
        work = work.dropna(subset=["start_time", "end_time"]).copy()

        if work.empty:
            return work

        padding = pd.to_timedelta(self.gps_padding_seconds, unit="s")
        enriched_parts: list[pd.DataFrame] = []

        for codeid_id, group in work.groupby("codeid_id"):
            fetch_start = group["start_time"].min() - padding
            fetch_end = group["end_time"].max() + padding

            gps_raw = self.fetch_gps_data(fetch_start, fetch_end, int(cast(Any, codeid_id)))
            gps_track = self._prepare_gps_track(
                gps_raw,
                self.gps_resample_seconds
            )

            rows: list[dict[str, object]] = []

            for _, gait_row in group.iterrows():
                window_start = gait_row["start_time"] - padding
                window_end = gait_row["end_time"] + padding

                if gps_track.empty:
                    window_track = gps_track
                else:
                    window_track = gps_track[
                        (gps_track["_time"] >= window_start) &
                        (gps_track["_time"] <= window_end)
                    ].copy()

                gps_summary = self._summarize_prepared_gps_track(
                    gps_track=window_track,
                    min_points=self.gps_min_points,
                    min_distance_m=self.gps_min_distance_m,
                    min_speed_m_s=self.gps_min_speed_m_s,
                    max_speed_m_s=self.gps_max_speed_m_s,
                )

                output_row = gait_row.to_dict()
                output_row.update(gps_summary)
                rows.append(output_row)

            enriched_group = pd.DataFrame(rows)
            enriched_parts.append(enriched_group)

            if verbose >= 2:
                validated_count = int(enriched_group["gps_validated"].sum())
                print(
                    f"[GPS] codeid_id={codeid_id} | gait_rows={len(enriched_group)} | "
                    f"gps_validated={validated_count}"
                )

        return pd.concat(enriched_parts, ignore_index=True)


    def resample_sensor_data(self, df: pd.DataFrame, target_hz: float) -> pd.DataFrame:
        """Resamples raw sensor data to a fixed temporal grid.

        Args:
            df (pd.DataFrame): Raw sensor data containing a '_time' column.
            target_hz (float): Target resampling frequency in Hz.

        Returns:
            pd.DataFrame: Resampled sensor data with a regular '_time' grid.
        """
        if df.empty:
            return df

        if "_time" not in df.columns:
            raise ValueError(i18n._("ERR_MISSING_TIME_COLUMN"))

        numeric_cols = [col for col in ["Ax", "Ay", "Az", "Gx", "Gy", "Gz"] if col in df.columns]
        if not numeric_cols:
            return pd.DataFrame()

        work = df[["_time"] + numeric_cols].copy()
        work["_time"] = pd.to_datetime(work["_time"], errors="coerce")
        work = work.dropna(subset=["_time"])
        if work.empty:
            return pd.DataFrame()

        work = (
            work.sort_values("_time")
                .drop_duplicates(subset="_time", keep="last")
                .set_index("_time")
        )

        if len(work) < 2:
            return work.reset_index()

        sample_period = pd.to_timedelta(1 / target_hz, unit="s")

        resampled = (
            work.resample(sample_period)
                .mean()
                .interpolate(method="time", limit_direction="both")
                .reset_index()
        )

        return resampled

    def calculate_magnitude(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates signal magnitudes for acceleration and gyroscope data.

        Args:
            df (pd.DataFrame): DataFrame containing raw sensor values.

        Returns:
            pd.DataFrame: Same DataFrame with added ``|a|`` and ``|g|`` columns.
        """
        if {"Ax", "Ay", "Az", "Gx", "Gy", "Gz"}.issubset(df.columns):
            df["|a|"] = np.sqrt(df["Ax"]**2 + df["Ay"]**2 + df["Az"]**2)
            df["|g|"] = np.sqrt(df["Gx"]**2 + df["Gy"]**2 + df["Gz"]**2)
        else:
            if self.verbose >= 1:
                print(i18n._("MVDET-AG-NODAT"))
        return df

    def is_effective_by_welch(self, signal: np.ndarray, power_threshold: float, sampling_rate: float) -> bool:
        """Determines if a signal contains sufficient power in a frequency band.

        Args:
            signal (np.ndarray): Input signal array.
            power_threshold (float): Minimum band power required to mark the segment as effective.
            sampling_rate (float): Sampling rate used for spectral analysis.

        Returns:
            bool: True if power within the target frequency band exceeds threshold.
        """
        if len(signal) < 2:
            return False
        freqs, power = welch(
            signal,
            fs=sampling_rate,
            nperseg=min(len(signal), self.window_size_samples)
        )
        band_power = power[(freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])].sum()
        return band_power >= power_threshold

    def is_effective_by_time(self, signal: np.ndarray, threshold: float) -> bool:
        """Checks if the signal remains active for a continuous minimum duration.

        Args:
            signal (np.ndarray): Input signal array.
            threshold (float): Activity threshold.

        Returns:
            bool: True if signal is continuously active long enough.
        """
        std_signal = np.std(signal)
        if std_signal < 0.01:
            return False
        active = np.abs(signal) > threshold
        consecutive = np.diff(
            np.where(
                np.concatenate(([active[0]], active[:-1] != active[1:], [True]))
            )[0]
        )[::2]
        return (len(consecutive) >= self.min_continuous_hits)

    
    def detect_effective_movement(
        self,
        activity_windows: pd.DataFrame,
        output_filename: str | None = None,
        verbose: int = 0
    ) -> pd.DataFrame:
        """Detects intervals of effective movement from sensor data.

        Args:
            activity_windows (pd.DataFrame): DataFrame containing rows with start_time, 
                                             end_time, codeid_id, and foot.
            output_filename (str, optional): Path to an Excel file for exporting raw data 
                                  (default is None).
            verbose (int): Verbosity level (0 = silent, 1 = info, 2 = debug).

        Returns:
            pd.DataFrame: Validated segments with effective movement data.
        """

        def segment_fixed_windows(df: pd.DataFrame, window_size: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
            """
            Split the data into consecutive fixed-size windows (by sample count),
            optionally keeping the final partial window if it is large enough.

            Args:
                df (pd.DataFrame): Sorted DataFrame with a '_time' column.
                window_size (int): Number of samples per window.

            Returns:
                list[tuple[pd.Timestamp, pd.Timestamp]]: (start_time, end_time) for each window.
            """
            if "_time" not in df.columns:
                raise ValueError(i18n._("ERR_MISSING_TIME_COLUMN"))

            df = df.sort_values("_time").reset_index(drop=True)

            segments = []
            total_rows = len(df)

            full_limit = total_rows - window_size + 1
            last_full_start = None

            for i in range(0, max(full_limit, 0), window_size):
                start_time = df.loc[i, "_time"]
                end_time = df.loc[i + window_size - 1, "_time"]
                segments.append((start_time, end_time))
                last_full_start = i

            if total_rows == 0:
                return segments

            next_start = 0 if last_full_start is None else last_full_start + window_size
            remaining = total_rows - next_start

            if 0 < remaining < window_size:
                min_partial_samples = max(2, int(np.ceil(window_size * self.min_window_fraction)))
                if remaining >= min_partial_samples:
                    start_time = df.loc[next_start, "_time"]
                    end_time = df.loc[total_rows - 1, "_time"]
                    segments.append((start_time, end_time))

            return segments

        def merge_connected_segments(segments: list[tuple[pd.Timestamp, pd.Timestamp]], 
                                     max_gap_sec=5.):
            """Merges temporally close segments into a single one.

            Args:
                segments (list[tuple[pd.Timestamp, pd.Timestamp]]): List of segment start and end times.
                max_gap_sec (float): Maximum allowed gap for merging segments.

            Returns:
                list[tuple[pd.Timestamp, pd.Timestamp]]: Merged list of segments.
            """
            if not segments:
                return []

            segments = sorted(segments, key=lambda x: x[0])
            merged = []
            current_start, current_end = segments[0]

            for start, end in segments[1:]:
                gap = (start - current_end).total_seconds()
                if gap <= max_gap_sec:
                    current_end = max(current_end, end)
                else:
                    merged.append((current_start, current_end))
                    current_start, current_end = start, end

            merged.append((current_start, current_end))
            return merged
        #
        # End of aux fucntion. 
        # Starting point for function detect_effective_movement()

        if "foot" not in activity_windows.columns:
            raise ValueError(i18n._("MVNT-ROOT-MISS"))

        results = []
        writer = ExcelWriter(output_filename, engine="xlsxwriter") if output_filename else None

        for row in activity_windows.itertuples(index=False):
            segments = []
            valid_segments = []
            
            if verbose >= 1:
                print(i18n._("MSG_TMP_IDS").format(id=row.CodeID,ref=row.codeid_id,
                                tstart=row.start_time,tend=row.end_time))
            try:
                start = ensure_utc(cast(str | pd.Timestamp | datetime, row.start_time))
                end = ensure_utc(cast(str | pd.Timestamp | datetime, row.end_time))
                if end <= start:
                    if verbose >= 2:
                        print(f"Skipping invalid segment: start={start}, end={end}")
                    continue
            except Exception:
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            if pd.isnull(start) or pd.isnull(end):
                if self.verbose:
                    print(i18n._("MVNT-TS-NOV").format(row=row))
                continue

            codeid_id = int(cast(Any, row.codeid_id))
            foot = str(cast(Any, row.foot))
            cid = getattr(row, "CodeID", codeid_id)

            if verbose > 1:
                print(i18n._("MVNT-QRY-DAT").format(
                    cid=cid, frm=start, dur=(end - start).total_seconds()
                ))

            sensor_data = self.fetch_sensor_data(cast(pd.Timestamp, start), cast(pd.Timestamp, end), codeid_id, foot)
            sensor_data.drop(columns=['result', 'table', '_start', '_stop'],
                             inplace=True, errors='ignore')
            for col in sensor_data.columns:
                if isinstance(sensor_data[col].dtype, DatetimeTZDtype):
                    sensor_data[col] = sensor_data[col].dt.tz_localize(None)
            if sensor_data.empty:
                continue

            # Export to Excel if requested
            if writer:
                sheet_base = f"{codeid_id}_{foot}_{start.strftime('%H%M%S')}"[:25]
                max_rows = 1_000_000
                for i in range((len(sensor_data) - 1) // max_rows + 1):
                    part = sensor_data.iloc[i*max_rows:(i+1)*max_rows].copy()
                    for col in part.select_dtypes(['datetimetz']).columns:
                        part[col] = pd.to_datetime(part[col], utc=True).dt.tz_localize(None)
                    sheet = f"{sheet_base}_{i+1}"
                    part.to_excel(writer, sheet_name=sheet, index=False)
                    if verbose > 0:
                        print(i18n._("MVNT-XLSX-DAT").format(shn=sheet, file=output_filename))

            if verbose > 1:
                print(i18n._("MVNT-QRY-REC").format(ns=sensor_data.shape[0]))

            sensor_data = self.resample_sensor_data(sensor_data, self.resample_hz)
            if sensor_data.empty:
                continue

            sensor_data = self.calculate_magnitude(sensor_data)
            if "|a|" not in sensor_data.columns or "|g|" not in sensor_data.columns:
                continue

            sensor_data = sensor_data.sort_values("_time").reset_index(drop=True)
            analysis_sampling_rate = self.resample_hz

            # Split into fixed-size analysis windows
            segments = segment_fixed_windows(sensor_data, self.window_size_samples)

            for seg_start, seg_end in segments:
                seg_data = sensor_data[(sensor_data["_time"] >= seg_start) &
                                       (sensor_data["_time"] <= seg_end)]

                acc_seg = seg_data["|a|"].to_numpy()
                gyro_seg = seg_data["|g|"].to_numpy()

                acc_ok = self.is_effective_by_welch(
                    acc_seg,
                    self.accel_power_threshold,
                    analysis_sampling_rate
                ) and self.is_effective_by_time(acc_seg - 1, self.accel_threshold)

                gyro_ok = self.is_effective_by_welch(
                    gyro_seg,
                    self.gyro_power_threshold,
                    analysis_sampling_rate
                ) and self.is_effective_by_time(gyro_seg, self.gyro_threshold)

                if acc_ok or gyro_ok:
                    valid_segments.append((seg_start, seg_end))

            merged_segments = merge_connected_segments(valid_segments, max_gap_sec=10)
            filtered_segments = [
                (mstart, mend)
                for mstart, mend in merged_segments
                if (mend - mstart).total_seconds() >= self.min_effective_duration_sec
            ]

            for mstart, mend in filtered_segments:
                results.append({
                    "codeid_id": codeid_id,
                    "start_time": mstart.isoformat(),
                    "end_time": mend.isoformat(),
                    "duration": (mend - mstart).total_seconds(),
                    "leg": foot
                })

            if verbose >= 3:
                print(i18n._("LST-SEGS").format(results=pd.DataFrame(results)))
                
            if verbose >= 2:
                print(i18n._("MVNT-WLK-FOOT").format(cid=codeid_id, foot=foot,
                    dur=(end - start).total_seconds()))

        if writer:
            writer.close()

        try:
            validated = [EffectiveMovement(**r).model_dump() for r in results]
            return pd.DataFrame(validated)
        except ValidationError as e:
            print(i18n._("MVNT-VAL-EFF-ERR").format(e=e))
            return pd.DataFrame()

    def detect_effective_gait(self, df_effective: pd.DataFrame, verbose: int = 0) -> pd.DataFrame:
        """Detect overlapping periods of effective movement for both feet.

        Args:
            df_effective (pd.DataFrame): Movement segments with columns
                ['codeid_id', 'start_time', 'end_time', 'duration', 'leg'].
            verbose (int): Verbosity level.

        Returns:
            pd.DataFrame: Gait episodes, optionally enriched with GPS validation fields.
        """
        base_columns = ["codeid_id", "start_time", "end_time", "duration", "gait_confidence_level"]
        gps_columns = [
            "gps_points",
            "gps_distance_m",
            "gps_elapsed_sec",
            "gps_avg_speed_m_s",
            "gps_validated",
        ]
        output_columns = base_columns + gps_columns

        if df_effective.empty:
            return pd.DataFrame(columns=output_columns)

        df = df_effective.copy()

        def _parse_mixed_utc_naive(value):
            if pd.isnull(value):
                return pd.NaT
            ts = pd.Timestamp(value)
            if ts.tzinfo is None:
                return ts
            return ts.tz_convert("UTC").tz_localize(None)

        df["start_time"] = pd.Series([_parse_mixed_utc_naive(value) for value in df["start_time"]], index=df.index)
        df["end_time"] = pd.Series([_parse_mixed_utc_naive(value) for value in df["end_time"]], index=df.index)
        df = df.dropna(subset=["start_time", "end_time"]).copy()

        gait_rows: list[dict] = []
        brief_gait_duration_sec = min(
            self.min_effective_duration_sec,
            self.min_gait_duration_sec,
        )

        for codeid, grp in df.groupby("codeid_id"):
            left = grp[grp["leg"] == "Left"][["start_time", "end_time"]]
            right = grp[grp["leg"] == "Right"][["start_time", "end_time"]]

            if left.empty or right.empty:
                continue

            left = left.assign(_key=1)
            right = right.assign(_key=1)
            merged = left.merge(right, on="_key", suffixes=("_L", "_R")).drop(columns="_key")

            for _, row in merged.iterrows():
                start_time = max(row["start_time_L"], row["start_time_R"])
                end_time = min(row["end_time_L"], row["end_time_R"])

                if start_time < end_time:
                    duration = (end_time - start_time).total_seconds()
                    gait_confidence_level = 0
                    if duration >= self.min_gait_duration_sec:
                        gait_confidence_level = 2
                    elif duration >= brief_gait_duration_sec:
                        gait_confidence_level = 1

                    if gait_confidence_level > 0:
                        gait_rows.append(
                            {
                                "codeid_id": codeid,
                                "start_time": start_time,
                                "end_time": end_time,
                                "duration": duration,
                                "gait_confidence_level": gait_confidence_level,
                            }
                        )

        df_gait = pd.DataFrame(gait_rows, columns=base_columns)

        if df_gait.empty:
            return pd.DataFrame(columns=output_columns)

        for col in gps_columns:
            if col not in df_gait.columns:
                df_gait[col] = pd.NA

        return df_gait[output_columns]

    def save_to_postgresql(self, table_name: str, df: pd.DataFrame, verbose: int = 0) -> None:
        """Saves the given DataFrame to a PostgreSQL table using the DataManager.

        Args:
            table_name (str): Name of the destination table.
            df (pd.DataFrame): DataFrame to store.

        Returns:
            None
        """
        if df.empty and verbose > 0:
            print(i18n._("PGSQL-INS-TAB-NOD-ERR").format(table_name=table_name))
            return
        try:
            self.data_manager.store_data(table_name, df, verbose)
        except Exception as e:
            print(i18n._("PGSQL-INS-TAB-ERR").format(table_name=table_name, e=e))

