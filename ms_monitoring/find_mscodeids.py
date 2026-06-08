import argparse
import sys
import pytz
from datetime import datetime, timedelta
import pandas as pd

from msTools import i18n
from msTools.data_manager import DataManager
from msCodeID.codeid_processor import CodeIDProcessor
from msTools.timeutils import ensure_utc


class VAction(argparse.Action):
    """
    Custom argparse Action to handle cumulative verbosity (-v).
    """
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, getattr(namespace, self.dest) + 1)
        else:
            setattr(namespace, self.dest, int(values))


def main() -> None:
    # 1) Pre-parse only -l/--lang (so we don’t show help in the wrong language yet)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument(
        "-l", "--lang", dest="lng", type=str, default="es",
        help="Language: [en|es]"
    )
    pre_args, remaining = pre.parse_known_args()

    # 2) Initialize translation with the chosen language
    i18n.init_translation(pre_args.lng)
    _ = i18n._

    # 3) Build the fully localized ArgumentParser
    parser = argparse.ArgumentParser(
        description=_("DESC_FIND_MSCodeIDs")
    )
    parser.add_argument(
        "-l", "--lang", dest="lng", type=str, default=pre_args.lng,
        help=_("ARG_STR_LNG")
    )
    parser.add_argument(
        "-f", "--from", dest="from_date", metavar="FROM_DATE",
        type=str, required=False, help=_("ARG_STR_TIME_FROM")
    )
    parser.add_argument(
        "-u", "--until", dest="until_date", metavar="UNTIL_DATE",
        type=str, required=False, help=_("ARG_STR_TIME_UNTIL")
    )
    parser.add_argument(
        "-c", "--config", dest="config_file", metavar="CONFIG_FILE",
        type=str, required=True, help=_("ARG_STR_PATH_YAML")
    )
    parser.add_argument(
        "-v", "--verbose", action=VAction, nargs="?", default=0, const=1,
        help=_("ARG_VB_LEVEL")
    )
    parser.add_argument(
        "--head-rows", dest="head_rows", type=int, default=5,
        help=_("ARG_HEAD_ROWS")
    )
    parser.add_argument(
        "--save", dest="save", type=int, choices=[0,1], default=1,
        help=_("ARG_SAVE")
    )

    args = parser.parse_args(remaining)

    # If the user changed -l here, re-initialize translation
    if args.lng != pre_args.lng:
        i18n.init_translation(args.lng)
        _ = i18n._

    # Initialize DataManager and CodeIDProcessor
    data_manager = DataManager(config_path=args.config_file)
    codeid_processor = CodeIDProcessor(data_manager, verbose=args.verbose)

    try:
        # Handle dates using ensure_utc()
        if args.from_date:
            start_datetime = ensure_utc(args.from_date)
        else:
            # default: midnight yesterday
            tmp = datetime.now() - timedelta(days=1)
            tmp = tmp.replace(hour=0, minute=0, second=0, microsecond=0)
            start_datetime = ensure_utc(tmp)

        if args.until_date:
            end_datetime = ensure_utc(args.until_date)
        else:
            end_datetime = ensure_utc(datetime.now(pytz.timezone("Europe/Madrid")))
            end_datetime = ensure_utc(end_datetime)

        # If end is before start, error and exit
        if end_datetime < start_datetime:
            sys.stderr.write(
                _("ERR_END_BEFORE_START")
                .format(end=end_datetime, start=start_datetime)
            )
            sys.exit(1)

        # Verbose info about date range
        if args.verbose >= 1:
            print(
                _("MSG_GET_MSCodeIDs_RANGE")
                .format(
                    start=start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    end=end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                )
            )

        # Fetch CodeIDs in the given date range
        codeids = data_manager.get_codeids_in_range(
            start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            end_datetime.strftime("%Y-%m-%d %H:%M:%S")
        )
        if not codeids:
            print(_("MSG_NO_CODEIDS_FOUND"))
            return

        if args.verbose >= 1:
            print(_("MSG_FOUND_N_CODEIDS").format(
                n=len(codeids),
                start=args.from_date or start_datetime,
                end=args.until_date or end_datetime
            ))

        if args.verbose >= 3:
            print(_("LBL_CODEIDS_HEADER"))
            for cid in codeids:
                print(_("LIST_ITEM_CODEID").format(cid=cid))

        # Process each CodeID
        for codeid in codeids:
            if args.verbose >= 1:
                print(_("MSG_PROCESSING_CODEID").format(codeid=codeid))

            # Store the CodeID in PostgreSQL and get its internal ID
            if args.save == 1:
                try:
                    codeid_id, is_new = data_manager.store_codeid(codeid, args.verbose)
                except Exception as e:
                    print(_("ERR_STORING_CODEID").format(codeid=codeid, error=str(e)))
                    continue
            else:
                # Dry-run mode: do not write to PostgreSQL. Use a placeholder ID.
                codeid_id, is_new = (-1, False)

            # Fetch sensor data for this CodeID
            try:
                sensor_data = codeid_processor.fetch_codeid_data(
                    codeid, start_datetime, end_datetime
                )
            except Exception as e:
                print(_("ERR_FETCH_DATA").format(codeid=codeid, error=str(e)))
                continue

            if sensor_data.empty:
                if args.verbose >= 1:
                    print(_("MSG_NO_DATA_FOR_CODEID").format(codeid=codeid))
                continue

            # Robust check: ensure 'Foot' column is present
            if 'Foot' not in sensor_data.columns:
                print(_("ERR_FOOT_MISSING").format(codeid=codeid), file=sys.stderr)
                continue

            # Identify activity segments with an 80-second gap threshold
            try:
                (
                    activity_segL,
                    activity_segR,
                    activity_segL_merge,
                    activity_segR_merge,
                ) = codeid_processor.build_activity_leg_frames(
                    sensor_data=sensor_data,
                    codeid_id=codeid_id,
                    gap_threshold_seconds=80.0,
                )

                if activity_segL.empty:
                    if args.verbose >= 1:
                        print(_("WARN_NO_SEGMENTS_LEG").format(codeid=codeid, foot='Left'))
                    activity_refL = None
                else:
                    if args.save == 1:
                        activity_refL = data_manager.transform_activityleg(activity_segL)
                    else:
                        activity_refL = None

                if activity_segR.empty:
                    if args.verbose >= 1:
                        print(_("WARN_NO_SEGMENTS_LEG").format(codeid=codeid, foot='Right'))
                    activity_refR = None
                else:
                    if args.save == 1:
                        activity_refR = data_manager.transform_activityleg(activity_segR)
                    else:
                        activity_refR = None

                # Store activity_leg segments
                if not activity_segL.empty:
                    if args.save == 1:
                        ids = data_manager.store_data("activity_leg", activity_refL, verbose=args.verbose)
                        if len(ids) != len(activity_refL):
                            raise RuntimeError("Failed to store all Left activity_leg rows.")
                        n_ref = len(activity_refL)
                    else:
                        ids = list(range(1, len(activity_segL_merge) + 1))
                        n_ref = len(activity_segL_merge)

                    activity_segL_merge['codeleg_id'] = ids

                    if args.verbose >= 2:
                        print(_("INFO_SEGMENTS_STORED").format(n=n_ref))
                        print(activity_segL_merge.head(args.head_rows))

                if not activity_segR.empty:
                    if args.save == 1:
                        ids = data_manager.store_data("activity_leg", activity_refR, verbose=args.verbose)
                        if len(ids) != len(activity_refR):
                            raise RuntimeError("Failed to store all Right activity_leg rows.")
                        n_ref = len(activity_refR)
                    else:
                        ids = list(range(100000, 100000 + len(activity_segR_merge)))
                        n_ref = len(activity_segR_merge)

                    activity_segR_merge['codeleg_id'] = ids

                    if args.verbose >= 2:
                        print(_("INFO_SEGMENTS_STORED").format(n=n_ref))
                        print(activity_segR_merge.head(args.head_rows))

                # Compute intersection between left/right segments
                merged = codeid_processor.build_activity_all_frame(
                    activity_seg_right_merge=activity_segR_merge,
                    activity_seg_left_merge=activity_segL_merge,
                )
                if not merged.empty:
                    if args.save == 1:
                        data_manager.store_data("activity_all", merged, verbose=args.verbose)
                    if args.verbose >= 2:
                        print(_("INFO_MERGED_STORED").format(n=len(merged)))
                        print(merged.head(args.head_rows))

            except Exception as e:
                print(_("ERR_PROCESS_SEGMENTS").format(codeid=codeid, error=str(e)))

        # Final summary
        if args.verbose >= 1:
            print(_("INFO_ALL_PROCESSED"))
    finally:
        data_manager.close_all()

    del data_manager
    return


if __name__ == "__main__":
    main()
