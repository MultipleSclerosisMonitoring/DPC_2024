import pandas as pd
from datetime import datetime
from pydantic import ValidationError
from msTools.data_manager import DataManager
from msTools.models import ActivityLeg, ActivityAll
from msGait.models import ActivitySegment

class CodeIDProcessor:
    def __init__(self, data_manager: DataManager):
        """
        Inicializa el procesador de CodeIDs.

        :param data_manager: Objeto DataManager para interacciones con PostgreSQL.
        :type data_manager: object
        """
        self.data_manager = data_manager
        self.influx_client = data_manager.get_influx_client()
        self.bucket = data_manager.bucket

    def fetch_codeid_data(self, codeid: str, start_datetime: datetime, end_datetime: datetime) -> pd.DataFrame:
        """
        Obtiene datos de InfluxDB asociados a un CodeID específico.

        :param codeid: Identificador único del CodeID.
        :type codeid: str
        :param start_datetime: Inicio del rango de tiempo.
        :type start_datetime: str
        :param end_datetime: Fin del rango de tiempo.
        :type end_datetime: str
        :return: DataFrame con los datos asociados.
        :rtype: pd.DataFrame
        """
        # Verificar si las fechas ya tienen información de zona horaria
        if start_datetime.tzinfo is None:
            start_datetime = pd.to_datetime(start_datetime).tz_localize("UTC")
        else:
            start_datetime = pd.to_datetime(start_datetime).tz_convert("UTC")

        if end_datetime.tzinfo is None:
            end_datetime = pd.to_datetime(end_datetime).tz_localize("UTC")
        else:
            end_datetime = pd.to_datetime(end_datetime).tz_convert("UTC")

        # Convertir las fechas a UTC y formato ISO 8601
        start_datetime = start_datetime.isoformat().replace("+00:00", "Z")
        end_datetime = end_datetime.isoformat().replace("+00:00", "Z")
        
        query_api = self.influx_client.query_api()
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start_datetime}, stop: {end_datetime})
            |> filter(fn: (r) => r["CodeID"] == "{codeid}" and r["_field"] == "Ax")
            |> aggregateWindow(every: 1m, fn: count, createEmpty: false)
            |> keep(columns: ["_time", "CodeID", "_field", "_value", "Foot", "lat", "lng", "mac", "DeviceName"])
        '''

        try:
            result = query_api.query(org=self.data_manager.config['influxdb']['org'], query=query)
            data = [record.values for table in result for record in table.records]
            df = pd.DataFrame(data).sort_values('_time')
            if df.empty:
                print(f"No se encontraron datos para CodeID {codeid}.")
            else:
                print(f"Datos recuperados para CodeID {codeid}: {len(df)} filas.")
            return df
        except Exception as e:
            print(f"Error al consultar datos de InfluxDB para CodeID {codeid}: {e}")
            return pd.DataFrame()

    def identify_activity_segments(self, df: pd.DataFrame, threshold_seconds: float = 70, \
                    foot:str = 'Left') -> pd.DataFrame:
        """
        Identifica segmentos contiguos de datos basados en un umbral de tiempo.

        :param df: DataFrame con datos filtrados por CodeID.
        :type df: pd.DataFrame
        :param threshold_seconds: Umbral en segundos para identificar saltos.
        :type threshold_seconds: float
        :param foot: Left o Right, la pierna de interés.
        :type foot: str
        :return: DataFrame con columnas ['codeid_id', 'foot', 'device_name', 'mac', 'start_time', 'end_time'].
        :rtype: pd.DataFrame
        """
        def grouping(df: pd.DataFrame, threshold_seconds: float) -> pd.DataFrame :
            """
            Crea los grupos contiguos de _time y DeviceName

            Args:
                df (pd.DataFrame): Resultado de Numero de registros por segundo de DeviceName
                delta (int): Número de segundos que define los grupos

            Returns:
                pd.DataFrame: Estructura con las marcas de tiempo desde / hasta de cada grupo
            """
            df = df.assign(_time_diff= df['_time'].diff().dt.total_seconds())

            # Identificar los grupos donde la diferencia es mayor a 80 segundos o el 'DeviceName' cambia
            df= df.assign(group = ((df['_time_diff'] > threshold_seconds) | \
                            (df['DeviceName'] != df['DeviceName'].shift())).cumsum())

            # Generar el nuevo dataframe con los grupos y los valores 'time_from' y 'time_until'
            result_df = df.groupby('group').agg(
                time_from=pd.NamedAgg(column='_time', aggfunc='first'),
                time_until=pd.NamedAgg(column='_time', aggfunc='last'),
                CodeID=pd.NamedAgg(column='CodeID', aggfunc='first'),
                DeviceName=pd.NamedAgg(column='DeviceName', aggfunc='first'),
                Foot=pd.NamedAgg(column='Foot', aggfunc='first'),
                total_value=pd.NamedAgg(column='_value', aggfunc='sum'),
                mac=pd.NamedAgg(column='mac', aggfunc='first')
            ).reset_index(drop=True)

            # Eliminar la columna de diferencias temporales y el identificador de grupo del dataframe original
            df = df.drop(columns=['_time_diff', 'group'])            
            return(result_df)
        
        if df.empty:
            print("No se encontraron datos en el DataFrame proporcionado.")
            return pd.DataFrame(columns=["codeid_id", "foot", "device_name", "mac", "start_time", "end_time"])

        # Verificar si '_time' ya tiene zona horaria antes de localización
        if not pd.api.types.is_datetime64_any_dtype(df["_time"]):
            df["_time"] = pd.to_datetime(df["_time"])
            if df["_time"].dt.tz is None:
                df["_time"] = df["_time"].dt.tz_localize("Europe/Madrid")
            # df["_time"] = df["_time"].dt.tz_convert("UTC")

        df  = df.drop(columns=['result','table','_field','lng','lat']).sort_values("_time")
        dfF = df.loc[df['Foot']==foot,:]
        
        dfFg= grouping(dfF, threshold_seconds)
        return(dfFg)
    
    def inter_segs(self,sg1:pd.DataFrame,sg2:pd.DataFrame)->pd.DataFrame:
        """
        Calcula la intersección de registros from/until

        Args:
            sg1 (pd.DataFrame): DataFrame de pie Derecho
            sg2 (pd.DataFrame): DataFrame de pie Izquierdo

        Returns:
            pd.DataFrame: DataFrame con las intersecciones
        """
        def is_intersection(row):
            return (
                row['time_from_1'] <= row['time_until_2'] and
                row['time_from_2'] <= row['time_until_1']
            )
        # Calcular los límites reales de la intersección
        def calculate_intersection(row):
            return pd.Series({
                'time_from': max(row['time_from_1'], row['time_from_2']),
                'time_until': min(row['time_until_1'], row['time_until_2'])
            })        
        sg1 = sg1.reset_index().rename(columns={'index':'R1_id'})
        sg2 = sg2.reset_index().rename(columns={'index':'R2_id'})
        # Realizar un producto cartesiano entre los DataFrames
        cross_join = sg1.merge(sg2, how='cross', suffixes=('_1', '_2'))        
        # Filtrar las filas donde los segmentos de tiempo se solapan
        cross_join['intersects'] = cross_join.apply(is_intersection, axis=1)
        # Filtrar solo las filas con intersección
        intersections = cross_join[cross_join['intersects']]
        # Calcular los valores de la intersección para las columnas time_from y time_until
        intersections.loc[:,['time_from', 'time_until']] = intersections.apply( \
                            calculate_intersection, axis=1)
        # Crear el DataFrame con las columnas solicitadas
        if intersections.shape[0] > 0:
            result_df = intersections[['time_from', 'time_until', 'R1_id', 'R2_id', \
                    'codeid_id_1','codeid_id_2']]
            result_df = result_df.reset_index(drop=True)
            return result_df
        else:
            return None

    def merge_activity_legs_to_all(self, act_segR: pd.DataFrame, act_segL: pd.DataFrame, \
                                    inter: pd.DataFrame) -> pd.DataFrame:
        """
        Combina las ventanas de actividad de ambas piernas (derecha e izquierda) desde activity_leg 
        para identificar períodos de actividad sincronizada y los almacena en activity_all.

        :param act_segR: DataFrame de la actividad del pie Derecho.
        :type act_segR: pd.DataFrame
        :param act_segL: DataFrame de la actividad del pie Izquierdo.
        :type act_segL: pd.DataFrame
        :param inter: DataFrame con la intersección entre act_segR y act_segL
        :type inter: pd.DataFrame
        :return: DataFrame con toda la información integrada para inyectar en PostGresQL
        :rtype: pd.DataFrame
        """
        # Función para convertir el campo mac al formato deseado
        def format_mac(address):
            # Extraer el texto después del último '-'
            hex_part = address.split('-')[-1]
            # Insertar ':' cada dos caracteres
            formatted_mac = ':'.join(hex_part[i:i+2] for i in range(0, len(hex_part), 2))
            return formatted_mac
        # Combinar res con activity_segR y activity_segL usando los IDs R1_id y R2_id
        result = inter.merge(act_segR[['CodeID', 'device_name', 'foot', \
                                'mac','codeleg_id']],
                        left_on='R1_id',
                        right_index=True,
                        suffixes=('', '_R'))

        result = result.merge(act_segL[['CodeID', 'device_name', 'foot', \
                                'mac','codeleg_id']],
                            left_on='R2_id',
                            right_index=True,
                            suffixes=('_R', '_L'))

        # Seleccionamos las columnas relevantes
        final_result = result[[
            'time_from', 'time_until',
            'CodeID_R', 'device_name_R', 'foot_R', 'mac_R',
            'CodeID_L', 'device_name_L', 'foot_L', 'mac_L',
            'codeid_id_1','codeid_id_2', 'codeleg_id_R','codeleg_id_L'
        ]]
        # Aplicar la función a los campos de mac en el DataFrame
        if sum(final_result['mac_R'].str.contains(':', na=False)) == 0:
            final_result = final_result.copy()
            final_result.loc[:,'mac_R'] = final_result['mac_R'].apply(format_mac)
        if sum(final_result['mac_L'].str.contains(':', na=False)) == 0:
            final_result = final_result.copy()
            final_result.loc[:,'mac_L'] = final_result['mac_L'].apply(format_mac)
        final_result = final_result.copy()
        final_result.loc[:,'is_effective'] = False
        final_result['duration'] = (final_result['time_until'] - \
                                    final_result['time_from']).dt.total_seconds()
        # Crear la nueva columna 'macs' como una lista con los valores de 'mac_L' y 'mac_R'
        final_result['macs'] = final_result.apply(lambda row: [row['mac_L'], \
                                row['mac_R']], axis=1)
        final_result['codeid_ids'] = final_result.apply(lambda row: [row['codeid_id_2'], \
                                row['codeid_id_1']], axis=1)
        final_result['codeleg_ids'] = final_result.apply(lambda row: [row['codeleg_id_L'], \
                                row['codeleg_id_R']], axis=1)
        final_result['device_names'] = final_result.apply(lambda row: [ \
                                row['device_name_L'], row['device_name_R']], axis=1)
        final_result['active_legs'] = final_result.apply(lambda row: [row['foot_L'], \
                                row['foot_R']], axis=1)
        final_result.rename(columns={'time_from': 'start_time', \
                                     'time_until': 'end_time'}, inplace=True)
        final_result.drop(columns=['CodeID_R', 'device_name_R', 'foot_R', \
                'mac_R', 'CodeID_L', 'device_name_L', 'foot_L', 'mac_L', \
                'codeleg_id_L','codeleg_id_R'],inplace=True)
        return(final_result)

    def save_to_postgresql(self, table_name: str, df: pd.DataFrame)->None:
        """
        Guarda datos procesados en una tabla de PostgreSQL.

        :param table_name: Nombre de la tabla.
        :type table_name: str
        :param df: DataFrame con los datos a guardar.
        :type df: pd.DataFrame
        """
        if df.empty:
            print(f"No hay datos para guardar en {table_name}.")
            return

        try:
            self.data_manager.store_data(table_name, df)
        except Exception as e:
            print(f"Error al guardar los datos en la tabla {table_name}: {e}")


