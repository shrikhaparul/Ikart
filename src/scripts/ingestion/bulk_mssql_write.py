""" script for writing data from mssql table"""
import sys
import logging
import os
from datetime import datetime
import importlib
from sqlalchemy.exc import OperationalError
import pymssql
import sqlalchemy

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_sqlserver = getattr(module, "establish_conn_for_sqlserver")

task_logger = logging.getLogger('task_logger')
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
MSSQL_LOG_STATEMENT = "mssql ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"

def db_table_exists(sessions: dict, schema: str, tablename: str)-> bool:
    """ function for checking whether a table exists or not in mssql """
    try:
        # checking whether the table exists in database or not
        sql = sqlalchemy.text(f"select table_name from information_schema.tables where "\
        f"table_name='{tablename}' and table_schema='{schema}'")
        connection = sessions.connection()
        result = connection.execute(sql)
        return bool(result.rowcount)
    except sqlalchemy.exc.OperationalError as e:
        if "Unable to connect: Adaptive Server is unavailable or does not exist"in str(e):
            task_logger.error("connection failed,Unable to connect %s",str(e))
        sys.exit()
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def is_nested_json_column(series):
    """Check if all elements in the series are either dictionaries or lists"""
    return all(isinstance(item, (dict, list)) for item in series)

def insert_data(conn_details,dataframe,sessions,target):
    """function for inserting df data in to table"""
    try:
        connection = sessions.connection()
        json_columns = [col for col in dataframe.columns if is_nested_json_column(dataframe[col])]
        dtype_dict = {col: sqlalchemy.types.JSON for col in json_columns}
        if target["audit_fields"] == "YES":
            dataframe['CRTD_BY']=conn_details["username"]
            dataframe['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            dataframe['UPDT_BY']= " "
            dataframe['UPDT_DTTM']= " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql(target["object_name"], connection, schema = target["schema_name"],
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(MSSQL_LOG_STATEMENT)
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql(target["object_name"], connection, schema = target["schema_name"],
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(MSSQL_LOG_STATEMENT)
    except sqlalchemy.exc.OperationalError as e:
        error_message = str(e)
        if 'The specified schema name ' in error_message:
            task_logger.error("The specified schema name does not exist: %s", error_message)
            sys.exit()
        else:
            task_logger.error("Duplicate columns  : %s", error_message)
            raise e
    except Exception as error:
        task_logger.info("error occured in insert_data function %s", str(error))
        raise error


def create(conn, dataframe,conn_details:str,target)-> bool:
    """if table is not present , it will create"""
    try:
        if db_table_exists(conn, target["schema_name"],target["object_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',
            target["object_name"])
            insert_data(conn_details,dataframe,conn,target)
        else:
            task_logger.info('%s already exists, so appending data to the same table',
            target["object_name"])
            insert_data(conn_details,dataframe,conn,target)
    except OperationalError as error:
        if 'Column names in each table must be unique.' in str(error):
            task_logger.error("there are duplicate column names in the target table")
            sys.exit()
        task_logger.exception("create() is %s", str(error))
        raise error

def append(conn: dict, dataframe, conn_details,target) -> bool:
    """if table exists, it will append"""
    try:
        if db_table_exists(conn, target["schema_name"], target["object_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["object_name"])
            insert_data(conn_details,dataframe,conn,target)
        else:
            task_logger.error('%s does not exists, so create table first',
            target["object_name"])
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously to append")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error

def replace(conn: dict, dataframe,counter: int, conn_details,target) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        if db_table_exists(conn, target["schema_name"], target["object_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                target["object_name"])
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{target["schema_name"]}.{target["object_name"]}')
                conn.execute(replace_query)
                task_logger.info(" table replace finished, started inserting data into "
                 "%s table", target["object_name"])
                insert_data(conn_details,dataframe,conn,target)
            else:
                insert_data(conn_details,dataframe,conn,target)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to drop',
            target["object_name"])
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error

def truncate(conn: dict,dataframe,counter: int, conn_details,target) -> bool:
    """if table exists, it will truncate"""
    try:
        if db_table_exists(conn, target["schema_name"], target["object_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["object_name"])
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{target["schema_name"]}.{target["object_name"]}')
                conn.execute(truncate_query)
                task_logger.info("mssql truncating table finished, started inserting data into "
                "table :%s", target["object_name"])
                insert_data(conn_details,dataframe,conn,target)
            else:
                insert_data(conn_details,dataframe,conn,target)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            target["object_name"])
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously"
            "to insert data after truncate")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error


def trgt_record_count(json_data,status,datafram,task_id,run_id,
    paths_data,iter_value,audit,target,group_no,subtask_no):
    """function to get target record count"""
    if target["action_on_table"] != "drop" and status is not False:
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',datafram.shape[0],
        iter_value,group_no,subtask_no)
        task_logger.info('the number of records ingested in target table:%s',
        datafram.shape[0])

def write(json_data,datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions,subtask_target_section,group_no,subtask_no) -> bool:
    """ function for ingesting data to mssql based on the operation in json"""
    try:
        target = subtask_target_section
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to mssql db initiated")
        _ ,conn_details = establish_conn_for_sqlserver(json_data,'target',
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
        trgt_record_count(json_data,status,sessions,task_id,run_id,paths_data,
        iter_value,audit,target,group_no,subtask_no)
        return status
    except pymssql.DatabaseError as e:
        error_message = str(e.args[0]) if len(e.args) > 0 else None
        if error_message:
            task_logger.error("Database Error: %s", error_message)
            sys.exit()
        else:
            task_logger.error("An unknown Database Error occurred")
        task_logger.error("Error reading data from SQL Server")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()
    except OperationalError:
        task_logger.error("connection specified in the task is incorrect")
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED', iter_value)
        sys.exit()
    except Exception as error:
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED', iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
