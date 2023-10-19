""" script for writing data to postgres table"""
import sys
import logging
import os
from datetime import datetime
import importlib
from sqlalchemy.exc import OperationalError
import sqlalchemy
import pandas as pd
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
module = importlib.import_module("connections")
establish_conn_for_postgres = getattr(module, "establish_conn_for_postgres")
task_logger = logging.getLogger('task_logger')

CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
POSTGRES_LOG_STATEMENT = "postgres ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"

# def establish_conn(json_data: dict, json_section: str) -> bool:
#     """establishes connection for the postgres database
#        you pass it through the json"""
#     try:
#         connection_details = get_config_section(json_data["task"][
# json_section]["connection_file_path"],\
#         json_data["task"][json_section]["connection_name"])
#         conn1 = sqlalchemy.create_engine(f'postgresql://{connection_details["user"]}'
#         f':{connection_details["password"].replace("@", "%40")}@{connection_details["host"]}'
#         f':{int(connection_details["port"])}/{connection_details["database"]}')
#         # logging.info("connection established")
#         return conn1
#     except Exception as error:
#         logging.exception("establish_conn() is %s", str(error))
#         raise Exception("establish_conn(): " + str(error)) from error

def db_table_exists(sessions: dict, schema: str, tablename: str)-> bool:
    """ function for checking whether a table exists or not in postgres """
    # checking whether the table exists in database or not
    try:
        sql = f"select table_name from information_schema.tables where table_name='{tablename}'"\
            f"and table_schema='{schema}'"
        connection = sessions.connection()
        result = connection.execute(sql)
        return bool(result.rowcount)
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def insert_data(json_data,conn_details,dataframe,sessions):
    """function for inserting df data in to table"""
    try:
        target = json_data["task"]["target"]
        connection = sessions.connection()
        if target["audit_columns"] == "active":
            dataframe['CRTD_BY']=conn_details["username"]
            dataframe['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            dataframe['UPDT_BY']= " "
            dataframe['UPDT_DTTM']= " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql(target["table_name"], connection,\
            index = False, if_exists = "append")
            task_logger.info(POSTGRES_LOG_STATEMENT)
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql(target["table_name"], connection,
            index = False, if_exists = "append")
            task_logger.info(POSTGRES_LOG_STATEMENT)
    except Exception as error:
        # Rollback the transaction in case of an error
        # sessions.rollback()
        # task_logger.info("Transaction rolled back due to an error! %s", str(error))
        task_logger.info("error occured in insert_data function %s", str(error))
        raise error

def create(json_data: dict, conn, dataframe,conn_details) -> bool:
    """if table is not present , it will create"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema_name"],target["table_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',\
            target["table_name"])
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table exists, it will say table is already present, give new name to create
            task_logger.error('%s already exists, so give a new table name to create',
            target["table_name"])
            return False
    except OperationalError as error:
        if 'Duplicate column name' in str(error):
            task_logger.error("there are duplicate column names in the target table")
            sys.exit()
        else:
            task_logger.info("else")
            task_logger.exception("create() is %s", str(error))
            raise error

def append(json_data: dict, conn: dict, dataframe,conn_details) -> bool:
    """if table exists, it will append"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema_name"],target["table_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["table_name"])
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table is not there, then it will say table does not exist
            # create table first or give table name that exists to append data
            task_logger.error('%s does not exists, so create table first',\
            target["table_name"])
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously to append")
            return False
        else:
            task_logger.exception("append() is %s", str(error))
            raise error

def truncate(json_data: dict, conn: dict,dataframe,counter: int, conn_details) -> bool:
    """if table exists, it will truncate"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema_name"],target["table_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["table_name"])
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE'
                f'{target["schema_name"]}.{target["table_name"]}')
                conn.execution_options(autocommit=True).execute(truncate_query)
                task_logger.info("postgres truncating table completed")
                insert_data(json_data,conn_details,dataframe,conn)
            else:
                insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            target["table_name"])
            return False
    except OperationalError as error:
        if "Unknown column 'CRTD_BY' in 'field list'" in str(error):
            task_logger.error("audit columns not found in the table previously"
            "to insert data after truncate")
            return False
        else:
            task_logger.exception("append() is %s", str(error))
            raise error

def drop(json_data: dict, conn: dict) -> bool:
    """if table exists, it will drop"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema_name"],target["table_name"]) is True:
            task_logger.info("%s table exists, started dropping the table",
            target["table_name"])
            drop_query = sqlalchemy.text(f'DROP TABLE {target["schema_name"]}.'
            f'{target["table_name"]}')
            conn.execution_options(autocommit=True).execute(drop_query)
            task_logger.info("postgres dropping table completed")
            return True
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to drop',
            target["table_name"])
            return False
    except Exception as error:
        task_logger.exception("drop() is %s", str(error))
        raise error

def replace(json_data: dict, conn: dict, dataframe,counter: int, conn_details) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema_name"],target["table_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                target["table_name"])
                replace_query = sqlalchemy.text(f'DROP TABLE'
                f'{target["schema_name"]}.{target["table_name"]}')
                conn.execution_options(autocommit=True).execute(replace_query)
                task_logger.info(" table replace finished, started inserting data into "
                 "%s table", target["table_name"])
                insert_data(json_data,conn_details,dataframe,conn)
                task_logger.info(POSTGRES_LOG_STATEMENT)
            else:
                insert_data(json_data,conn_details,dataframe,conn)
                task_logger.info(POSTGRES_LOG_STATEMENT)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name',\
            target["table_name"])
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error

def write_to_txt(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def trgt_record_count(json_data,status,sessions,task_id,run_id,iter_value,audit):
    """function to get target record count"""
    target = json_data["task"]["target"]
    if target["operation"] != "drop" and status is not False:
        schema = json_data['task']['target']['schema_name']
        sql = f'SELECT count(0) from {schema}.{target["table_name"]};'
        connection = sessions.connection()
        record_count = connection.execute(sql).fetchall()
        audit(json_data, task_id,run_id,'TRGT_RECORD_COUNT',record_count[-1][-1],
        iter_value)
        task_logger.info('the number of records present in target table after ingestion:%s',
        record_count[-1][-1])

def write(json_data,datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions) -> bool:
    """ function for ingesting data to postgres based on the operation in json"""
    try:
        target = json_data["task"]["target"]
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to postgres db initiated")
        _ ,conn_details = establish_conn_for_postgres(json_data,'target',
                                                     config_file_path)
        status="Pass"
        if target["operation"] == "create":
            if counter == 1:
                status=create(json_data, sessions, datafram, conn_details)
            else:
                status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "append":
            status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "truncate":
            status=truncate(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] == "drop":
            status=drop(json_data, sessions)
        elif target["operation"] == "replace":
            status=replace(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] not in ("create", "append","truncate",
            "drop","replace"):
            task_logger.error("give proper input for operation to be performed on table")
            status = False
        trgt_record_count(json_data,status,sessions,task_id,run_id,iter_value,audit)
        return status
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
