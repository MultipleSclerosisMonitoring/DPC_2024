from __future__ import annotations

"""Run the repository's daily semantic pipeline for a closed time window.

This module provides a cron-oriented orchestration command that executes the
blind semantic stages in the intended operational order:

1. run ``find_mscodeids`` for a closed time window
2. resolve the newly relevant ``activity_all`` identifiers for that same window
3. run ``find_gait`` explicitly on those identifiers

The default behavior targets the previous calendar day in ``Europe/Madrid`` so
that recurring executions operate on a stable and auditable closed interval.
Unlike the stage CLIs' convenience defaults, this wrapper always computes and
passes explicit boundaries unless the caller overrides them.

The command is designed for production scheduling:

- deterministic time windows
- explicit subprocess calls using the current Python interpreter
- PostgreSQL-backed retrieval of ``activity_all`` identifiers
- compact progress logging suitable for cron files
- optional dry-run mode that keeps the orchestration intact while delegating
  ``--save 0`` to both processing stages
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from msTools.data_manager import DataManager
from msTools.settings import get_runtime_config_path
from msTools.timeutils import ensure_utc

LOCAL_TZ = ZoneInfo("Europe/Madrid")


class VAction(argparse.Action):
    """Implement an argparse verbosity flag compatible with repeated ``-v``.

    The action accepts ``-v``, ``-vv``, or ``-v 2`` and stores the cumulative
    verbosity level in the destination namespace attribute.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        """Store the parsed verbosity level.

        Args:
            parser: Active argument parser.
            namespace: Parsed namespace being populated.
            values: Optional explicit verbosity value.
            option_string: Concrete option that triggered the action.
        """
        current = getattr(namespace, self.dest, 0)
        if values is None:
            setattr(namespace, self.dest, current + 1)
        else:
            setattr(namespace, self.dest, int(values))


@dataclass(slots=True)
class ClosedWindow:
    """One closed operational window used by the daily wrapper.

    The dataclass keeps the inclusive UTC start, the exclusive UTC end, and a
    human-readable label for progress logging.
    """

    start_utc: datetime
    end_utc: datetime
    label: str


def resolve_closed_window(args: argparse.Namespace) -> ClosedWindow:
    """Resolve the closed processing window for the current execution.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Closed window represented as UTC timestamps.

    Raises:
        ValueError: If the provided arguments define an invalid interval.
    """
    if args.day and (args.from_date or args.until_date):
        raise ValueError("Use either --day or (--from/--until), not both.")

    if args.day:
        day_local = datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
        start_local = day_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    elif args.from_date or args.until_date:
        if not (args.from_date and args.until_date):
            raise ValueError("Both --from and --until are required when overriding the window explicitly.")
        start_utc = ensure_utc(args.from_date).to_pydatetime()
        end_utc = ensure_utc(args.until_date).to_pydatetime()
        if end_utc <= start_utc:
            raise ValueError("The end timestamp must be after the start timestamp.")
        return ClosedWindow(start_utc=start_utc, end_utc=end_utc, label=f"{start_utc.isoformat()} -> {end_utc.isoformat()}")
    else:
        today_local = datetime.now(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = today_local - timedelta(days=1)
        end_local = today_local

    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    label = f"{start_local.date().isoformat()} Europe/Madrid"
    return ClosedWindow(start_utc=start_utc, end_utc=end_utc, label=label)


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the daily pipeline wrapper.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run the daily semantic pipeline on a closed time window: "
            "find_mscodeids first, then find_gait on the matching activity_all IDs."
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
        "--day",
        help="Closed local day to process in YYYY-MM-DD format. Defaults to the previous day in Europe/Madrid.",
    )
    parser.add_argument(
        "-f",
        "--from",
        dest="from_date",
        help="Explicit inclusive start timestamp. Must be combined with --until.",
    )
    parser.add_argument(
        "-u",
        "--until",
        dest="until_date",
        help="Explicit exclusive end timestamp. Must be combined with --from.",
    )
    parser.add_argument(
        "-l",
        "--lang",
        default="en",
        help="Language forwarded to the underlying CLI commands.",
    )
    parser.add_argument(
        "--save",
        type=int,
        choices=[0, 1],
        default=1,
        help="Whether the wrapped stages should persist to PostgreSQL (1) or run in dry mode (0).",
    )
    parser.add_argument(
        "--head-rows",
        type=int,
        default=5,
        help="Preview row count forwarded to the wrapped stage CLIs.",
    )
    parser.add_argument(
        "--gait-batch-size",
        type=int,
        default=250,
        help="Maximum number of activity_all IDs passed to each find_gait subprocess call.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        nargs="?",
        action=VAction,
        default=0,
        const=1,
        help="Increase verbosity (for example -v, -vv, or -v 2).",
    )
    return parser


