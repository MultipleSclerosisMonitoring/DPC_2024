import pandas as pd
from influxdb_client import InfluxDBClient
import psycopg2
import yaml
from msTools.models import CodeID, ActivityLeg, ActivityAll
from msTools import i18n
from msGait.models import EffectiveMovement, ActivitySegment
from pydantic import ValidationError
from typing import List, Dict
import datetime


class DataManager:
    def __init__(self, config_path: str)->None:
        """
        Inicializa el DataManager con las conexiones a InfluxDB y PostgreSQL.
        
        :param config_path: Ruta del archivo YAML con la configuración.
        :type config_path: str
        """
        self.config = self.load_config(config_path)

        # Configurar PostgreSQL
        self.pg_conn = self._connect_postgresql()

        # Configurar InfluxDB
        self.influxdb_client = InfluxDBClient(
            url=self.config["influxdb"]["url"],
            token=self.config["influxdb"]["token"],
            org=self.config["influxdb"]["org"],
            timeout=self.config["influxdb"]["timeout"]
        )
        self.bucket: str = self.config["influxdb"]["bucket"]
        self.measurement: str = self.config['influxdb']['measurement']

    def __del__(self)-> None:
        self.close_influxdb()
        self.close_pg()

    def load_config(self, config_path: str) -> Dict:
        """
        Carga la configuración desde un archivo YAML.

        :param config_path: Ruta al archivo YAML.
        :type config_path: str
        :return: Diccionario con la configuración.
        :rtype: dict
        """
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
        
    def get_config(self, sect:str) -> Dict:
        """
        Returns loaded config section kept in sect.

        :param sect: Section interesting inside config.
        :type sect: str
        :return: Dictionary with the section data
        :rtype: dict
        """
        if sect in self.config.keys():
            return self.config[sect]
        else:
            return None

    def _connect_postgresql(self) -> psycopg2.extensions.connection:
        """
        Establece una conexión con PostgreSQL.

        :return: Objeto de conexión de PostgreSQL.
        :rtype: object
        """
        try:
            return psycopg2.connect(
                host=self.config["postgresql"]["host"],
                database=self.config["postgresql"]["database"],
                user=self.config["postgresql"]["user"],
                password=self.config["postgresql"]["password"]
            )
        except psycopg2.OperationalError as e:
            print(i18n._("PGSQL-CONN-ERR").format(e=e))
            raise

    def close_pg(self) -> None:
        self.pg_conn.close()

    def close_influxdb(self) -> None:
        self.influxdb_client.close()

    def get_influx_client(self) -> InfluxDBClient:
        """
        Devuelve el cliente de InfluxDB.
        
        :return: Objeto cliente de InfluxDB.
        :rtype: object
        """
        return self.influxdb_client

    def check_and_create_tables(self, sql_file_path: str) -> None:
        """
        Comprueba si las tablas necesarias existen en PostgreSQL y las crea si no existen.

        :param sql_file_path: Ruta al archivo SQL con las definiciones de las tablas.
        :type sql_file_path: str
        """
        try:
            required_tables = [
                "codeids", "effective_movement", "activity_leg", "activity_all"
            ]  # Tablas actualizadas

            with self.pg_conn.cursor() as cursor:
                for table_name in required_tables:
                    cursor.execute(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        );
                    """)
                    exists = cursor.fetchone()[0]
                    if not exists:
                        print(f"Creando tabla '{table_name}' desde {sql_file_path}...")
                        with open(sql_file_path, "r", encoding="utf-8") as sql_file:
                            sql_script = sql_file.read()
                            cursor.execute(sql_script)
                            self.pg_conn.commit()
                    else:
                        print(f"Tabla '{table_name}' ya existe.")
        except Exception as e:
            self.pg_conn.rollback()
            print(i18n._("PGSQL-TAB-ERR").format(e=e))
            raise

    def get_codeids_in_range(self, start_datetime: str, end_datetime: str) -> List[str]:
        """
        Obtiene los CodeIDs únicos en un rango de fechas desde InfluxDB.
        
        :param start_datetime: Fecha y hora de inicio en formato string.
        :param end_datetime: Fecha y hora de fin en formato string.
        :return: Lista de CodeIDs únicos.
        :rtype: list[str]
        """
        try:
            # Verificar zona horaria antes de localización/conversión
            start_datetime = pd.to_datetime(start_datetime)
            if start_datetime.tzinfo is None:
                start_datetime = start_datetime.tz_localize("UTC")
            start_datetime = start_datetime.tz_convert("UTC").isoformat().replace("+00:00", "Z")

            end_datetime = pd.to_datetime(end_datetime)
            if end_datetime.tzinfo is None:
                end_datetime = end_datetime.tz_localize("UTC")
            end_datetime = end_datetime.tz_convert("UTC").isoformat().replace("+00:00", "Z")

            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: {start_datetime}, stop: {end_datetime})
                |> filter(fn: (r) => r._measurement == "{self.measurement}")
                |> keep(columns: ["CodeID"])
                |> distinct()
            '''
            
            query_api = self.influxdb_client.query_api()
            result = query_api.query(query, org=self.config['influxdb']['org'])
            return [record['CodeID'] for table in result for record in table.records]
        except Exception as e:
            print(i18n._("INFL-QRY-COD-ERR").format(e=e))
            return []
        

    def fetch_data(self, query: str) -> pd.DataFrame:
        """
        Ejecuta una consulta SQL en PostgreSQL y devuelve los resultados como un DataFrame.

        :param query: Consulta SQL a ejecutar.
        :return: DataFrame con los resultados de la consulta.
        :rtype: pd.DataFrame
        """
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]  # Obtener nombres de columnas
                data = cursor.fetchall()  # Obtener datos
                return pd.DataFrame(data, columns=columns)
        except Exception as e:
            print(i18n._("PGSQL-QRY-GEN-ERR").format(e=e))
            raise

    def recover_activity_all(self, act: pd.DataFrame, vb: int = 0) -> pd.DataFrame:
        """
        To complete the act DataFrame with the CodeID.

        :param act: Structure with start_time, end_time, Foot, codeid_id.
        :return: DataFrame with the same data plus the CodeID.
        :rtype: pd.DataFrame
        """
        # Cover rows with preparation for 
        activity_leg_like = []
        for _, row in act.iterrows():
            if vb > 1:
                print(i18n._("VB_REG_ACT_ALL").format(row=row))
            for i, foot in enumerate(row["active_legs"]):
                sql = "SELECT codeid from codeids where id='" + \
                    str(row["codeid_ids"][i]) + "'"
                cid = self.fetch_data(sql)
                activity_leg_like.append({
                    "start_time": row["start_time"], "end_time": row["end_time"],
                    "codeid_id": row["codeid_ids"][i], "CodeID": cid['codeid'][0],
                    "foot": foot})
        df_legs = pd.DataFrame(activity_leg_like)
        if vb > 0:
            print(i18n._("VB-ACT-ALL-LEGS").format(ns=df_legs.shape[0]))
        return df_legs


    def store_codeid(self, codeid: str) -> int:
        """
        Almacena un CodeID único en la tabla codeids y devuelve su ID.

        :param codeid: El CodeID a almacenar.
        :return: ID del CodeID en la tabla.
        :rtype: int
        """
        try:
            # Validar el CodeID usando Pydantic
            validated_codeid = CodeID(codeid=codeid)

            with self.pg_conn.cursor() as cursor:
                # Intentar insertar el codeid
                cursor.execute(
                    "INSERT INTO codeids (codeid) VALUES (%s) ON CONFLICT (codeid) DO NOTHING RETURNING id;",
                    (validated_codeid.codeid,)
                )
                result = cursor.fetchone()
                if result:
                    self.pg_conn.commit()
                    return result[0]  # Devuelve el ID recién creado
                # Si ya existe, buscar el ID
                cursor.execute("SELECT id FROM codeids WHERE codeid = %s;", (validated_codeid.codeid,))
                return cursor.fetchone()[0]  # Devuelve el ID existente
        except ValidationError as e:
            # print()
            print(i18n._("PGSQL-VAL-COD-ERR").format(e=e))
            raise
        except Exception as e:
            self.pg_conn.rollback()
            print(i18n._("PGSQL-INS-COD-ERR").format(e=e))
            raise

    def transform_activityleg(self, data:pd.DataFrame) -> pd.DataFrame:
        """
        Transforms a pandas DataFrame moving time columns to ISO string,
        and CodeID to codeid_id by quering the codeids table.

        :param data:  Activity_Leg pandas.
        :type data: pd.DataFrame
        :return: Updated Activity Leg pandas
        :rtype: pd.DataFrame
        """
        def get_codeid_id_from_db(codeid:str) -> int:
            """
            find the codeid_id by quering the codeids table matching CodeID.

            :param codeid:  CodeID string
            :type data: str
            :return: Id in table codeids
            :rtype: int
            """        
            with self.pg_conn.cursor() as cursor:
                # Si ya existe, buscar el ID
                cursor.execute("SELECT id FROM codeids WHERE codeid = %s;", (codeid,))
                return cursor.fetchone()[0]  # Devuelve el ID existente
        #
        data['start_time'] = data['time_from'].apply(lambda x: x.isoformat())
        data['end_time'] = data['time_until'].apply(lambda x: x.isoformat())
        data['codeid_id'] = data['CodeID'].apply(get_codeid_id_from_db)
        data['duration'] = (data['time_until']-data['time_from']).dt.total_seconds()
        lnom = ['codeid_id','foot','start_time','end_time','duration','mac',\
                'device_name','total_value']
        data.rename(columns={'DeviceName':'device_name','Foot':'foot'}, inplace=True)
        ddat = data.drop(columns=['time_from','time_until','CodeID'])
        return ddat[lnom]
        
    def store_data(self, table_name: str, data: pd.DataFrame) -> None:
        """
        Almacena datos en una tabla específica en PostgreSQL, validando 
                los datos con pydantic.

        :param table_name: Nombre de la tabla.
        :param data: DataFrame con los datos a almacenar.
        """
        if data.empty:
            print(i18n._("PGSQL-INS-TAB-NOD-ERR").format(table_name=table_name))
            return

        try:
            print(i18n._("PGSQL-INS-TAB-INFO"))

            # Convertir columnas a cadenas si es necesario
            if "start_time" in data.columns:
                data["start_time"] = data["start_time"].astype(str)
            if "end_time" in data.columns:
                data["end_time"] = data["end_time"].astype(str)

            # Validar los datos
            validated_rows = []
            for _, row in data.iterrows():
                if table_name == "activity_leg":
                    validated_rows.append(ActivityLeg(**row.to_dict()).dict())
                elif table_name == "effective_movement":
                    validated_rows.append(EffectiveMovement(**row.to_dict()).dict())
                elif table_name == "activity_all":
                    row_dict = row.to_dict()
                    
                    # Normalizamos los codeleg_ids: reemplazamos None por -1
                    if "codeleg_ids" in row_dict:
                        row_dict["codeleg_ids"] = [
                            -1 if v is None else int(v) for v in row_dict["codeleg_ids"]
                        ]
                    
                    validated_rows.append(ActivityAll(**row_dict).dict())

                elif table_name == "fullref_sensor_codeid":
                    validated_rows.append(ActivitySegment(**row.to_dict()).dict())
                else:
                    raise ValueError(f"Tabla no reconocida: {table_name}")

            # Guardar en PostgreSQL
            inserted_ids = [] # List of inserted activity_leg IDs
            with self.pg_conn.cursor() as cursor:
                for row in validated_rows:
                    columns = ', '.join(row.keys())
                    placeholders = ', '.join(['%s'] * len(row))
                    sql = f"INSERT INTO {table_name} ({columns}) VALUES " + \
                          f"({placeholders}) RETURNING id"
                    cursor.execute(sql, tuple(row.values()))
                    inserted_id = cursor.fetchone()[0]  # Obtaining the inserted ID
                    inserted_ids.append(inserted_id)
                self.pg_conn.commit()
                print(i18n._("PGSQL-INS-TAB-OK").format(table_name=table_name))
                return inserted_ids
        except ValidationError as e:
            print(i18n._("PGSQL-VAL-TAB-ERR").format(e=e))
        except Exception as e:
            self.pg_conn.rollback()
            print(i18n._("PGSQL-INS-TAB-ERR").format(e=e))


    def get_real_codeid(self, codeid_id: int) -> str:
        """
        Obtiene el verdadero CodeID desde PostgreSQL dado un ID de la tabla codeids.

        :param codeid_id: ID del CodeID en la tabla codeids.
        :return: El verdadero CodeID como string.
        :rtype: str
        """
        try:
            query = "SELECT codeid FROM codeids WHERE id = %s;"
            with self.pg_conn.cursor() as cursor:
                cursor.execute(query, (codeid_id,))
                result = cursor.fetchone()
                if result:
                    return result[0]  # Devuelve el CodeID
                else:
                    raise ValueError(f"No se encontró CodeID para id {codeid_id}.")
        except Exception as e:
            print(i18n._("PGSQL-QRY-COD-ERR").format(e=e))
            raise

