""" script for writing data to postgres table"""
import sys
import logging
import os
import json
from datetime import datetime
import importlib
import sqlalchemy
import pandas as pd
from sqlalchemy.exc import OperationalError
import numpy as np

module = importlib.import_module("utility")
update_status_file = getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_oracle = getattr(module, "establish_conn_for_oracle")

task_logger = logging.getLogger('task_logger')
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
ORACLE_LOG_STATEMENT = "oracle ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"

def db_table_exists(sessions: dict, schema: str, tablename: str)-> bool:
    """ function for checking whether a table exists or not in oracle """
    try:
        # checking whether the table exists in database or not
        schema=schema.upper()
        tablename=tablename.upper()
        schema_sql = (f"select owner,table_name from all_tables "
        f"where owner='{schema}'")
        connection = sessions.connection()
        schema_result = pd.read_sql_query(schema_sql, connection)
        if bool(len(schema_result)) == True:
            table_sql = (f"select owner,table_name from all_tables "
            f"where table_name='{tablename}' and owner='{schema}'")
            table_result = pd.read_sql_query(table_sql, connection)
            return bool(len(table_result))
        task_logger.error("schema %s does not exist",schema)
        sys.exit()
    except sqlalchemy.exc.DatabaseError as error:
        if "ORA-12541" in str(error):
            task_logger.error("No Oracle connection: Check the Oracle Listener")
            sys.exit()
        elif "ORA-01918" in str(error):
            task_logger.error("User schema %s does  not exist ",schema)
            sys.exit()
        elif "ORA-00942" in str(error):
            task_logger.error("table or view does not exist ")
            sys.exit()
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def is_nested_json_column(series):
    """Check if all elements in the series are either dictionaries or lists"""
    return all(isinstance(item, (dict, list)) for item in series)

def insert_data(json_data, conn_details, dataframe, sessions):
    """Function for inserting DataFrame data into a table."""
    try:
        target = json_data["task"]["target"]
        connection = sessions.connection()
        json_columns = [col for col in dataframe.columns if is_nested_json_column(dataframe[col])]

        for col in json_columns:
            dataframe[col] = dataframe[col].apply(json.dumps)

        for col in dataframe.columns:
            if len(dataframe[col].apply(type).drop_duplicates().tolist()) > 1:
                dataframe[col] = dataframe[col].astype(str)

        for col in dataframe.select_dtypes(include=['float64', 'float32']).columns:
            dataframe[col].fillna(0, inplace=True)
            dataframe[col] = dataframe[col].replace([np.inf, -np.inf], 0)
            dataframe[col] = dataframe[col].astype(int)

        table_name = target["table_name"].lower()
        

        if target["audit_columns"] == "active":
            dataframe['CRTD_BY'] = conn_details["username"]
            dataframe['CRTD_DTTM'] = datetime.now().strftime(CURRENT_TIMESTAMP)
            dataframe['UPDT_BY'] = " "
            dataframe['UPDT_DTTM'] = " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql(table_name, connection, schema=target["schema"],
            index=False, if_exists="append", dtype={
            sqlalchemy.types.FLOAT(): sqlalchemy.types.Float(precision=53).with_variant(
            sqlalchemy.dialects.oracle.FLOAT(), 'oracle')
                             })
            task_logger.info(ORACLE_LOG_STATEMENT)
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql(table_name, connection, schema=target["schema"],
                             index=False, if_exists="append", dtype={
            sqlalchemy.types.FLOAT(): sqlalchemy.types.Float(precision=53).with_variant(
            sqlalchemy.dialects.oracle.FLOAT(), 'oracle')
                             })
            task_logger.info(ORACLE_LOG_STATEMENT)
    except sqlalchemy.exc.DatabaseError as error:
        if f"ORA-01918: user '{target['schema'].upper()}' does not exist" in str(error):
            task_logger.error("User schema %s does  not exist ",target['schema'])
            sys.exit()
        elif "ORA-00957: duplicate column name" in str(error):
            task_logger.error("there are duplicate column names in the target table")
            sys.exit()
        elif "ORA-01950" in str(error):
            task_logger.error("no privileges on tablespace")
            sys.exit()
        else:
            task_logger.error("An error occurred: %s", str(error))
            raise error
    except sqlalchemy.exc.ProgrammingError as error:
        if 'Incorrect column name' in str(error):
            task_logger.error("error due to incorrect column name %s", str(error))
            sys.exit()
    except Exception as error:
        task_logger.info("error occured in insert_data function %s", str(error))
        raise error

