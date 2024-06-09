""" script for writing data from snowflake table"""
import sys
import logging
import os
from datetime import datetime
import importlib
import json
import sqlalchemy
import numpy as np
from snowflake.connector.errors import ProgrammingError


module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_snowflake = getattr(module, "establish_conn_for_snowflake")

task_logger = logging.getLogger('task_logger')
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
SNOWFLAKE_LOG_STATEMENT = "snowflake ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"
DUPLICATE_COLUMNS = 'duplicate column name'
SCHEMA_NOT_FOUND = "schema %s does not exist."


def db_table_exists(sessions: dict, database: str, schema: str, tablename: str)-> bool:
    """ function for checking whether a table exists or not in snowflake """
    try:
        # checking whether the table exists in database or not
        sql = sqlalchemy.text(f"select table_schema, table_name from {database}.information_schema"\
        f".tables where table_name ='{tablename.upper()}'  and table_schema = '{schema.upper()}'")
        task_logger.info(sql)
        connection = sessions.connection()
        result = connection.execute(sql)
        return bool(result.rowcount)
    except sqlalchemy.err.OperationalError as error:
        task_logger.exception("Schema name not present in the db: %s",str(error))
        raise error
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def is_nested_json_column(series):
    """Check if all elements in the series are either dictionaries or lists"""
    return all(isinstance(item, (dict, list)) for item in series)

def insert_data(conn_details,dataframe,sessions,target,schema_name):
    """function for inserting df data in to table"""
    try:
        connection = sessions.connection()
        json_columns = [col for col in dataframe.columns if is_nested_json_column(dataframe[col])]
        for col in json_columns:
            dataframe[col] = dataframe[col].apply(json.dumps)
        for col in dataframe.columns:
            if dataframe[col].dtype == 'object':
                # Convert object datatype columns to string
                dataframe[col] = dataframe[col].astype(str)
            elif dataframe[col].dtype == 'float64' or dataframe[col].dtype == 'float32':
                # If column is of float datatype, handle NaN and infinite values
                dataframe[col].fillna(0, inplace=True)
                dataframe[col] = dataframe[col].replace([np.inf, -np.inf], 0)
                # Convert to integer if appropriate
                dataframe[col] = dataframe[col].astype(int)
            elif dataframe[col].dtype == 'uniqueidentifier':
                # Convert uniqueidentifier datatype to VARCHAR
                dataframe[col] = dataframe[col].astype(str)

        dtype_dict = {col: sqlalchemy.types.JSON for col in json_columns}
        if target["audit_fields"] == "YES":
            dataframe['CRTD_BY']=conn_details["username"]
            dataframe['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            dataframe['UPDT_BY']= " "
            dataframe['UPDT_DTTM']= " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql(target["object_name"].lower(), connection, schema = schema_name,
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(SNOWFLAKE_LOG_STATEMENT)
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql(target["object_name"].lower(), connection, schema = schema_name,
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(SNOWFLAKE_LOG_STATEMENT)
    except sqlalchemy.exc.ProgrammingError as e:
        if DUPLICATE_COLUMNS in str(e):
            task_logger.error("there are duplicate column names in the target table %s",str(e))
            sys.exit()
        else:
            task_logger.error(SCHEMA_NOT_FOUND,schema_name)
            sys.exit()
    except Exception as e:
        task_logger.info("error occured in insert_data function %s", str(e))
        raise e

def create(conn, dataframe,conn_details:str,target)-> bool:
    """if table is not present , it will create"""
    try:
        schema_name =target['database_name']+'.'+ target["schema_name"].lower()
        if db_table_exists(conn, target['database_name'], target["schema_name"].
            lower(),target["object_name"].lower()) is False:
            task_logger.info('%s does not exists so creating a new table',
            target["object_name"].lower())
            insert_data(conn_details,dataframe,conn,target,schema_name)
        else:
            task_logger.info('%s already exists, so appending data to the same table',
            target["object_name"].lower())
            insert_data(conn_details,dataframe,conn,target,schema_name)
    except sqlalchemy.exc.ProgrammingError as error:
        if DUPLICATE_COLUMNS in str(error):
            task_logger.error("Duplicate column names in the target table")
            sys.exit()
        else:
            task_logger.info("else")
            task_logger.exception("create() is %s", str(error))
            raise error

def append(conn: dict, dataframe, conn_details,target) -> bool:
    """if table exists, it will append"""
    try:
        if db_table_exists(conn, target["database_name"], target["schema_name"].lower(),
             target["object_name"].lower()) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["object_name"].lower())
            schema_name =target['database_name']+'.'+ target["schema_name"].lower()
            insert_data(conn_details,dataframe,conn,target,schema_name)
        else:
            task_logger.error('%s does not exists, so create table first',
            target["object_name"].lower())
            return False
    except ProgrammingError:
        task_logger.error("audit columns not found in the table previously to append")
        return False

def replace(conn: dict, dataframe,counter: int, conn_details,target) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        if db_table_exists(conn, target["database_name"], target["schema_name"].lower(),
            target["object_name"].lower()) is True:
            schema_name =target['database_name']+'.'+ target["schema_name"].lower()
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                target["object_name"].lower())
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{schema_name}.{target["object_name"].lower()}')
                conn.execute(replace_query)
                task_logger.info(" table replace finished, started inserting data into "
                 "%s table", target["object_name"].lower())
                insert_data(conn_details,dataframe,conn,target,schema_name)
            else:
                insert_data(conn_details,dataframe,conn,target,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to drop',
            target["object_name"].lower())
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error

