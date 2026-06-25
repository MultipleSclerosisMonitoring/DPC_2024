import pandas as pd
from influxdb_client import InfluxDBClient
import psycopg2
from collections.abc import Sequence

from msTools.models import CodeID, ActivityLeg, ActivityAll
from msTools import i18n
from msTools.timeutils import ensure_utc
from msGait.models import EffectiveMovement, EffectiveGait, ActivitySegment
from pydantic import ValidationError
from typing import Any, cast
from psycopg2 import sql
import datetime
from pandas.api.types import DatetimeTZDtype

from msTools.settings import AppConfig, get_runtime_config_path, load_app_config



class DataManager:
    def _require_pg_conn(self) -> psycopg2.extensions.connection:
        if self.pg_conn is None:
            raise RuntimeError("PostgreSQL connection is not initialized.")
        return self.pg_conn


    def __init__(self, config_path: str) -> None:
        """Initialize the DataManager and open database connections.

        Args:
            config_path: Path to the YAML configuration file.
        """
        # Initialize attributes early so __del__ never fails even if init raises.
        self.settings: AppConfig | None = None
        self.config: dict[str, Any] = {}
        self.pg_conn: psycopg2.extensions.connection | None = None
        self.influxdb_client: InfluxDBClient | None = None
        self.bucket: str = ""
        self.measurement: str = ""

        self.settings = load_app_config(get_runtime_config_path(config_path))
        self.config = self.settings.model_dump(mode="python")

        # Configure PostgreSQL connection
        self.pg_conn = self._connect_postgresql()

        # Configure InfluxDB client
        self.influxdb_client = InfluxDBClient(
            url=self.config["influxdb"]["url"],
            token=self.config["influxdb"]["token"],
            org=self.config["influxdb"]["org"],
            timeout=self.config["influxdb"]["timeout"]
        )
        self.bucket: str = self.config["influxdb"]["bucket"]
        self.measurement: str = self.config['influxdb']['measurement']

    def __del__(self) -> None:
        """Ensure all connections are closed on deletion."""
        # Never raise in destructors (it creates noisy 'Exception ignored in ...').
        try:
            self.close_influxdb()
        except Exception:
            pass
        try:
            self.close_pg()
        except Exception:
            pass

    def load_config(self, config_path: str) -> dict[str, Any]:
        """Load and validate configuration values.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            Parsed configuration dictionary after environment overrides.
        """
        settings = load_app_config(get_runtime_config_path(config_path))
        return settings.model_dump(mode="python")
        
    def get_config(self, sect: str) -> dict[str, Any] | None:
        """Return one configuration section from the loaded config.

        Args:
            sect: Name of the section to retrieve.

        Returns:
            The requested configuration section, or ``None`` if it does not exist.
        """
        if sect in self.config.keys():
            return self.config.get(sect)
        else:
            return None

    def _connect_postgresql(self) -> psycopg2.extensions.connection:
        """Create and return a PostgreSQL connection.

        Returns:
            Open psycopg2 PostgreSQL connection.
        """
        try:
            return psycopg2.connect(
                host=self.config["postgresql"]["host"],
                port=self.config["postgresql"].get("port", 5432),
                database=self.config["postgresql"]["database"],
                user=self.config["postgresql"]["user"],
                password=self.config["postgresql"]["password"],
                options="-c timezone=UTC"
            )
        except psycopg2.OperationalError as e:
            print(i18n._("PGSQL-CONN-ERR").format(e=e))
            raise

    def close_pg(self) -> None:
        """Closes the PostgreSQL connection."""
        if self.pg_conn is not None and getattr(self.pg_conn, "closed", 1) == 0:
            self.pg_conn.close()

    def close_influxdb(self) -> None:
        """Closes the InfluxDB client."""
        if self.influxdb_client is not None:
            self.influxdb_client.close()

    def close_all(self) -> None:
        """Closes both PostgreSQL and InfluxDB connections."""
        if self.pg_conn is not None and getattr(self.pg_conn, "closed", 1) == 0:
            self.pg_conn.close()
        if self.influxdb_client is not None:
            self.influxdb_client.close()

    def get_influx_client(self) -> InfluxDBClient:
        """Return the active InfluxDB client instance.

        Returns:
            InfluxDB client used by the repository.

        Raises:
            RuntimeError: If the client is not initialized.
        """
        if self.influxdb_client is None:
            raise RuntimeError("InfluxDB client is not initialized.")
        return self.influxdb_client

    def check_and_create_tables(self, sql_file_path: str) -> None:
        """Create required PostgreSQL tables when they do not exist.

        Args:
            sql_file_path: Path to the SQL file containing the table definitions.
        """
        try:
            required_tables = [
                "codeids",
                "effective_movement",
                "activity_leg",
                "activity_all",
                "fullref_sensor_codeid",
                "effective_gait",
            ]

            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                for table_name in required_tables:
                    cursor.execute(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        );
                    """)
                    fetchone_result = cursor.fetchone()
                    if fetchone_result is None:
                        raise RuntimeError(f"Table existence query did not return a row for {table_name}.")
                    exists = fetchone_result[0]
                    if not exists:
                        print(i18n._("INFO_CREATE_TABLE").format(table=table_name, file=sql_file_path))
                        with open(sql_file_path, "r", encoding="utf-8") as sql_file:
                            sql_script = sql_file.read()
                            cursor.execute(sql_script)
                            pg_conn.commit()
                    else:
                        print(i18n._("INFO_TABLE_EXISTS").format(table=table_name))
        except Exception as e:
            pg_conn.rollback()
            print(i18n._("PGSQL-TAB-ERR").format(e=e))
            raise

    def get_codeids_in_range(self, start_datetime: str, end_datetime: str) -> list[str]:
        """Retrieve unique CodeIDs from InfluxDB inside a time range.

        Args:
            start_datetime: Start datetime as a string.
            end_datetime: End datetime as a string.

        Returns:
            Sorted list of unique CodeID values found in the interval.
        """
        try:
            start = ensure_utc(start_datetime)
            end = ensure_utc(end_datetime)

            start_iso = start.isoformat().replace("+00:00", "Z")
            end_iso = end.isoformat().replace("+00:00", "Z")

            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_iso}, stop: {end_iso})
                |> filter(fn: (r) => r._measurement == "{self.measurement}")
                |> filter(fn: (r) => exists r.CodeID)
                |> keep(columns: ["CodeID"])
                |> distinct(column: "CodeID")
            '''

            influx_client = self.get_influx_client()
            result = influx_client.query_api().query(
                query, org=self.config['influxdb']['org']
            )

            codeids = sorted(
                str(record.values["CodeID"])
                for table in result
                for record in table.records
                if record.values.get("CodeID") not in (None, "")
            )

            return codeids

        except Exception as e:
            print(i18n._("INFL-QRY-COD-ERR").format(e=e))
            return []
        

    def fetch_data(
        self,
        query: str,
        params: Sequence[Any] | None = None,
    ) -> pd.DataFrame:
        """Execute a SQL query in PostgreSQL and return the result as a DataFrame.

        Args:
            query: SQL query string.
            params: Optional SQL parameters passed to ``cursor.execute``.

        Returns:
            DataFrame containing the query results.
        """
        try:
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                if params is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, params)
                if cursor.description is None:
                    raise RuntimeError("Query did not return a description.")
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                return pd.DataFrame(data, columns=columns)
        except Exception as e:
            print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            raise

    def segments_retrieval(
        self,
        fstart: str | None = None,
        fend: str | None = None,
        ids: list[int] | None = None,
        verbose: int = 0
    ) -> pd.DataFrame:
        """Retrieve `activity_all` rows by explicit IDs or by overlapping time window.

        Args:
            fstart: Start datetime when retrieving by time range.
            fend: End datetime when retrieving by time range.
            ids: Explicit list of `activity_all` IDs to retrieve.
            verbose: Verbosity level for console output.

        Returns:
            DataFrame with columns
            [`id`, `start_time`, `end_time`, `duration`,
            `codeid_ids`, `codeleg_ids`, `active_legs`].

        Raises:
            ValueError: If neither a valid ID list nor a valid time window is provided.
        """
        query = """
            SELECT id, start_time, end_time, duration,
                codeid_ids, codeleg_ids, active_legs
            FROM activity_all
        """
        params = None

        if ids is not None:
            if len(ids) == 0:
                if verbose >= 1:
                    print(i18n._("WARN_NO_SEGMENTS_FOUND"))
                return pd.DataFrame(
                    columns=[
                        "id",
                        "start_time",
                        "end_time",
                        "duration",
                        "codeid_ids",
                        "codeleg_ids",
                        "active_legs",
                    ]
                )

            if verbose >= 1:
                print(i18n._("INFO_SEGMENTS_BY_IDS").format(ids=ids))

            query += " WHERE id = ANY(%s) ORDER BY codeid_ids;"
            params = (ids,)
        else:
            if not fstart or not fend:
                raise ValueError(i18n._("ERR_MISSING_IDS_OR_WINDOW"))

            if verbose >= 1:
                print(i18n._("INFO_SEGMENTS_BY_RANGE").format(start=fstart, end=fend))

            start_utc = ensure_utc(fstart)
            end_utc = ensure_utc(fend)

            query += """
                WHERE start_time <= %s
                AND end_time >= %s
                ORDER BY codeid_ids;
            """
            params = (end_utc, start_utc)

        try:
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(query, params)
                if cursor.description is None:
                    raise RuntimeError("Query did not return a description.")
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                df = pd.DataFrame(data, columns=columns)
        except Exception as e:
            print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            raise

        if df.empty and verbose >= 1:
            print(i18n._("WARN_NO_SEGMENTS_FOUND"))
        else:
            for col in df.columns:
                if isinstance(df[col].dtype, DatetimeTZDtype):
                    df[col] = df[col].dt.tz_localize(None)

        return df


    def recover_activity_all(self, act: pd.DataFrame, verbose: int = 0) -> pd.DataFrame:
        """Expand `activity_all` rows into per-leg rows with resolved CodeID values.

        Args:
            act: DataFrame containing `activity_all`-like rows.
            verbose: Verbosity level for console output.

        Returns:
            DataFrame with one row per leg and columns
            [`start_time`, `end_time`, `codeid_id`, `CodeID`, `foot`].
        """
        if act.empty:
            return pd.DataFrame(columns=["start_time", "end_time", "codeid_id", "CodeID", "foot"])

        activity_leg_like = []

        # Collect unique codeid_ids first to avoid N+1 queries
        unique_codeid_ids = sorted({
            int(codeid_id)
            for _, row in act.iterrows()
            for codeid_id in row["codeid_ids"]
            if codeid_id is not None
        })

        codeid_map = {}
        if unique_codeid_ids:
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, codeid FROM codeids WHERE id = ANY(%s);",
                    (unique_codeid_ids,)
                )
                codeid_map = {row_id: codeid for row_id, codeid in cursor.fetchall()}

        for _, row in act.iterrows():
            if verbose > 1:
                print(i18n._("VB_REG_ACT_ALL").format(row=row))

            for i, foot in enumerate(row["active_legs"]):
                current_codeid_id = row["codeid_ids"][i]
                resolved_codeid = codeid_map.get(int(current_codeid_id))

                if resolved_codeid is None:
                    raise ValueError(
                        i18n._("ERR_CODEID_NOT_FOUND").format(id=current_codeid_id)
                    )

                activity_leg_like.append({
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "codeid_id": current_codeid_id,
                    "CodeID": resolved_codeid,
                    "foot": foot
                })

        df_legs = pd.DataFrame(activity_leg_like)

        if verbose > 0:
            print(i18n._("VB-ACT-ALL-LEGS").format(ns=df_legs.shape[0]))

        if df_legs.shape[0] > 0:
            for col in df_legs.columns:
                if isinstance(df_legs[col].dtype, DatetimeTZDtype):
                    df_legs[col] = df_legs[col].dt.tz_localize(None)

        return df_legs


    def store_codeid(self, codeid: str, verbose: int = 0) -> tuple[int, bool]:
        """Store a unique CodeID in PostgreSQL and return its identifier.

        Args:
            codeid: CodeID string to insert or recover.
            verbose: Verbosity level for console output.

        Returns:
            Tuple containing the PostgreSQL ID and a boolean indicating
            whether the row was newly inserted.
        """
        try:
            validated_codeid = CodeID(codeid=codeid)

            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO codeids (codeid) VALUES (%s) ON CONFLICT (codeid) DO NOTHING RETURNING id;",
                    (validated_codeid.codeid,)
                )
                result = cursor.fetchone()
                if result:
                    new_id = result[0]
                    pg_conn.commit()
                    if verbose >= 2:
                        print(i18n._("INFO_CODEID_NEW").format(codeid=codeid, id=new_id))
                    return new_id, True
                
                cursor.execute("SELECT id FROM codeids WHERE codeid = %s;", (validated_codeid.codeid,))
                existing_row = cursor.fetchone()
                if existing_row is None:
                    raise RuntimeError(f"CodeID {validated_codeid.codeid} was not found after insert attempt.")
                existing_id = existing_row[0]
                if verbose >= 2:
                    print(i18n._("INFO_CODEID_EXIST").format(codeid=codeid, id=existing_id))
                return existing_id, False
        except ValidationError as e:
            print(i18n._("PGSQL-VAL-COD-ERR").format(e=e))
            raise
        except Exception as e:
            pg_conn.rollback()
            print(i18n._("PGSQL-INS-COD-ERR").format(e=e))
            raise

    def update_codeid_seen_at(
        self,
        codeid_id: int,
        first_seen_at: str | pd.Timestamp | datetime.datetime,
        last_seen_at: str | pd.Timestamp | datetime.datetime,
    ) -> None:
        """Update codeid first_seen_at and last_seen_at using min/max semantics."""
        first_seen = ensure_utc(first_seen_at)
        last_seen = ensure_utc(last_seen_at)

        pg_conn = self._require_pg_conn()
        with pg_conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE codeids
                SET first_seen_at = LEAST(COALESCE(first_seen_at, %s), %s),
                    last_seen_at = GREATEST(COALESCE(last_seen_at, %s), %s)
                WHERE id = %s
                """,
                (first_seen, first_seen, last_seen, last_seen, codeid_id),
            )
            if getattr(cursor, "rowcount", None) == 0:
                raise RuntimeError(f"CodeID id {codeid_id} does not exist.")
            pg_conn.commit()

    def transform_activityleg(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform raw leg-segment data into the schema expected by `activity_leg`.

        Args:
            data: DataFrame containing raw activity-leg segments.

        Returns:
            DataFrame normalized to the `activity_leg` storage schema.
        """
        def get_codeid_id_from_db(codeid: str) -> int:
            """Resolve the PostgreSQL ID associated with a CodeID value.

            Args:
                codeid: CodeID string.

            Returns:
                Integer identifier from the `codeids` table.
            """    
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute("SELECT id FROM codeids WHERE codeid = %s;", (codeid,))
                fetchone_result = cursor.fetchone()
                if fetchone_result is None:
                    raise RuntimeError(f"CodeID {codeid} was not found in PostgreSQL.")
                return fetchone_result[0] 
        
        work = data.copy()
        work['start_time'] = work['time_from'].apply(lambda x: x.isoformat())
        work['end_time'] = work['time_until'].apply(lambda x: x.isoformat())
        work['codeid_id'] = work['CodeID'].apply(get_codeid_id_from_db)
        work['duration'] = (work['time_until'] - work['time_from']).dt.total_seconds()
        work.rename(columns={'DeviceName': 'device_name', 'Foot': 'foot'}, inplace=True)

        output_columns = [
            "codeid_id",
            "foot",
            "start_time",
            "end_time",
            "duration",
            "mac",
            "device_name",
            "total_value",
        ]
        transformed_data = work.drop(columns=["time_from", "time_until", "CodeID"])
        return transformed_data[output_columns]
        
    
    def _insert_row_returning_id(self, cursor, table_name: str, row: dict[str, Any]) -> int:
        """Insert one row safely into a table and return the generated ID.

        Args:
            cursor: Open PostgreSQL cursor.
            table_name: Destination table name.
            row: Row values to insert.

        Returns:
            Inserted row ID.

        Raises:
            RuntimeError: If the insert operation does not return an ID.
        """
        column_names = list(row.keys())
        query = sql.SQL(
            "INSERT INTO {table} ({fields}) VALUES ({values}) RETURNING id"
        ).format(
            table=sql.Identifier(table_name),
            fields=sql.SQL(", ").join(sql.Identifier(col) for col in column_names),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in column_names),
        )
        cursor.execute(query, tuple(row[col] for col in column_names))
        result = cursor.fetchone()
        if result is None:
            raise RuntimeError(f"Insert into {table_name} did not return an id.")
        return result[0]

    def _find_existing_row_id(self, cursor, table_name: str, row: dict[str, Any]) -> int | None:
        """Find an equivalent existing row for idempotent tables.

        Args:
            cursor: Open PostgreSQL cursor.
            table_name: Table to search.
            row: Candidate row values.

        Returns:
            Existing row ID if found, otherwise ``None``.
        """
        if table_name == "activity_leg":
            cursor.execute(
                """
                SELECT id
                FROM activity_leg
                WHERE codeid_id IS NOT DISTINCT FROM %s
                  AND foot IS NOT DISTINCT FROM %s
                  AND start_time IS NOT DISTINCT FROM %s
                  AND end_time IS NOT DISTINCT FROM %s
                  AND duration IS NOT DISTINCT FROM %s
                  AND mac IS NOT DISTINCT FROM %s
                  AND device_name IS NOT DISTINCT FROM %s
                  AND total_value IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (
                    row["codeid_id"],
                    row["foot"],
                    row["start_time"],
                    row["end_time"],
                    row["duration"],
                    row.get("mac"),
                    row.get("device_name"),
                    row.get("total_value"),
                ),
            )
        elif table_name == "activity_all":
            cursor.execute(
                """
                SELECT id
                FROM activity_all
                WHERE codeid_ids IS NOT DISTINCT FROM %s
                  AND codeleg_ids IS NOT DISTINCT FROM %s
                  AND start_time IS NOT DISTINCT FROM %s
                  AND end_time IS NOT DISTINCT FROM %s
                  AND duration IS NOT DISTINCT FROM %s
                  AND macs IS NOT DISTINCT FROM %s
                  AND device_names IS NOT DISTINCT FROM %s
                  AND active_legs IS NOT DISTINCT FROM %s
                  AND is_effective IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (
                    row["codeid_ids"],
                    row["codeleg_ids"],
                    row["start_time"],
                    row["end_time"],
                    row["duration"],
                    row.get("macs"),
                    row.get("device_names"),
                    row.get("active_legs"),
                    row.get("is_effective"),
                ),
            )
        elif table_name == "effective_movement":
            cursor.execute(
                """
                SELECT id
                FROM effective_movement
                WHERE codeid_id IS NOT DISTINCT FROM %s
                  AND start_time IS NOT DISTINCT FROM %s
                  AND end_time IS NOT DISTINCT FROM %s
                  AND duration IS NOT DISTINCT FROM %s
                  AND leg IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (
                    row["codeid_id"],
                    row["start_time"],
                    row["end_time"],
                    row["duration"],
                    row["leg"],
                ),
            )
        elif table_name == "effective_gait":
            cursor.execute(
                """
                SELECT id
                FROM effective_gait
                WHERE codeid_id IS NOT DISTINCT FROM %s
                  AND start_time IS NOT DISTINCT FROM %s
                  AND end_time IS NOT DISTINCT FROM %s
                  AND duration IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (
                    row["codeid_id"],
                    row["start_time"],
                    row["end_time"],
                    row["duration"],
                ),
            )
        else:
            return None

        result = cursor.fetchone()
        return result[0] if result else None

    def _upsert_like_row_returning_id(self, cursor, table_name: str, row: dict[str, Any]) -> int:
        """Reuse an existing row ID when possible, otherwise insert a new row.

        Args:
            cursor: Open PostgreSQL cursor.
            table_name: Destination table name.
            row: Candidate row values.

        Returns:
            Existing or newly inserted row ID.
        """
        existing_id = self._find_existing_row_id(cursor, table_name, row)
        if existing_id is not None:
            if table_name == "effective_gait":
                self._update_effective_gait_row(cursor, existing_id, row)
            return existing_id
        return self._insert_row_returning_id(cursor, table_name, row)


    def store_data(self, table_name: str, data: pd.DataFrame, verbose: int = 1) -> list[int]:
        """Validate and store rows into a PostgreSQL table.

        Args:
            table_name: Destination table name.
            data: DataFrame of rows to validate and store.
            verbose: Verbosity level for console output.

        Returns:
            List of inserted or reused row IDs.
        """
        if data.empty:
            if verbose > 0:
                print(i18n._("PGSQL-INS-TAB-NOD-ERR").format(table_name=table_name))
            return []

        try:
            if verbose > 0:
                print(i18n._("PGSQL-INS-TAB-INFO").format(table_name=table_name))

            data_to_store = data.copy()

            if "start_time" in data_to_store.columns:
                data_to_store["start_time"] = data_to_store["start_time"].astype(str)
            if "end_time" in data_to_store.columns:
                data_to_store["end_time"] = data_to_store["end_time"].astype(str)

            validated_rows = []
            for _, row in data_to_store.iterrows():
                row_dict = row.to_dict()

                if table_name == "activity_leg":
                    validated_rows.append(ActivityLeg(**row_dict).model_dump())

                elif table_name == "effective_movement":
                    validated_rows.append(EffectiveMovement(**row_dict).model_dump())

                elif table_name == "activity_all":
                    if "codeleg_ids" in row_dict:
                        row_dict["codeleg_ids"] = [
                            -1 if v is None else int(v) for v in row_dict["codeleg_ids"]
                        ]
                    validated_rows.append(ActivityAll(**row_dict).model_dump())

                elif table_name == "fullref_sensor_codeid":
                    validated_rows.append(ActivitySegment(**row_dict).model_dump())

                elif table_name == "effective_gait":
                    validated_rows.append(EffectiveGait(**row_dict).model_dump())

                elif table_name == "codeids":
                    validated_rows.append(CodeID(**row_dict).model_dump())

                else:
                    raise ValueError(i18n._("ERR_UNKNOWN_TABLE").format(table=table_name))

            inserted_ids: list[int] = []

            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                for row in validated_rows:
                    if table_name in {"activity_leg", "activity_all", "effective_movement", "effective_gait"}:
                        row_id = self._upsert_like_row_returning_id(cursor, table_name, row)
                    else:
                        row_id = self._insert_row_returning_id(cursor, table_name, row)

                    inserted_ids.append(row_id)

                pg_conn.commit()

            if verbose > 0:
                print(i18n._("PGSQL-INS-TAB-OK").format(table_name=table_name))
            if verbose > 1:
                print(i18n._("PGSQL-LST-INS").format(ids=inserted_ids))

            return inserted_ids

        except ValidationError as e:
            print(i18n._("PGSQL-VAL-TAB-ERR").format(e=e))
            return []
        except Exception as e:
            pg_conn.rollback()
            print(i18n._("PGSQL-INS-TAB-ERR").format(e=e))
            return []


    def get_real_codeid(self, codeid_id: int) -> str:
        """Retrieve the CodeID string associated with a numeric PostgreSQL ID.

        Args:
            codeid_id: Numeric ID stored in the `codeids` table.

        Returns:
            CodeID string associated with that identifier.

        Raises:
            ValueError: If the given ID does not exist in the `codeids` table.
        """
        try:
            query = "SELECT codeid FROM codeids WHERE id = %s;"
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(query, (codeid_id,))
                result = cursor.fetchone()
                if result:
                    return result[0]  
                else:
                    raise ValueError(i18n._("ERR_CODEID_NOT_FOUND").format(id=codeid_id))
        except Exception as e:
            print(i18n._("PGSQL-QRY-COD-ERR").format(e=e))
            raise
    
    def get_codeid_id_by_value(self, codeid: str) -> int | None:
        """Retrieve the numeric PostgreSQL ID associated with a CodeID string.

        Args:
            codeid: CodeID string stored in the `codeids` table.

        Returns:
            Integer ID if found, otherwise ``None``.
        """
        try:
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM codeids WHERE codeid = %s;",
                    (codeid,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(i18n._("PGSQL-QRY-COD-ERR").format(e=e))
            raise

    def get_record_all_legs(self, clegs: set, clname: str = "codeleg_ids") -> pd.DataFrame:
        """Retrieve `activity_all` rows matching a set of array-valued leg references.

        Args:
            clegs: Set of leg-reference arrays to match.
            clname: Name of the PostgreSQL array column to compare against.

        Returns:
            DataFrame containing the matching `activity_all` rows.

        Raises:
            ValueError: If no matching rows are found.
        """
        try:
            array_literals = [sql.SQL("ARRAY[{}]").format(
                    sql.SQL(', ').join(map(sql.Literal, pair))
                ) for pair in clegs]

            # Build ARRAY[...] literals for the IN clause
            in_clause = sql.SQL(', ').join(array_literals)
            query = sql.SQL("SELECT * FROM activity_all WHERE {} IN ({})").format(
                sql.Identifier(clname),in_clause)
            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
                if result:
                    if cursor.description is None:
                        raise RuntimeError("Query did not return a description.")
                    columns = [desc[0] for desc in cursor.description]
                    df = pd.DataFrame(result, columns=columns)
                    # Due to the lack of TZ info we must change 
                    for col in df.columns:
                        if isinstance(df[col].dtype, DatetimeTZDtype):
                            df[col] = df[col].dt.tz_localize(None)
                    return df
                else:
                    raise ValueError(i18n._("PGSQL-QRY-CLNAME-NONE").format(clname=clname,clegs=clegs))
        except Exception as e:
            print(i18n._("PGSQL-QRY-COD-ERR").format(e=e))
            raise

    def get_activity_ids_by_start_date_range(
        self,
        start_datetime: str | datetime.datetime,
        end_datetime: str | datetime.datetime
    ) -> list[int]:
        """Return distinct `activity_all` IDs whose start time falls inside a range.

        Args:
            start_datetime: Start of the time window as string or datetime.
            end_datetime: End of the time window as string or datetime.

        Returns:
            Sorted list of matching `activity_all.id` values.
        """
        try:
            sdt = ensure_utc(start_datetime)  # → aware UTC datetime
            edt = ensure_utc(end_datetime)

            pg_conn = self._require_pg_conn()
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT id
                    FROM activity_all
                    WHERE start_time >= %s AND start_time <= %s
                    ORDER BY id
                    """,
                    (sdt, edt),
                )
                rows = cur.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            return []    
        
    def _update_effective_gait_row(
        self,
        cursor,
        row_id: int,
        row: dict[str, Any]
    ) -> None:
        """Update GPS enrichment fields for an existing `effective_gait` row."""
        cursor.execute(
            """
            UPDATE effective_gait
            SET gait_confidence_level = %s,
                gps_points = %s,
                gps_distance_m = %s,
                gps_elapsed_sec = %s,
                gps_avg_speed_m_s = %s,
                gps_validated = %s
            WHERE id = %s
            """,
            (
                row.get("gait_confidence_level"),
                row.get("gps_points"),
                row.get("gps_distance_m"),
                row.get("gps_elapsed_sec"),
                row.get("gps_avg_speed_m_s"),
                row.get("gps_validated"),
                row_id,
            ),
        )
