from __future__ import annotations

"""Fast CodeID inventory synchronization from InfluxDB into PostgreSQL.

This module provides a cron-friendly command that scans one or more InfluxDB
buckets for recently seen ``CodeID`` values and registers them in PostgreSQL.

The command is intentionally narrower than ``find_mscodeids``:

- it does **not** build semantic segments
- it does **not** populate ``activity_leg`` or ``activity_all``
- it does **not** run movement or gait detection

Instead, it offers a lightweight inventory layer whose main purpose is to make
newly observed ``CodeID`` values visible quickly, for example in Grafana or in
operational dashboards.

The implementation is designed to live comfortably inside this repository's
runtime model:

- configuration is loaded through :mod:`msTools.settings`
- timestamps are normalized with :func:`msTools.timeutils.ensure_utc`
- database access uses the PostgreSQL settings already declared in
  ``config.yaml`` / ``.env``
- only dependencies already declared by the project are used

The target table is ``codeids`` by default. The command always requires a
``codeid`` column and can optionally take advantage of the following inventory
columns when they exist:

- ``type``
- ``bucket``
- ``first_seen_at``
- ``last_seen_at``

This means the script is backward-compatible with the repository's current
minimal ``codeids`` schema while also supporting an enriched inventory schema
if the table is extended later.
"""

import argparse
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2
from influxdb_client import InfluxDBClient
from psycopg2 import sql
from urllib3.exceptions import InsecureRequestWarning

from msTools.settings import AppConfig, get_runtime_config_path, load_app_config
from msTools.timeutils import ensure_utc


DEFAULT_KNOWN_BUCKET_MEASUREMENTS: dict[str, list[str]] = {
    "Gait/autogen": ["Gait"],
    "MbientLab/autogen": [
        "Accel",
        "Altitude",
        "Gyro",
        "Illumination",
        "Magnetometer",
        "MetaWear",
    ],
    "SmartBand/autogen": ["BloodP", "Heart", "Steps"],
}


class VAction(argparse.Action):
    """Implement an argparse verbosity flag compatible with ``-v`` repetition.

    The action accepts any of the following forms:

    - ``-v``
    - ``-vv``
    - ``-v 2``

    Attributes:
        values: Accumulated verbosity level.
    """

    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        nargs: str | int | None = None,
        const: Any | None = None,
        default: Any | None = None,
        type: Any | None = None,
        choices: Any | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ) -> None:
        """Initialize the cumulative verbosity action.

        Args:
            option_strings: Command-line option names handled by the action.
            dest: Namespace attribute receiving the parsed value.
            nargs: Standard argparse ``nargs`` parameter.
            const: Standard argparse ``const`` parameter.
            default: Standard argparse ``default`` parameter.
            type: Standard argparse ``type`` parameter.
            choices: Standard argparse ``choices`` parameter.
            required: Standard argparse ``required`` parameter.
            help: Standard argparse help message.
            metavar: Standard argparse metavar specification.
        """
        super().__init__(
            option_strings,
            dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )
        self.values = 0

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | None,
        option_string: str | None = None,
    ) -> None:
        """Store the parsed verbosity level in the target namespace.

        Args:
            parser: Active argument parser.
            namespace: Parsed namespace being populated.
            values: Optional explicit verbosity value.
            option_string: Concrete option that triggered the action.
        """
        if values is None:
            self.values += 1
        else:
            self.values = int(values)
        setattr(namespace, self.dest, self.values)


@dataclass(slots=True)
class InventoryRecord:
    """One inventory observation recovered from InfluxDB.

    The dataclass stores the normalized CodeID value, optional Influx-side
    ``type`` metadata, the source bucket, and the UTC timestamp associated with
    the current synchronization run.
    """

    codeid: str
    token_type: str | None
    bucket: str
    seen_at: datetime


