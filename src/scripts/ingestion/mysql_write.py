""" script for writing data from mysql table"""
import sys
import logging
import os
from datetime import datetime
import importlib
from sqlalchemy import create_engine, text
import pandas as pd
from sqlalchemy.exc import OperationalError
import pymysql
import sqlalchemy
from sqlalchemy.dialects.mysql import insert
import time


module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_mysql = getattr(module, "establish_conn_for_mysql")

task_logger = logging.getLogger('task_logger')
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
MYSQL_LOG_STATEMENT = "mysql ingestion completed"
WITH_AUDIT_COLUMNS = "data ingesting with audit columns"
WITH_OUT_AUDIT_COLUMNS = "data ingesting with out audit columns"

def db_table_exists(sessions: dict, schema: str, tablename: str)-> bool:
    """ function for checking whether a table exists or not in mysql """
    try:
        # checking whether the table exists in database or not
        schema_sql=sqlalchemy.text(f"select table_name from information_schema.tables where table_schema='{schema}'")
        connection = sessions.connection()
        schema_result = connection.execute(schema_sql)
        if bool(schema_result.rowcount) == True:
            table_sql = sqlalchemy.text(f"select table_name from information_schema.tables where "\
                f"table_name='{tablename}' and table_schema='{schema}'")
            table_result = connection.execute(table_sql)
            return bool(table_result.rowcount)
        task_logger.error("schema %s does not exist",schema)
        sys.exit()
    except pymysql.err.OperationalError as error:
        task_logger.exception("Schema name not present in the db: %s",str(error))
    except Exception as error:
        task_logger.exception("db_table_exists() is %s", str(error))
        raise error

def is_nested_json_column(series):
    """Check if all elements in the series are either dictionaries or lists"""
    return all(isinstance(item, (dict, list)) for item in series)

def insert_data(json_data,conn_details,dataframe,sessions):
    """function for inserting df data in to table"""
    try:
        target = json_data["task"]["target"]
        connection = sessions.connection()
        json_columns = [col for col in dataframe.columns if is_nested_json_column(dataframe[col])]
        dtype_dict = {col: sqlalchemy.types.JSON for col in json_columns}
        if target["audit_columns"] == "active":
            dataframe['CRTD_BY']=conn_details["username"]
            dataframe['CRTD_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            dataframe['UPDT_BY']= " "
            dataframe['UPDT_DTTM']= " "
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql(target["table_name"], connection, schema = target["schema"],
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(MYSQL_LOG_STATEMENT)
            
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql(target["table_name"], connection, schema = target["schema"],
            index = False, if_exists = "append", dtype = dtype_dict)
            task_logger.info(MYSQL_LOG_STATEMENT)
            
    except sqlalchemy.exc.OperationalError as error:
        if error.orig.args[0] == 1049:
            task_logger.error("Database %s does not exist.",
                              target["schema"])
            sys.exit()
        elif 'Unknown column' in str(error):
            task_logger.error("Error: The specified column does not exist in the table.%s",str(error))
            sys.exit()
        else:
            task_logger.error("An error occurred: %s", str(error))
            raise error
    
    except Exception as error:
        task_logger.info("error occured in insert_data function %s", str(error))
        raise error
def update_table(json_data,conn_details,dataframe,sessions):
    """function for inserting df data in to table"""
    try:
        target = json_data["task"]["target"]
        connection = sessions.connection()
        json_columns = [col for col in dataframe.columns if is_nested_json_column(dataframe[col])]
        dtype_dict = {col: sqlalchemy.types.JSON for col in json_columns}
        if target["audit_columns"] == "active":
            dataframe['UPDT_BY']= conn_details["username"]
            dataframe['UPDT_DTTM']= datetime.now().strftime(CURRENT_TIMESTAMP)
            task_logger.info(WITH_AUDIT_COLUMNS)
            dataframe.to_sql("target_update_table", connection, schema = target["schema"],
            index = False, if_exists = "append", dtype = dtype_dict)
            sessions.commit()            
        else:
            task_logger.info(WITH_OUT_AUDIT_COLUMNS)
            dataframe.to_sql("target_update_table", connection, schema = target["schema"],
            index = False, if_exists = "append", dtype = dtype_dict)
            sessions.commit()
    except sqlalchemy.exc.OperationalError as error:
        if error.orig.args[0] == 1049:
            task_logger.error("Database %s does not exist.",
                              target["schema"])
            sys.exit()
        elif 'Unknown column' in str(error):
            task_logger.error("Error: The specified column does not exist in the table.%s",str(error))
            sys.exit()
        else:
            task_logger.error("An error occurred: %s", str(error))
            raise error
    
    except Exception as error:
        task_logger.info("error occured in insert_data function %s", str(error))
        raise error

def create(json_data: dict, conn, dataframe,conn_details:str)-> bool:
    """if table is not present , it will create"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"],target["table_name"]) is False:
            task_logger.info('%s does not exists so creating a new table',
            target["table_name"])
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            task_logger.info("%s table exists, started appending the data to table",
            target["table_name"])
            insert_data(json_data,conn_details,dataframe,conn)
    except OperationalError as error:
        if 'Duplicate column name' in str(error):
            task_logger.error("there are duplicate column names in the target table")
            sys.exit()
        
        else:
            task_logger.info("else")
            task_logger.exception("create() is %s", str(error))
            raise error

def append(json_data: dict, conn: dict, dataframe, conn_details) -> bool:
    """if table exists, it will append"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"], target["table_name"]) is True:
            task_logger.info("%s table exists, started appending the data to table",
            target["table_name"])
            insert_data(json_data,conn_details,dataframe,conn)
        else:
            task_logger.error('%s does not exists, so create table first',
            target["table_name"])
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
                target["table_name"])
                replace_query = sqlalchemy.text(f'DROP TABLE '
                f'{target["schema"]}.{target["table_name"]}')
                # conn.execution_options(autocommit=False).execute(replace_query)
                conn.execute(replace_query)
                task_logger.info(" table replace finished, started inserting data into "
                 "%s table", target["table_name"])
                insert_data(json_data,conn_details,dataframe,conn)
            else:
                insert_data(json_data,conn_details,dataframe,conn)
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name',
            target["table_name"])
            return False
    except Exception as error:
        task_logger.exception("replace() is %s", str(error))
        raise error
