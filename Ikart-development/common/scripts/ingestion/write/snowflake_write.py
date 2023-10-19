""" script for writing data to snowflake table"""
import sys
import logging
from datetime import datetime
import os
import importlib
import sqlalchemy
from sqlalchemy.exc import ProgrammingError
import pandas as pd
from snowflake.connector.errors import ProgrammingError

module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")

task_logger = logging.getLogger('task_logger')
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
SNOWFLAKE_LOG_STATEMENT = "snowflake ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"

def db_table_exists(sessions: dict,database: str,schema: str, table_name: str)-> bool:
    """ function for checking whether a table exists or not in snowflake """
    # checking whether the table exists in database or not
    try:
        sql = f"select table_schema, table_name from {database}.information_schema.tables "\
            f"where table_name ='{table_name.upper()}'  and table_schema = '{schema.upper()}'"
        connection = sessions.connection()
        result = connection.execute(sql)
        return bool(result.rowcount)
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def establish_conn(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the snowflake database
       you pass it through the json"""
    try:
        connection_details =  get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+'.json')
        password = decrypt(connection_details["password"])
        conn = sqlalchemy.create_engine(f'snowflake://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["account"]}/'
        f':{connection_details["database"]}/{json_data["task"]["target"]["schema"]}'
        f'?warehouse={connection_details["warehouse"]}&role={connection_details["role"]}')
        return conn,connection_details
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        raise error

def insert_data(json_data,conn_details,datafram,sessions,schema_name):
    """function for inserting df data in to table"""
    connection = sessions.connection()
    target = json_data["task"]["target"]
    if target["audit_columns"] == "active":
        datafram['CRTD_BY']=conn_details["username"]
        datafram['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
        datafram['UPDT_BY']= " "
        datafram['UPDT_DTTM']= " "
        task_logger.info(WITH_AUDIT_COLUMNS)
        datafram.to_sql(target["table_name"], connection,\
        schema = schema_name,index = False, if_exists = "append")
        task_logger.info(SNOWFLAKE_LOG_STATEMENT)
    else:
        task_logger.info(WITH_OUT_AUDIT_COLUMNS)
        datafram.to_sql(target["table_name"], connection,\
        schema = schema_name,index = False, if_exists = "append")
        task_logger.info(SNOWFLAKE_LOG_STATEMENT)

def create(json_data: dict, conn, datafram, conn_details) -> bool:
    """if table is not present , it will create"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn ,conn_details["database"],target["schema"],
        target["table_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',\
            target["table_name"])
            schema_name =conn_details["database"]+'.'+ target["schema"]
            insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table exists, it will say table is already present, give new name to create
            task_logger.error('%s already exists, so give a new table name to create',
            target["table_name"])
            return False
    except Exception as error:
        task_logger.exception("create() is %s", str(error))
        raise error

def append(json_data: dict, conn: dict, datafram,conn_details) -> bool:
    """if table exists, it will append"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn,conn_details["database"] ,target["schema"],
        target["table_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["table_name"])
            schema_name =conn_details["database"]+'.'+ target["schema"]
            insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            # create table first or give table name that exists to append data
            task_logger.error('%s does not exists, so create table first',\
            target["table_name"])
            return False
    except ProgrammingError:
        task_logger.error("audit columns not found in the table previously to append")
        return False

def truncate(json_data: dict, conn: dict,datafram,counter: int, conn_details) -> bool:
    """if table exists, it will truncate"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn,conn_details["database"] , target["schema"],
            target["table_name"]) is True:
            schema_name =conn_details["database"]+'.'+ target["schema"]
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["table_name"])
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{schema_name}.'
                f'{target["table_name"]}')
                conn.execution_options(autocommit=True).execute(truncate_query)
                task_logger.info("snowflake truncating table finished, started inserting data into "
                "%s table", target["table_name"])
                insert_data(json_data,conn_details,datafram,conn,schema_name)
            else:
                insert_data(json_data,conn_details,datafram,conn,schema_name)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to truncate',
            target["table_name"])
            return False
    except ProgrammingError as error:
        if 'column "inserted_by" of relation' in str(error):
            task_logger.error("audit columns not found in the table previously to insert data")
            return False
        else:
            task_logger.exception("append() is %s", str(error))
            raise error