@dataclass(slots=True)
class SyncStats:
    """Execution summary for one synchronization run.

    The counters separate scanned inventory rows from inserted, updated,
    unchanged, and anomalous outcomes so that cron logs remain auditable.
    """

    scanned_records: int = 0
    inserted_codeids: int = 0
    updated_codeids: int = 0
    unchanged_codeids: int = 0
    anomalies: int = 0


class InfluxCodeIDInventory:
    """Read lightweight CodeID inventory data from one or more Influx buckets.

    The class reuses the connection parameters from the repository's validated
    application settings, while allowing the caller to query multiple buckets.
    """

    def __init__(self, settings: AppConfig) -> None:
        """Create a reusable InfluxDB client from repository settings.

        Args:
            settings: Validated repository settings.
        """
        self.settings = settings
        verify_ssl = bool(settings.influxdb.verify)
        if not verify_ssl:
            # Cron-oriented runs may intentionally use a non-verified internal
            # TLS endpoint; hide the repetitive urllib3 noise while keeping the
            # connection behavior unchanged.
            warnings.filterwarnings(
                "ignore",
                category=InsecureRequestWarning,
            )
        self.client = InfluxDBClient(
            url=settings.influxdb.url,
            token=settings.influxdb.token,
            org=settings.influxdb.org,
            timeout=settings.influxdb.timeout,
            verify_ssl=verify_ssl,
        )

    def close(self) -> None:
        """Close the underlying InfluxDB client."""
        self.client.close()

    def fetch_records(
        self,
        bucket_measurements: dict[str, list[str]],
        start_time: datetime,
        end_time: datetime,
        *,
        verbose: int = 0,
    ) -> list[InventoryRecord]:
        """Fetch distinct inventory records from InfluxDB.

        Args:
            bucket_measurements: Mapping from bucket name to the list of
                measurements that should be scanned inside that bucket.
            start_time: Inclusive UTC start timestamp.
            end_time: Exclusive UTC end timestamp.
            verbose: Verbosity level for progress output.

        Returns:
            Deduplicated inventory observations across all requested buckets.
        """
        start_iso = pd.Timestamp(start_time).isoformat().replace("+00:00", "Z")
        end_iso = pd.Timestamp(end_time).isoformat().replace("+00:00", "Z")
        query_api = self.client.query_api()

        records_by_key: dict[tuple[str, str | None, str], InventoryRecord] = {}
        seen_at = pd.Timestamp.now("UTC").to_pydatetime()

        for bucket, measurements in bucket_measurements.items():
            if verbose >= 1:
                print(
                    f"[check_user_tokens_multi] Scanning bucket={bucket!r} "
                    f"measurements={measurements} from {start_iso} to {end_iso}."
                )

            for measurement in measurements:
                query = """
                from(bucket: "{bucket}")
                    |> range(start: {start_iso}, stop: {end_iso})
                    |> filter(fn: (r) => r._measurement == "{measurement}")
                    |> filter(fn: (r) => exists r.CodeID)
                    |> keyValues(keyColumns: ["CodeID"])
                    |> group()
                    |> keep(columns: ["CodeID", "type"])
                """.format(
                    bucket=bucket,
                    start_iso=start_iso,
                    end_iso=end_iso,
                    measurement=measurement,
                )
                result = query_api.query(org=self.settings.influxdb.org, query=query)

                for table in result:
                    for row in table.records:
                        codeid = row.values.get("CodeID")
                        if codeid in (None, ""):
                            continue
                        token_type = row.values.get("type")
                        key = (
                            str(codeid),
                            None if token_type in (None, "") else str(token_type),
                            bucket,
                        )
                        records_by_key[key] = InventoryRecord(
                            codeid=str(codeid),
                            token_type=None if token_type in (None, "") else str(token_type),
                            bucket=bucket,
                            seen_at=seen_at,
                        )

        return sorted(
            records_by_key.values(),
            key=lambda item: (item.codeid, item.bucket, item.token_type or ""),
        )