def update_data(json_data, sessions, max_retries=3, retry_delay=1):
    """
    Updates data in a database or service using the provided JSON data and sessions.
    Parameters:
    max_retries (int, optional): The maximum number of retry attempts in case of failure. Defaults to 3.
    retry_delay (int, optional): The delay in seconds between retry attempts. Defaults to 1 second.
    """
    connection = sessions.connection()
    target=json_data["task"]["target"]
    primary_key_column = target['primary_key'].split(',')
    result = connection.execute(f'DESCRIBE {target["schema"]}.target_update_table')
    
    column_descriptions = result.fetchall()
    column_names = [desc[0] for desc in column_descriptions]
    set_clause = ', '.join([f't.{col} = s.{col}' for col in column_names if col not in primary_key_column])
    update_query = f"""
        UPDATE  {target["schema"]}.{target["table_name"]} t
        INNER JOIN  {target["schema"]}.target_update_table s 
        ON {" AND ".join([f"s.{pk} = t.{pk}" for pk in primary_key_column])}
        SET {set_clause}
    """
    attempt = 0
    while attempt < max_retries:
        try:
            connection.execute(update_query)
            sessions.commit()
            return True  # Return True if update query executed successfully
        except OperationalError as e:
            if "1213" in str(e.orig):
                # Deadlock detected, retry the transaction
                attempt += 1
                time.sleep(retry_delay)
                task_logger.error(f"Retrying due to deadlock (attempt {attempt})...")
            else:
                task_logger.error("Error: %s", str(e))
                return False

    task_logger.error("Failed to update after multiple retries due to deadlock.")
    return False
