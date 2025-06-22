import argparse
import json
from typing import Optional, List

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


i18n.init_translation('es')  # Inicializa por defecto


def main():
    parser = argparse.ArgumentParser(description=i18n._("ARG_TIT_FIND_GAIT"))
    parser.add_argument("-i", "--ids", dest="act_all_ids", type=json.loads, required=True,
                        help=i18n._("ARG_LIST_ACT_ALL_IDS"))
    # parser.add_argument("-f", "--from", dest="fstart", type=str, default=None,
    #                     help=i18n._("ARG_STR_TIME_FROM"))
    # parser.add_argument("-u", "--until", dest="fend", type=str, default=None,
    #                     help=i18n._("ARG_STR_TIME_UNTIL"))
    parser.add_argument("-c", "--config", dest="config_file", type=str, required=True,
                        help=i18n._("ARG_STR_PATH_YAML"))
    parser.add_argument("-l", "--lang", dest="lng", type=str, default="es",
                        help=i18n._("ARG_STR_LNG"))
    parser.add_argument("-o", "--output", dest="fout", type=str, default=None,
                        help=i18n._("ARG_STR_FOUT"))
    parser.add_argument("-v", "--verbose", action=VAction, nargs="?", default=0, const=1,
                        help=i18n._("ARG_VB_LEVEL"))
    parser.add_argument("--head-rows", dest="head_rows", type=int, default=8,
                        help=i18n._("ARG_HEAD_ROWS"))
    parser.add_argument("--save", dest="save", action="store_true", default=False,
                        help="Guardar resultados en PostgreSQL")
    args = parser.parse_args()
    i18n.init_translation(args.lng)
    
    # Inicializar detector (gestiona internamente DataManager y recuperación de segmentos)
    # Constructor flexible que puede funcionar por ids o por fechas
    detector = MovementDetector(
        config_file   = args.config_file,
        sampling_rate = 50,
        fstart        = None,
        fend          = None,
        ids           = args.act_all_ids,
        verbose       = args.verbose
    )

    # Si no hay piernas, salimos
    if detector.df_legs.empty:
        return

    if args.verbose >= 1:
        print(i18n._("FGAIT_1ST"))

    # Detectar marchas efectivas por pierna
    df_effective = detector.detect_effective_movement(detector.df_legs,
                            nomf=args.fout,vb=args.verbose)
    if df_effective.empty:
        print(i18n._("FGAIT_NO_WALK"))
        return

    if args.verbose >= 2:
        print(i18n._("FGAIT_WKLS_FND"))
        print(df_effective.head(args.head_rows))

    # Guardado o impresión de effective_movement
    if args.save:
        detector.save_to_postgresql("effective_movement", df_effective,vb=args.verbose)
        if args.verbose >= 1:
            print(i18n._("FGAIT_NUM_WALKS").format(ns=len(df_effective)))

    # Detectar periodos de marcha efectiva simultánea (ambos pies)
    df_gait = detector.detect_effective_gait(df_effective,vb=args.verbose)
    if df_gait.empty:
        if args.verbose >= 1:
            print("No se encontraron periodos de marcha efectiva simultánea.")
    else:
        if args.verbose >= 1:
            print("Periodos de marcha efectiva simultánea (ambos pies):")
            if args.verbose >= 2:
                df_string = df_gait.to_string(index=False)
                indentation = "     "  # 5 spaces
                # Divide la cadena en líneas, sangra cada línea y únelas de nuevo
                indented_df_string = "\n".join([indentation + line for line in 
                                                df_string.splitlines()])
                print(indented_df_string)

        if args.save:
            detector.save_to_postgresql("effective_gait", df_gait,vb=args.verbose)
            if args.verbose >= 1:
                print(f"{len(df_gait)} registros de effective_gait guardados")

    if args.verbose >= 1:
        print(i18n._("FGAIT_END"))
    
    detector.close()


if __name__ == "__main__":
    main()