class PostgresCodeIDInventoryStore:
    """Persist CodeID inventory information into the repository database.

    The store follows the repository's preferred semantics for ``codeids``:
    ``codeid`` remains the primary identity. ``type`` and ``bucket`` are
    treated as optional inventory metadata.

    If an existing ``codeid`` row already stores non-null metadata and the new
    observation conflicts with it, the store records an anomaly instead of
    creating another ``codeids`` row.
    """

    def __init__(self, settings: AppConfig, table_name: str = "codeids") -> None:
        """Open a PostgreSQL connection using repository settings.

        Args:
            settings: Validated repository settings.
            table_name: Destination table, defaulting to ``codeids``.
        """
        self.settings = settings
        self.table_name = table_name
        self.connection = psycopg2.connect(
            host=settings.postgresql.host,
            port=settings.postgresql.port,
            database=settings.postgresql.database,
            user=settings.postgresql.user,
            password=settings.postgresql.password,
            options="-c timezone=UTC",
        )

    def close(self) -> None:
        """Close the PostgreSQL connection."""
        if getattr(self.connection, "closed", 1) == 0:
            self.connection.close()

    def _table_columns(self, cursor) -> set[str]:
        """Return the existing column names of the destination table.

        Args:
            cursor: Open PostgreSQL cursor.

        Returns:
            Set of column names present in the destination table.
        """
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            (self.table_name,),
        )
        return {str(row[0]) for row in cursor.fetchall()}

    def _fetch_existing_rows(
        self,
        cursor,
        codeids: list[str],
        available_columns: set[str],
    ) -> dict[str, dict[str, Any]]:
        """Fetch existing rows for a set of CodeIDs.

        Args:
            cursor: Open PostgreSQL cursor.
            codeids: CodeIDs that may need to be inserted or updated.
            available_columns: Columns available in the target table.

        Returns:
            Mapping from ``codeid`` to the row metadata already stored.
        """
        select_columns = ["id", "codeid"]
        for optional_column in ("type", "bucket", "first_seen_at", "last_seen_at"):
            if optional_column in available_columns:
                select_columns.append(optional_column)

        query = sql.SQL("SELECT {fields} FROM {table} WHERE codeid = ANY(%s)").format(
            fields=sql.SQL(", ").join(sql.Identifier(name) for name in select_columns),
            table=sql.Identifier(self.table_name),
        )
        cursor.execute(query, (codeids,))

        existing: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            row_dict = dict(zip(select_columns, row, strict=True))
            existing[str(row_dict["codeid"])] = row_dict
        return existing

    def sync_records(
        self,
        records: list[InventoryRecord],
        *,
        dry_run: bool = False,
        fail_on_anomaly: bool = False,
        verbose: int = 0,
    ) -> SyncStats:
        """Synchronize CodeID inventory records into PostgreSQL.

        Args:
            records: Inventory observations to store.
            dry_run: When ``True``, compute the full plan without modifying the
                database.
            fail_on_anomaly: When ``True``, abort the synchronization when a
                metadata conflict is detected for an existing ``codeid``.
            verbose: Verbosity level for progress output.

        Returns:
            Execution statistics summarizing the synchronization outcome.

        Raises:
            RuntimeError: If the target table does not contain a ``codeid``
                column or if ``fail_on_anomaly`` is enabled and a conflict is
                detected.
        """
        stats = SyncStats(scanned_records=len(records))
        if not records:
            return stats

        deduplicated_by_codeid: dict[str, InventoryRecord] = {}
        intra_run_anomalies: list[str] = []
        for record in records:
            current = deduplicated_by_codeid.get(record.codeid)
            if current is None:
                deduplicated_by_codeid[record.codeid] = record
                continue
            if current.token_type != record.token_type or current.bucket != record.bucket:
                intra_run_anomalies.append(
                    "Intra-run metadata conflict for codeid={codeid}: "
                    "({type_a}, {bucket_a}) vs ({type_b}, {bucket_b})".format(
                        codeid=record.codeid,
                        type_a=current.token_type,
                        bucket_a=current.bucket,
                        type_b=record.token_type,
                        bucket_b=record.bucket,
                    )
                )

        with self.connection.cursor() as cursor:
            available_columns = self._table_columns(cursor)
            if "codeid" not in available_columns:
                raise RuntimeError(
                    f"Target table {self.table_name!r} does not contain a 'codeid' column."
                )

            existing_rows = self._fetch_existing_rows(
                cursor,
                list(deduplicated_by_codeid.keys()),
                available_columns,
            )

            anomaly_messages = list(intra_run_anomalies)

            for record in deduplicated_by_codeid.values():
                existing = existing_rows.get(record.codeid)
                if existing is None:
                    stats.inserted_codeids += 1
                    if not dry_run:
                        self._insert_new_row(cursor, available_columns, record)
                    continue

                should_update = False
                updates: dict[str, Any] = {}

                if "type" in available_columns:
                    stored_type = existing.get("type")
                    if stored_type in (None, "") and record.token_type not in (None, ""):
                        updates["type"] = record.token_type
                        should_update = True
                    elif (
                        stored_type not in (None, "")
                        and record.token_type not in (None, "")
                        and stored_type != record.token_type
                    ):
                        anomaly_messages.append(
                            f"Conflicting type for codeid={record.codeid}: stored={stored_type!r}, incoming={record.token_type!r}."
                        )

                if "bucket" in available_columns:
                    stored_bucket = existing.get("bucket")
                    if stored_bucket in (None, "") and record.bucket not in (None, ""):
                        updates["bucket"] = record.bucket
                        should_update = True
                    elif stored_bucket not in (None, "") and stored_bucket != record.bucket:
                        anomaly_messages.append(
                            f"Conflicting bucket for codeid={record.codeid}: stored={stored_bucket!r}, incoming={record.bucket!r}."
                        )

                if "first_seen_at" in available_columns and existing.get("first_seen_at") is None:
                    updates["first_seen_at"] = record.seen_at
                    should_update = True

                if "last_seen_at" in available_columns:
                    stored_last_seen = existing.get("last_seen_at")
                    if stored_last_seen is None or stored_last_seen < record.seen_at:
                        updates["last_seen_at"] = record.seen_at
                        should_update = True

                if should_update:
                    stats.updated_codeids += 1
                    if not dry_run:
                        self._update_existing_row(cursor, existing["id"], updates)
                else:
                    stats.unchanged_codeids += 1

            stats.anomalies = len(anomaly_messages)
            for message in anomaly_messages:
                print(f"[check_user_tokens_multi] WARNING: {message}")

            if fail_on_anomaly and anomaly_messages:
                raise RuntimeError(
                    "Inventory synchronization detected metadata conflicts and fail_on_anomaly was enabled."
                )

            if dry_run:
                self.connection.rollback()
            else:
                self.connection.commit()

        if verbose >= 1:
            print(
                "[check_user_tokens_multi] Sync summary: "
                f"scanned={stats.scanned_records}, inserted={stats.inserted_codeids}, "
                f"updated={stats.updated_codeids}, unchanged={stats.unchanged_codeids}, "
                f"anomalies={stats.anomalies}."
            )

        return stats

    def _insert_new_row(
        self,
        cursor,
        available_columns: set[str],
        record: InventoryRecord,
    ) -> None:
        """Insert one previously unseen ``codeid`` row.

        Args:
            cursor: Open PostgreSQL cursor.
            available_columns: Columns available in the destination table.
            record: Inventory observation being inserted.
        """
        payload: dict[str, Any] = {"codeid": record.codeid}
        if "type" in available_columns:
            payload["type"] = record.token_type
        if "bucket" in available_columns:
            payload["bucket"] = record.bucket
        if "first_seen_at" in available_columns:
            payload["first_seen_at"] = record.seen_at
        if "last_seen_at" in available_columns:
            payload["last_seen_at"] = record.seen_at

        query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({values})").format(
            table=sql.Identifier(self.table_name),
            fields=sql.SQL(", ").join(sql.Identifier(name) for name in payload.keys()),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in payload.keys()),
        )
        cursor.execute(query, tuple(payload.values()))

    def _update_existing_row(self, cursor, row_id: int, updates: dict[str, Any]) -> None:
        """Update one existing ``codeids`` row.

        Args:
            cursor: Open PostgreSQL cursor.
            row_id: Identifier of the row to update.
            updates: Mapping of columns that should be updated.
        """
        if not updates:
            return

        assignments = sql.SQL(", ").join(
            sql.SQL("{column} = %s").format(column=sql.Identifier(column_name))
            for column_name in updates.keys()
        )
        query = sql.SQL("UPDATE {table} SET {assignments} WHERE id = %s").format(
            table=sql.Identifier(self.table_name),
            assignments=assignments,
        )
        cursor.execute(query, tuple(updates.values()) + (row_id,))