def chunked(values: list[int], size: int) -> list[list[int]]:
    """Split a list into deterministic consecutive chunks.

    Args:
        values: Values to split.
        size: Maximum chunk size.

    Returns:
        List of sublists preserving the original order.
    """
    return [values[index:index + size] for index in range(0, len(values), size)]


def run_command(command: list[str], *, verbose: int) -> None:
    """Execute one subprocess command and fail fast on errors.

    Args:
        command: Command to execute.
        verbose: Verbosity level for progress output.

    Raises:
        subprocess.CalledProcessError: If the subprocess exits with a non-zero code.
    """
    if verbose >= 1:
        print("[run_daily_pipeline] Running:")
        print("  " + " ".join(command))
    subprocess.run(command, check=True)


def main() -> None:
    """Run the closed-window daily semantic pipeline wrapper."""
    parser = build_argument_parser()
    args = parser.parse_args()

    config_path = get_runtime_config_path(args.config_file)
    window = resolve_closed_window(args)
    start_text = window.start_utc.strftime("%Y-%m-%d %H:%M:%S")
    end_text = window.end_utc.strftime("%Y-%m-%d %H:%M:%S")

    if args.verbose >= 1:
        print(
            f"[run_daily_pipeline] Processing closed window {window.label}: "
            f"{start_text} UTC -> {end_text} UTC."
        )

    stage1_command = [
        sys.executable,
        "-m",
        "ms_monitoring.find_mscodeids",
        "-c",
        config_path,
        "-f",
        start_text,
        "-u",
        end_text,
        "-l",
        args.lang,
        "--save",
        str(args.save),
        "--head-rows",
        str(args.head_rows),
        "-v",
        str(args.verbose),
    ]
    run_command(stage1_command, verbose=args.verbose)

    if args.save == 0:
        if args.verbose >= 1:
            print("[run_daily_pipeline] Dry-run mode: skipping PostgreSQL activity_all lookup and gait stage execution.")
        return

    data_manager = DataManager(config_path=config_path)
    try:
        activity_ids = data_manager.get_activity_ids_by_start_date_range(start_text, end_text)
    finally:
        data_manager.close_all()

    if not activity_ids:
        if args.verbose >= 1:
            print("[run_daily_pipeline] No activity_all IDs found for the closed window. Nothing to send to find_gait.")
        return

    if args.verbose >= 1:
        print(f"[run_daily_pipeline] Retrieved {len(activity_ids)} activity_all IDs for gait processing.")

    for batch_index, batch in enumerate(chunked(activity_ids, args.gait_batch_size), start=1):
        id_list = ",".join(str(item) for item in batch)
        gait_command = [
            sys.executable,
            "-m",
            "ms_monitoring.find_gait",
            "-c",
            config_path,
            "-i",
            id_list,
            "-l",
            args.lang,
            "--save",
            "1",
            "--head-rows",
            str(args.head_rows),
            "-v",
            str(args.verbose),
        ]
        if args.verbose >= 1:
            print(
                f"[run_daily_pipeline] Launching gait batch {batch_index}/{len(chunked(activity_ids, args.gait_batch_size))} "
                f"with {len(batch)} activity_all IDs."
            )
        run_command(gait_command, verbose=args.verbose)

    if args.verbose >= 1:
        print("[run_daily_pipeline] Completed successfully.")


if __name__ == "__main__":
    main()
