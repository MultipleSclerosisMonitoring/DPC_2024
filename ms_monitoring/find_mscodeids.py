import argparse
import pandas as pd
from msTools.data_manager import DataManager
from msCodeID.codeid_processor import CodeIDProcessor
from datetime import datetime, timedelta
import gettext
import os

# Configurar localización
localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locales')
lang = gettext.translation('messages', localedir=localedir, languages=['es'], fallback=True)
lang.install()
_ = lang.gettext

class VAction(argparse.Action):
    """
    Clase para manejar el nivel de verbose (-v).
    """
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, getattr(namespace, self.dest) + 1)
        else:
            setattr(namespace, self.dest, int(values))

def main():
    parser = argparse.ArgumentParser(description=_("Find msCodeIDs and store activity windows into PostgreSQL."))
    parser.add_argument("-f", "--from", dest="from_date", type=str, required=False,
                        help=_("Start datetime (format: 'YYYY-MM-DD HH:MM:SS')."))
    parser.add_argument("-u", "--until", dest="until_date", type=str, required=False,
                        help=_("End datetime (format: 'YYYY-MM-DD HH:MM:SS')."))
    parser.add_argument("-c", "--config", dest="config_file", type=str, required=True,
                        help=_("Path to the configuration file (config.yaml)."))
    parser.add_argument("-v", "--verbose", action=VAction, nargs="?", default=0, const=1,
                        help=_("Verbosity level (0=Silent, 1=Basic, 2=Detailed)."))
    
    args = parser.parse_args()

    # Inicialización del DataManager y CodeIDProcessor
    data_manager = DataManager(config_path=args.config_file)
    codeid_processor = CodeIDProcessor(data_manager)

    # Crear/verificar tablas en PostgreSQL
    if args.verbose >= 1:
        print(_("Creating/verifying necessary tables..."))

    try:
        data_manager.check_and_create_tables("msTools/create_tables.sql")
        if args.verbose >= 1:
            print(_("Tables verified and created if necessary."))
    except Exception as e:
        print(_("Error verifying/creating tables: ") + str(e))
        return

    # Gestión de fechas
    if args.from_date:
        start_datetime = pd.to_datetime(args.from_date)
        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.tz_localize("UTC")
    else:
        start_datetime = datetime.now() - timedelta(days=1)
        start_datetime = pd.to_datetime(start_datetime.replace(hour=0, \
                            minute=0, second=0, microsecond=0))
        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.tz_localize("UTC")

    if args.until_date:
        end_datetime = pd.to_datetime(args.until_date)
        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.tz_localize("UTC")
    else:
        end_datetime = pd.to_datetime(datetime.now())
        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.tz_localize("UTC")

    if end_datetime < start_datetime:
        print(_("Error: End date ({end}) is before start date ({start}).").format(
            end=end_datetime, start=start_datetime))
        return None

    if args.verbose >= 1:
        print(_("Getting msCodeIDs from {start} to {end}...").format(
            start=start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            end=end_datetime.strftime('%Y-%m-%d %H:%M:%S')))
    
    # Obtener CodeIDs en el rango de fechas
    codeids = data_manager.get_codeids_in_range(
        start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        end_datetime.strftime("%Y-%m-%d %H:%M:%S")
    )
    if not codeids:
        print(_("No CodeIDs found."))
        return None

    if args.verbose >= 1:
        print(_("Found {n} different CodeIDs from {start} to {end}.").format(
            n=len(codeids), start=args.from_date, end=args.until_date))

    # Procesar CodeIDs
    for codeid in codeids:
        if args.verbose >= 1:
            print(_("Processing data for CodeID: {codeid}...").format(codeid=codeid))

        # Guardar el CodeID en la base de datos y obtener su ID
        try:
            codeid_id = data_manager.store_codeid(codeid)
            if args.verbose >= 2:
                print(_("CodeID {codeid} stored with ID {id}.").format(codeid=codeid, id=codeid_id))
        except Exception as e:
            print(_("Error storing CodeID {codeid}: {error}").format(codeid=codeid, error=str(e)))
            continue

        # Obtener datos del CodeID desde InfluxDB
        try:
            sensor_data = codeid_processor.fetch_codeid_data(codeid, \
                                start_datetime, end_datetime)
        except Exception as e:
            print(_("Error fetching data for CodeID {codeid}: {error}").format(codeid=codeid, error=str(e)))
            continue

        if sensor_data.empty:
            if args.verbose >= 1:
                print(_("No data found for CodeID: {codeid}.").format(codeid=codeid))
            continue

        if 'Foot' not in sensor_data.columns:  # Accidentally one sensor was declared
            if args.verbose >= 1:
                print(_("Foot field not found in sensor data for CodeID: {codeid}. Dataset size: {size}").format(
                    codeid=codeid, size=len(sensor_data)))
            continue
        # Identificar segmentos de actividad distancia 80seg (almacena en 
        # fullref_sensor_codeid automáticamente)
        try:
            activity_segL = codeid_processor.identify_activity_segments(\
                                sensor_data,80,'Left')
            activity_segR = codeid_processor.identify_activity_segments(\
                                sensor_data,80,'Right')
            # Preparing and accomodating data for postgresql table
            if activity_segL.empty:
                if args.verbose >= 1:
                    print(_("No activity segments identified for CodeID: {codeid}, foot: Left.").format(codeid=codeid))
            else:
                activity_refL = data_manager.transform_activityleg(activity_segL)
            
            if activity_segR.empty:
                if args.verbose >= 1:
                    print(_("No activity segments identified for CodeID: {codeid}, foot: Right.").format(codeid=codeid))
            else:
                activity_refR = data_manager.transform_activityleg(activity_segR)
            # Storing data
            if not activity_segL.empty:
                ids = data_manager.store_data("activity_leg", activity_refL)
                activity_segL['codeleg_id'] = ids
                if args.verbose >= 2:
                    print(_("Activity segments processed and stored ({n} rows):").format(n=len(activity_refL)))
                    print(activity_segL.head())

            if not activity_segR.empty:
                ids = data_manager.store_data("activity_leg", activity_refR)
                activity_segR['codeleg_id'] = ids
                if args.verbose >= 2:
                    print(_("Activity segments processed and stored ({n} rows):").format(n=len(activity_refR)))
                    print(activity_segR.head())

            # Generamos la intersección de las dos piernas
            # Key aspect in hierarchical information structure
            res = codeid_processor.inter_segs(activity_segR,activity_segL)
            if not res.empty:
                dbrg= codeid_processor.merge_activity_legs_to_all(activity_segR,\
                        activity_segL,res)
                data_manager.store_data("activity_all",dbrg)
                if args.verbose >= 2:
                    print(_("Final merged segments stored ({n} rows):").format(n=len(dbrg)))
                    print(dbrg.head())
        except Exception as e:
            print(_("Error processing activity segments for CodeID {codeid}: {error}").format(
                codeid=codeid, error=str(e)))
    #
    if args.verbose >= 1:
        print(_("All CodeIDs processed successfully."))
    #
    del data_manager
    return None


if __name__ == "__main__":
    main()