def parse_bucket_measurement_mappings(bucket_specs: list[str]) -> dict[str, list[str]]:
    """Parse explicit bucket-to-measurements mappings from the CLI.

    Args:
        bucket_specs: Repeated argument values in the form
            ``bucket=measurement1,measurement2``.

    Returns:
        Mapping from bucket name to measurement list.

    Raises:
        ValueError: If one of the values does not follow the expected syntax.
    """
    mappings: dict[str, list[str]] = {}
    for spec in bucket_specs:
        if "=" not in spec:
            raise ValueError(
                f"Invalid --bucket-measurements value {spec!r}. Expected bucket=measurement1,measurement2"
            )
        bucket, raw_measurements = spec.split("=", 1)
        measurements = [item.strip() for item in raw_measurements.split(",") if item.strip()]
        if not bucket.strip() or not measurements:
            raise ValueError(
                f"Invalid --bucket-measurements value {spec!r}. Bucket and measurements must be non-empty."
            )
        mappings[bucket.strip()] = measurements
    return mappings


def resolve_bucket_measurements(settings: AppConfig, args: argparse.Namespace) -> dict[str, list[str]]:
    """Resolve which buckets and measurements should be scanned.

    Resolution order is intentionally explicit:

    1. repeated ``--bucket-measurements bucket=measurement1,measurement2``
    2. ``--buckets`` using known legacy bucket defaults when available
    3. repository ``config.yaml`` bucket + measurement as a fallback

    Args:
        settings: Validated repository settings.
        args: Parsed CLI arguments.

    Returns:
        Mapping from bucket name to measurements.

    Raises:
        ValueError: If the user requests an unknown bucket without providing a
            measurement mapping.
    """
    explicit_mappings = parse_bucket_measurement_mappings(args.bucket_measurements or [])
    if explicit_mappings:
        return explicit_mappings

    if args.buckets:
        requested_buckets = [item.strip() for item in args.buckets.split(",") if item.strip()]
        resolved: dict[str, list[str]] = {}
        for bucket in requested_buckets:
            if bucket in DEFAULT_KNOWN_BUCKET_MEASUREMENTS:
                resolved[bucket] = DEFAULT_KNOWN_BUCKET_MEASUREMENTS[bucket]
            elif bucket == settings.influxdb.bucket:
                resolved[bucket] = [settings.influxdb.measurement]
            else:
                raise ValueError(
                    f"Unknown bucket {bucket!r}. Provide --bucket-measurements to declare its measurements explicitly."
                )
        return resolved

    return {settings.influxdb.bucket: [settings.influxdb.measurement]}


