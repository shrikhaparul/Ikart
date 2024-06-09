""" script for writing data to snowflake table"""
import sys
import logging
from datetime import datetime
import importlib
import json
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
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

def db_table_exists(sessions: dict,database: str,schema: str, table_name: str)-> bool:
    """ function for checking whether a table exists or not in snowflake """
    # checking whether the table exists in database or not
    try:
        sql = text(f"select table_schema, table_name from {database}.information_schema.tables "\
        f"where table_name ='{table_name.upper()}'  and table_schema = '{schema}'")
        connection = sessions.connection()
        result = connection.execute(sql)
        return bool(result.rowcount)
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def is_nested_json_column(series):
    """Check if all elements in the series are either dictionaries or lists"""
    return all(isinstance(item, (dict, list)) for item in series)

def insert_data(json_data,conn_details,datafram,sessions,schema_name):
    """function for inserting df data in to table"""
    try:
        json_columns = [col for col in datafram.columns if is_nested_json_column(datafram[col])]
        conn = sessions.connection()
        for col in json_columns:
            datafram[col] = datafram[col].apply(json.dumps)

        table_name = json_data["task"]["target"]["table_name"].lower()
        dtype_dict = {col:sqlalchemy.types.String for col in json_columns}
        if json_data["task"]["target"]["audit_columns"] == "active":
            datafram['CRTD_BY'] = conn_details["username"]
            datafram['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            datafram['UPDT_BY']= " "
            datafram['UPDT_DTTM']= " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            datafram.to_sql(table_name,conn,
            schema = schema_name,index = False, if_exists = "append",dtype = dtype_dict)

            task_logger.info(SNOWFLAKE_LOG_STATEMENT)
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            datafram.to_sql(table_name, conn,
            schema = schema_name,index = False, if_exists = "append",dtype = dtype_dict)
            task_logger.info(SNOWFLAKE_LOG_STATEMENT)
    except sqlalchemy.exc.ProgrammingError as e:
        if DUPLICATE_COLUMNS in str(e):
            task_logger.error("there are duplicate column names in the target table %s",str(e))
            sys.exit()
        else:
            task_logger.error('error %s',str(e))
            sys.exit()
    except Exception as e:
        task_logger.info("error occured in insert_data function %s", str(e))
        raise e


