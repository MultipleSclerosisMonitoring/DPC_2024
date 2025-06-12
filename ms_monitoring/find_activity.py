import argparse
import json
from msTools import i18n
from msTools.data_manager import DataManager
from msGait.movement_detector import MovementDetector

class VAction(argparse.Action):
    """
    Clase para manejar el nivel de verbose (-v).
    """
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, getattr(namespace, self.dest) + 1)
        else:
            setattr(namespace, self.dest, int(values))

# Define the language
# idioma_app = os.environ.get('LANG', 'es') # Ex: Get it from the Environment
i18n.init_translation('es') # Inicializa la traducción

def main():
    parser = argparse.ArgumentParser(description=i18n._("ARG_TIT_FIND_GAIT"))
    parser.add_argument("-i", "--ids", dest="act_all_ids", type=json.loads, default=None,
                        help=i18n._("ARG_LIST_ACT_ALL_IDS"))
    parser.add_argument("-f", "--from", dest="fstart", type=str, default=None,
                        help=i18n._("ARG_STR_TIME_FROM"))
    parser.add_argument("-u", "--until", dest="fend", type=str, default=None,
                        help=i18n._("ARG_STR_TIME_UNTIL"))
    parser.add_argument("-c", "--config", dest="config_file", type=str, required=True,
                        help=i18n._("ARG_STR_PATH_YAML"))
    parser.add_argument("-l", "--lang", dest="lng", type=str, default="es",
                        help=i18n._("ARG_STR_LNG"))
    parser.add_argument("-o", "--output", dest="fout", type=str, default=None,
                        help=i18n._("ARG_STR_FOUT"))
    parser.add_argument("-v", "--verbose", action=VAction, nargs="?", default=0, const=1,
                        help=i18n._("ARG_VB_LEVEL"))
    args = parser.parse_args()

    # Inicializar traducción
    i18n.init_translation(args.lng)

    # Determinar lista de IDs a procesar
    if args.act_all_ids is not None:
        act_all_ids = args.act_all_ids
        if args.verbose >= 1:
            print(i18n._("PRCS_LIST_ACT_ALL_IDS"))
    else:
        # Ventana temporal
        if not args.fstart or not args.fend:
            parser.error(i18n._("ERR_MUST_SPECIFY_IDS_OR_TIME_WINDOW"))
        if args.verbose >= 1:
            print(i18n._("PRCS_TIME_WINDOW").format(f=args.fstart, u=args.fend))
        dm = DataManager(config_path=args.config_file)
        df_ids = dm.fetch_data(
            f"SELECT id FROM activity_all WHERE start_time <= '{args.fend}'"
            f" AND end_time >= '{args.fstart}' ORDER BY id;"
        )
        if df_ids.empty:
            print(i18n._("FGAIT_NO_WINS"))
            return
        act_all_ids = df_ids['id'].tolist()

    # Carga de segmentos
    dm = DataManager(config_path=args.config_file)
    ids_str = ', '.join(map(str, act_all_ids))
    query = (
        f"SELECT id, start_time, end_time, duration, codeid_ids, codeleg_ids, active_legs "
        f"FROM activity_all WHERE id IN ({ids_str}) ORDER BY codeid_ids;"
    )
    activity_all = dm.fetch_data(query)
    if activity_all.empty:
        print(i18n._("FGAIT_NO_WINS"))
        return

    df_legs = dm.recover_activity_all(activity_all, args.verbose)

    # Inicializar detector
    detector = MovementDetector(
        data_manager=dm,
        sampling_rate=50,
        sect='movement',
        verbose=args.verbose
    )
    if args.verbose >= 1:
        print(i18n._("FGAIT_1ST"))

    df_effective = detector.detect_effective_movement(df_legs, args.fout, args.verbose)
    if df_effective.empty:
        print(i18n._("FGAIT_NO_WALK"))
        return

    if args.verbose >= 2:
        print(i18n._("FGAIT_WKLS_FND"))
        print(df_effective.head())

    # Guardar en BD
    detector.save_to_postgresql("effective_movement", df_effective)

    if args.verbose >= 1:
        print(i18n._("FGAIT_NUM_WALKS").format(ns=len(df_effective)))
        print(i18n._("FGAIT_END"))

if __name__ == "__main__":
    main()