def resolve_time_window(args: argparse.Namespace) -> tuple[datetime, datetime]:
    """Resolve the Influx query window for the current execution.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Tuple ``(start_time, end_time)`` as UTC-aware ``datetime`` objects.

    Raises:
        ValueError: If the resulting time window is invalid.
    """
    if args.from_date:
        start_time = ensure_utc(args.from_date).to_pydatetime()
    else:
        start_time = (pd.Timestamp.now("UTC") - pd.Timedelta(minutes=args.lookback_minutes)).to_pydatetime()

    if args.until_date:
        end_time = ensure_utc(args.until_date).to_pydatetime()
    else:
        end_time = pd.Timestamp.now("UTC").to_pydatetime()

    if end_time <= start_time:
        raise ValueError(f"Invalid time window: end_time={end_time!r} must be after start_time={start_time!r}.")

    return start_time, end_time


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the inventory synchronization tool.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Scan InfluxDB for recently observed CodeIDs and register them in "
            "PostgreSQL as a lightweight operational inventory."
        )
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        required=False,
        default=None,
        help="Path to config.yaml. If omitted, the repository runtime resolution is used.",
    )
    parser.add_argument(
        "-f",
        "--from",
        dest="from_date",
        required=False,
        help="Inclusive start timestamp. Naive values are interpreted in Europe/Madrid.",
    )
    parser.add_argument(
        "-u",
        "--until",
        dest="until_date",
        required=False,
        help="Exclusive end timestamp. Naive values are interpreted in Europe/Madrid.",
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=15,
        help=(
            "Fallback lookback window used when --from is omitted. "
            "This keeps frequent cron executions lightweight."
        ),
    )
    parser.add_argument(
        "-b",
        "--buckets",
        required=False,
        help=(
            "Comma-separated list of buckets to scan. Known legacy buckets use built-in "
            "measurement defaults; unknown buckets require --bucket-measurements."
        ),
    )
    parser.add_argument(
        "--bucket-measurements",
        action="append",
        default=[],
        help=(
            "Explicit bucket definition in the form bucket=measurement1,measurement2. "
            "This option may be repeated."
        ),
    )
    parser.add_argument(
        "--table",
        default="codeids",
        help="Destination PostgreSQL table. Defaults to codeids.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the synchronization without modifying PostgreSQL.",
    )
    parser.add_argument(
        "--fail-on-anomaly",
        action="store_true",
        help="Abort the run if conflicting inventory metadata is detected for an existing codeid.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        nargs="?",
        action=VAction,
        dest="verbose",
        default=0,
        const=1,
        help="Increase verbosity (for example -v, -vv, or -v 2).",
    )
    return parser