def create(json_data: dict, conn, datafram, conn_details) -> bool:
    """if table is not present , it will create"""
    try:
        schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
        if db_table_exists(conn ,conn_details["database"],json_data["task"]["target"]["schema"],
        json_data["task"]["target"]["table_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',\
            json_data["task"]["target"]["table_name"].upper())
            insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            task_logger.info('%s already exists, so appending the data to the existing table name',
            json_data["task"]["target"]["table_name"].upper())
            insert_data(json_data,conn_details,datafram,conn,schema_name)
    except sqlalchemy.exc.ProgrammingError as error:
        if DUPLICATE_COLUMNS in str(error):
            task_logger.error("Duplicate column names in the target table")
            sys.exit()
        else:
            task_logger.info("else")
            task_logger.exception("create() is %s", str(error))
            raise error

def append(json_data: dict, conn: dict, datafram,conn_details) -> bool:
    """if table exists, it will append"""
    try:
        if db_table_exists(conn,conn_details["database"] ,json_data["task"]["target"]["schema"],
        json_data["task"]["target"]["table_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            json_data["task"]["target"]["table_name"].upper())
            schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
            insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            # create table first or give table name that exists to append data
            task_logger.error('%s does not exists, so create table first',\
            json_data["task"]["target"]["table_name"].upper())
            return False
    except ProgrammingError:
        task_logger.error("audit columns not found in the table previously to append")
        return False

def truncate(json_data: dict, conn: dict,datafram,counter: int, conn_details) -> bool:
    """if table exists, it will truncate"""
    try:
        if db_table_exists(conn,conn_details["database"] , json_data["task"]["target"]["schema"],
            json_data["task"]["target"]["table_name"]) is True:
            schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                json_data["task"]["target"]["table_name"].upper())
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{schema_name}.'
                f'{json_data["task"]["target"]["table_name"].upper()}')
                conn.execute(truncate_query)
                task_logger.info("snowflake truncating table finished, started inserting data into "
                "%s table", json_data["task"]["target"]["table_name"].upper())
                insert_data(json_data,conn_details,datafram,conn,schema_name)
            else:
                insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            json_data["task"]["target"]["table_name"].upper())
            return False
    except ProgrammingError as error:
        if 'column "inserted_by" of relation' in str(error):
            task_logger.error("audit columns not found in the table previously to insert data")
            return False
        task_logger.exception("append() is %s", str(error))
        raise error

def drop(json_data: dict, conn: dict,conn_details) -> bool:
    """if table exists, it will drop"""
    try:
        if db_table_exists(conn,conn_details["database"], json_data["task"]["target"]["schema"],
            json_data["task"]["target"]["table_name"]) is True:
            task_logger.info("%s table exists, started dropping the table",
            json_data["task"]["target"]["table_name"].upper())
            schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
            drop_query = sqlalchemy.text(f'DROP TABLE {schema_name}.'
            f'{json_data["task"]["target"]["table_name"].upper()}')
            conn.execute(drop_query)
            task_logger.info("snowflake dropping table completed")
            return True
        # if table is not there, then it will say table does not exist
        task_logger.error('%s does not exists, give correct table name to drop',
        json_data["task"]["target"]["table_name"].upper())
        return False
    except Exception as error:
        task_logger.exception("drop() is %s", str(error))
        raise error

def replace(json_data: dict, conn: dict, datafram,counter: int, conn_details: list) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        if db_table_exists(conn,conn_details["database"], json_data["task"]["target"]["schema"],
        json_data["task"]["target"]["table_name"]) is True:
            schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                json_data["task"]["target"]["table_name"].upper())
                schema_name =conn_details["database"]+'.'+ json_data["task"]["target"]["schema"]
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{schema_name}.'
                f'{json_data["task"]["target"]["table_name"].upper()}')
                conn.execute(replace_query)
                insert_data(json_data,conn_details,datafram,conn,schema_name)
            else:
                insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name',\
            json_data["task"]["target"]["table_name"].upper())
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error

def trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,iter_value,audit):
    """function to get target record count"""
    if json_data["task"]["target"]["operation"] != "drop" and status is not False:
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',datafram.shape[0],
        iter_value)
        task_logger.info('the number of records ingested in target table:%s',
        datafram.shape[0])


def write(json_data, datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions) -> bool:
    """ function for ingesting data to snowflake based on the operation in json"""
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to snowflake db initiated")
        _,conn_details = establish_conn_for_snowflake(json_data, 'target',
        config_file_path,paths_data)
        status="Pass"
        if json_data["task"]["target"]["operation"] == "CREATE IF NOT EXIST":
            if counter == 1:
                create(json_data, sessions, datafram,conn_details)
                # print(create)
            else:
                status=append(json_data, sessions, datafram,conn_details)
        elif json_data["task"]["target"]["operation"] == "INSERT":
            status=append(json_data, sessions, datafram,conn_details)
        elif json_data["task"]["target"]["operation"] == "TRUNCATE AND LOAD":
            status=truncate(json_data, sessions, datafram, counter,conn_details)
        elif json_data["task"]["target"]["operation"] == "drop":
            status=drop(json_data, sessions,conn_details)
        elif json_data["task"]["target"]["operation"] == "DROP AND CREATE":
            status=replace(json_data, sessions, datafram, counter,conn_details)
        elif json_data["task"]["target"]["operation"] not in ("CREATE IF NOT EXIST",
             "INSERT","TRUNCATE AND LOAD","DROP AND CREATE","UPSERT"):
            task_logger.error("give proper input for operation to be performed on table")
            status = False
        trgt_record_count(json_data,status,datafram,task_id,run_id,
        paths_data,iter_value,audit)
        return status
    except ProgrammingError as e:
        snowflake_error = e.orig
        if snowflake_error.errno == 2025 and DUPLICATE_COLUMNS in str(snowflake_error):
            task_logger.error("there are duplicate column names in the target table")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error("there are duplicate column names in the target table")
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error