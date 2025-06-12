import argparse
import json
import pandas as pd
from msTools import i18n
from msTools.data_manager import DataManager

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
    # Inicializar traducción (por defecto español)
    parser = argparse.ArgumentParser(
        description=i18n._("Utilidad para encontrar segmentos en activity_all que intersectan con una ventana de tiempo")
    )
    parser.add_argument(
        "-f", "--from", dest="fstart", type=str, required=True,
        help=i18n._("Fecha y hora de inicio de la ventana (YYYY-MM-DD HH:MM:SS)")
    )
    parser.add_argument(
        "-u", "--until", dest="fend", type=str, required=True,
        help=i18n._("Fecha y hora de fin de la ventana (YYYY-MM-DD HH:MM:SS)")
    )
    parser.add_argument(
        "-c", "--config", dest="config_file", type=str, required=True,
        help=i18n._("Ruta al archivo YAML de configuración")
    )
    parser.add_argument(
        "-p", "--pattern", dest="pattern", type=str,
        help=i18n._("Patrón (regex) para filtrar los CodeIDs")
    )
    parser.add_argument(
        "-q", "--quiet", dest="quiet", action="store_true",
        help=i18n._("Modo silencioso: sólo devuelve la lista de IDs en JSON")
    )
    parser.add_argument(
        "-v", "--verbose", action=VAction, nargs="?", default=0, const=1,
        help=i18n._("Nivel de verbosidad")
    )
    parser.add_argument(
        "-l", "--lang", dest="lng", type=str,
        help=i18n._("Idioma para la internacionalización (e.g., 'en', 'es')")
    )
    args = parser.parse_args()

    # (Re)inicializar idioma si se indica
    if args.lng:
        i18n.init_translation(args.lng)
    else:
        i18n.init_translation('es')

    # Conectar a la base de datos
    dm = DataManager(config_path=args.config_file)
    start = args.fstart
    end = args.fend
    if args.verbose >= 1:
        print(i18n._("Buscando segmentos en activity_all entre {start} y {end}...").format(start=start, end=end))

    # Obtener segmentos que intersecan la ventana
    query = f"""
        SELECT id, start_time, end_time, duration, codeid_ids
        FROM activity_all
        WHERE start_time <= '{end}'
          AND end_time >= '{start}'
        ORDER BY id;
    """
    df = dm.fetch_data(query)
    if df.empty:
        print(i18n._("No se encontraron segmentos en el rango especificado."))
        return

    # Construir detalle por CodeID
    detalles = []
    for _, row in df.iterrows():
        for cid in row['codeid_ids']:
            codigo = dm.fetch_data(f"SELECT codeid FROM codeids WHERE id = '{cid}'")['codeid'][0]
            detalles.append({
                'id': row['id'],
                'CodeID': codigo,
                'from': row['start_time'],
                'until': row['end_time'],
                'duration': row['duration']
            })
    df_det = pd.DataFrame(detalles)

    # Filtrado regex si se especifica
    if args.pattern:
        df_det = df_det[df_det['CodeID'].str.contains(args.pattern, regex=True)]

    # Salida
    if args.quiet:
        ids = sorted(df_det['id'].unique().tolist())
        print(json.dumps(ids))
    else:
        print(df_det.to_string(index=False))
        unique_ids = sorted(df_det['id'].unique().tolist())
        print(i18n._("IDs encontrados: {ids}").format(ids=unique_ids))

if __name__ == "__main__":
    main()