def main() -> None:
    """Run the fast CodeID inventory synchronization command.

    The command intentionally keeps its transactional model simple:

    1. resolve configuration and time window
    2. query InfluxDB for lightweight inventory records
    3. insert or update ``codeids`` metadata in PostgreSQL
    4. report a compact execution summary suitable for cron logs
    """
    parser = build_argument_parser()
    args = parser.parse_args()

    config_path = get_runtime_config_path(args.config_file)
    settings = load_app_config(config_path)
    start_time, end_time = resolve_time_window(args)
    bucket_measurements = resolve_bucket_measurements(settings, args)

    inventory_reader = InfluxCodeIDInventory(settings)
    store = PostgresCodeIDInventoryStore(settings, table_name=args.table)

    try:
        records = inventory_reader.fetch_records(
            bucket_measurements,
            start_time,
            end_time,
            verbose=int(args.verbose or 0),
        )
        stats = store.sync_records(
            records,
            dry_run=args.dry_run,
            fail_on_anomaly=args.fail_on_anomaly,
            verbose=int(args.verbose or 0),
        )
        if int(args.verbose or 0) >= 1:
            print(
                "[check_user_tokens_multi] Completed successfully for window "
                f"{start_time.isoformat()} -> {end_time.isoformat()} with "
                f"{stats.scanned_records} scanned records."
            )
    finally:
        inventory_reader.close()
        store.close()


if __name__ == "__main__":
    main()