def truncate(conn: dict,dataframe,counter: int, conn_details,target) -> bool:
    """if table exists, it will truncate"""
    try:
        if db_table_exists(conn, target["database_name"], target["schema_name"].lower(),
             target["object_name"].lower()) is True:
            schema_name =target['database_name']+'.'+ target["schema_name"].lower()
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["object_name"].lower())
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{schema_name}.{target["object_name"].lower()}')
                conn.execute(truncate_query)
                task_logger.info("snowflake truncating table finished, started inserting data into "
                "table :%s", target["object_name"].lower())
                insert_data(conn_details,dataframe,conn,target,schema_name)
            else:
                insert_data(conn_details,dataframe,conn,target,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            target["object_name"].lower())
            return False
    except ProgrammingError as error:
        if 'column "inserted_by" of relation' in str(error):
            task_logger.error("audit columns not found in the table previously to insert data")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error

def trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,
    iter_value,audit,target,group_no,subtask_no):
    """function to get target record count"""
    if target["action_on_table"] != "drop" and status is not False:
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',datafram.shape[0],
        iter_value,group_no,subtask_no)
        task_logger.info('the number of records ingested in target table:%s',
        datafram.shape[0])

def write(json_data,datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions,subtask_target_section,group_no,subtask_no) -> bool:
    """ function for ingesting data to snowflake based on the operation in json"""
    try:
        target = subtask_target_section
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to snowflake db initiated")
        _ ,conn_details = establish_conn_for_snowflake(json_data, 'target',
         config_file_path,paths_data)
        # Remove spaces on the right of column names
        datafram = datafram.rename(columns=lambda x: str(x).strip())
        status="Pass"
        if target["action_on_table"] == "CREATE IF NOT EXIST":
            if counter == 1:
                create(sessions, datafram, conn_details,target)
            else:
                status=append(sessions, datafram,conn_details,target)
        elif target["action_on_table"] == "INSERT":
            status=append(sessions, datafram,conn_details,target)
        elif target["action_on_table"] == "TRUNCATE AND LOAD":
            status=truncate(sessions, datafram, counter,conn_details,target)
        elif target["action_on_table"] == "DROP AND CREATE":
            status=replace(sessions, datafram, counter,conn_details,target)
        elif target["action_on_table"] not in ("CREATE IF NOT EXIST", "INSERT",
            "TRUNCATE AND LOAD","DROP AND CREATE","UPSERT"):
            task_logger.error("give propper input for action_on_table condition")
            status = False
        trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,
        iter_value,audit,target,group_no,subtask_no)
        return status
    except ProgrammingError as e:
        snowflake_error = e.orig
        if snowflake_error.errno == 2025 and DUPLICATE_COLUMNS in str(snowflake_error):
            task_logger.error("there are duplicate column names in the target table")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error("there are duplicate column names in the target table")
        sys.exit()
    except sqlalchemy.exc.ProgrammingError as error:
        schema_name =target["schema_name"]
        if error.orig.args[0] == 2003:
            task_logger.error(SCHEMA_NOT_FOUND,schema_name)
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error(SCHEMA_NOT_FOUND,schema_name)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("ingest_data_to_snowflake() is %s", str(error))
        raise error