def create(json_data: dict, conn, dataframe,conn_details:str)-> bool:
    """if table is not present , it will create"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"],target["table_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',
            target["table_name"].upper())
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            task_logger.info('%s already exists, so appending data to the existing  table',
            target["table_name"].upper())
            insert_data(json_data,conn_details,dataframe,conn)
    except sqlalchemy.exc.DatabaseError as error:
        error_message = str(error)
        if "ORA-00957: duplicate column name" in error_message:
            task_logger.error("there are duplicate column names in the target table")
            sys.exit()
        else:
            task_logger.exception("create() is %s", str(error))
            raise error

def append(json_data: dict, conn: dict, dataframe, conn_details) -> bool:
    """if table exists, it will append"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"], target["table_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["table_name"].upper())
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            task_logger.error('%s does not exists, so create table first',
            target["table_name"].upper()
            )
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously to append")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error

def replace(json_data: dict, conn: dict, dataframe,counter: int, conn_details) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"], target["table_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                target["table_name"].upper())
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{target["schema"]}.{target["table_name"].upper()}')
                # conn.execution_options(autocommit=False).execute(replace_query)
                conn.execute(replace_query)
                task_logger.info("table replace finished, started inserting data into "
                 "%s table", target["table_name"].upper())
                insert_data(json_data,conn_details,dataframe,conn)
            else:
                insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name',
            target["table_name"].upper())
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error

def truncate(json_data: dict, conn: dict,dataframe,counter: int, conn_details) -> bool:
    """if table exists, it will truncate"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"], target["table_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["table_name"].upper())
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{target["schema"]}.{target["table_name"].upper()}')
                # conn.execution_options(autocommit=True).execute(truncate_query)
                conn.execute(truncate_query)
                task_logger.info("oracle truncating table finished, started inserting data into "
                "table :%s", target["table_name"].upper())
                insert_data(json_data,conn_details,dataframe,conn)
            else:
                insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            target["table_name"].upper())
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously"
            "to insert data after truncate")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error

def trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,iter_value,audit):
    """function to get target record count"""
    if json_data["task"]["target"]["operation"] != "drop" and status is not False:
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',datafram.shape[0],
        iter_value)
        task_logger.info('the number of records ingested in target table:%s',
        datafram.shape[0])

def write(json_data,datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions) -> bool:
    """ function for ingesting data to oracle based on the operation in json"""
    try:
        target = json_data["task"]["target"]
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to oracle db initiated")
        _ ,conn_details = establish_conn_for_oracle(json_data,'target',
                                                     config_file_path,paths_data)
        # Remove spaces on the right of column names
        datafram = datafram.rename(columns=lambda x: str(x).strip())
        status="Pass"
        if target["operation"] == "CREATE IF NOT EXIST":
            if counter == 1:
                create(json_data, sessions, datafram, conn_details)
            else:
                status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "INSERT":
            status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "TRUNCATE AND LOAD":
            status=truncate(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] == "DROP AND CREATE":
            status=replace(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] not in ("CREATE IF NOT EXIST", "INSERT","TRUNCATE AND LOAD",
            "DROP AND CREATE","UPSERT"):
            task_logger.error("give propper input for operation condition")
            status = False
        trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,iter_value,audit)
        return status
    except sqlalchemy.exc.DatabaseError as error:
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED', iter_value)
        task_logger.error("Database error %s",str(error))
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error