def upsert(json_data: dict, sessions: dict, dataframe,conn_details) -> bool:
    """Function for inserting or updating data into a table."""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(sessions, target["schema"], target["table_name"]) is True:
            task_logger.info("%s table exists, started upsert the table",
                target["table_name"])
            connection = sessions.connection()
            query = f'SELECT * FROM {target["schema"]}.{target["table_name"]}'
            result = connection.execute(query)
            dataframe_existing = pd.DataFrame(result.fetchall(), columns=result.keys())
            primary_keys=list(json_data["task"]["target"]['primary_key'].split(","))
            merged_df=dataframe_existing.merge(dataframe, on=primary_keys,how='outer',suffixes=('_x', '_y'))   
            filtered_df = merged_df.filter(regex=r'^((?!_x).)*$', axis=1)
            filtered_df.columns = [col.replace('_y', '') for col in filtered_df.columns]
            new_rows = filtered_df[~filtered_df.index.isin(dataframe_existing.index)]  # Rows not present in existing data
            updated_rows = filtered_df[filtered_df.index.isin(dataframe_existing.index)]
            columns_to_compare = [col for col in updated_rows.columns if col not in primary_keys]
            updated_rows = updated_rows.dropna()
            new_rows_count=new_rows.shape[0]
            if not updated_rows.empty:
                updated_rows_filtered = updated_rows[~updated_rows[columns_to_compare].apply(tuple, axis=1).isin(dataframe_existing[columns_to_compare].apply(tuple, axis=1))]
                updated_rows_count=updated_rows_filtered.shape[0]
                update_table(json_data, conn_details, updated_rows_filtered, sessions)
                task_logger.info("updated_rows_count: %s",updated_rows_count)
            if not new_rows.empty:
                insert_data(json_data, conn_details, new_rows, sessions)
                task_logger.info("new_rows_count:%s ",new_rows_count)
            update_data(json_data, sessions)
            #drop target_update_table after updating 
            drop_query = sqlalchemy.text(f'DROP TABLE '
                f'{target["schema"]}.target_update_table') 
            sessions.execute(drop_query)
            sessions.commit()
            return True
        else:
            # if table is not there, then it will say table does not exist
            task_logger.error('%s does not exists, give correct table name to upsert',
            target["table_name"])
            return False 
        
    except Exception as error:
        task_logger.exception("upsert() is %s", str(error))
        raise error

def truncate(json_data: dict, conn: dict,dataframe,counter: int, conn_details) -> bool:
    """if table exists, it will truncate"""
    try:
        target = json_data["task"]["target"]
        if db_table_exists(conn, target["schema"], target["table_name"]) is True:
            if counter == 1:
                task_logger.info("%s table exists, started truncating the table",
                target["table_name"])
                truncate_query = sqlalchemy.text(f'TRUNCATE TABLE '
                f'{target["schema"]}.{target["table_name"]}')
                # conn.execution_options(autocommit=True).execute(truncate_query)
                conn.execute(truncate_query)
                task_logger.info("mysql truncating table finished, started inserting data into "
                "table :%s", target["table_name"])
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
        task_logger.exception("append() is %s", str(error))
        raise error

def trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,iter_value,audit):
    """function to get target record count"""
    if json_data["task"]["target"]["operation"] not in ("drop","UPSERT") and status is not False:
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',datafram.shape[0],
        iter_value)
        task_logger.info('the number of records ingested in target table:%s',
        datafram.shape[0])     
def write(json_data,datafram,counter,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,sessions) -> bool:
    """ function for ingesting data to mysql based on the operation in json"""
    try:
        target = json_data["task"]["target"]
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        task_logger.info("ingest data to mysql db initiated")
        _ ,conn_details = establish_conn_for_mysql(json_data,'target',
        config_file_path,paths_data)
        datafram = datafram.rename(columns=lambda x: x.strip())
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
        elif target["operation"] == "UPSERT":
            status=upsert(json_data,sessions, datafram,conn_details)
        elif target["operation"] not in ("CREATE IF NOT EXIST", "INSERT","TRUNCATE AND LOAD",
            "DROP AND CREATE","UPSERT"):
            task_logger.error("give propper input for operation condition")
            status = False
        trgt_record_count(json_data,status,datafram,task_id,run_id,paths_data,iter_value,audit)
        return status
    except OperationalError:
        # task_logger.error("there are duplicate column names in the target table")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()
    except pymysql.err.ProgrammingError: #to handle table not found issue
        task_logger.error("the table name or connection specified in the task is incorrect")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