def drop(json_data: dict, conn: dict,conn_details) -> bool:
    """if table exists, it will drop"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn,conn_details["database"], target["schema"],
            json_data["task"]["target"]["table_name"]) is True:
            task_logger.info("%s table exists, started dropping the table",
            json_data["task"]["target"]["table_name"])
            schema_name =conn_details["database"]+'.'+ target["schema"]
            drop_query = sqlalchemy.text(f'DROP TABLE {schema_name}.'
            f'{target["table_name"]}')
            conn.execution_options(autocommit=True).execute(drop_query)
            task_logger.info("snowflake dropping table completed")
            return True
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to drop',
            target["table_name"])
            return False
    except Exception as error:
        task_logger.exception("drop() is %s", str(error))
        raise error

def replace(json_data: dict, conn: dict, datafram,counter: int, conn_details: list) -> bool:
    """if table exists, it will drop and replace data"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn,conn_details["database"], target["schema"],
        target["table_name"]) is True:
            schema_name =conn_details["database"]+'.'+ target["schema"]
            if counter == 1:
                task_logger.info("%s table exists, started replacing the table",
                target["table_name"])
                schema_name =conn_details["database"]+'.'+ target["schema"]
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{schema_name}.'
                f'{target["table_name"]}')
                conn.execution_options(autocommit=True).execute(replace_query)
                insert_data(json_data,conn_details,datafram,conn,schema_name)
            else:
                insert_data(json_data,conn_details,datafram,conn,schema_name)
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
            task_logger.info("pipeline txt file does not exist")
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def trgt_record_count(json_data,status,sessions,task_id,run_id,iter_value,audit,conn_details):
    """function to get target record count"""
    target = json_data["task"]["target"]
    if target["operation"] in ("create", "append","truncate",
        "replace") and status is not False:
        connection = sessions.connection()
        schema_name =conn_details["database"]+'.'+ target["schema"]
        sql = f'SELECT count(0) from {schema_name}.{target["table_name"]};'
        myresult = connection.execute(sql).fetchall()
        audit(json_data, task_id,run_id,'TRGT_RECORD_COUNT',myresult[-1][-1],
        iter_value)
        task_logger.info('the number of records present in target table after ingestion:%s',
        myresult[-1][-1])


def write(json_data, datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions) -> bool:
    """ function for ingesting data to snowflake based on the operation in json"""
    try:
        target = json_data["task"]["target"]
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to snowflake db initiated")
        _,conn_details = establish_conn(json_data, 'target',config_file_path)
        status="Pass"
        if target["operation"] == "create":
            if counter == 1:
                status=create(json_data, sessions, datafram,conn_details)
                # print(create)
            else:
                status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "append":
            status=append(json_data, sessions, datafram,conn_details)
        elif target["operation"] == "truncate":
            status=truncate(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] == "drop":
            status=drop(json_data, sessions,conn_details)
        elif target["operation"] == "replace":
            status=replace(json_data, sessions, datafram, counter,conn_details)
        elif target["operation"] not in ("create", "append","truncate",
            "drop","replace"):
            task_logger.error("give proper input for operation to be performed on table")
            # sys.exit()
            status = False
        trgt_record_count(json_data,status,sessions,task_id,run_id,iter_value,audit,conn_details)
        return status
    except ProgrammingError : #to handle table not found issue
        task_logger.error("the table or connection specified in the command is incorrect")
        write_to_txt(task_id,'FAILED',file_path)
        sys.exit()
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        task_logger.exception("ingest_data_to_snowflake() is %s", str(error))
        raise error
