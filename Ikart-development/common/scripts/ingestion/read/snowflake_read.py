""" script for reading data from snowflake table"""
import logging
import sys
import os
import pandas as pd
import sqlalchemy
import importlib
from utility import get_config_section,decrypt
from snowflake.connector.errors import ProgrammingError

task_logger = logging.getLogger('task_logger')

def establish_conn(json_data: dict, json_section: str,connection_file_path:str):
    """establishes connection for the snowflake database
       you pass it through the json"""
    try:
        connection_details =get_config_section(connection_file_path+json_data["task"][json_section]\
        ["connection_name"]+'.json')
        # print(connection_details["username"])
        password = decrypt(connection_details["password"])
        conn1= sqlalchemy.create_engine(f'snowflake://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["account"]}/'
        f':{connection_details["database"]}/{json_data["task"]["source"]["schema"]}'
        f'?warehouse={connection_details["warehouse"]}&role={connection_details["role"]}')
        task_logger.info("connection established")
        # task_logger.info("connection established")
        return conn1,connection_details
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        raise error

def write_to_txt(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            # task_logger.info("txt getting called")
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def read(json_data,connection_file_path,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from snowflake table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3,conn_details = establish_conn(json_data, 'source',connection_file_path)
        task_logger.info('reading data from snowflake started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        count1 = 0
        source = json_data["task"]["source"]
        if source["query"] == " ":
            #if query is empty it will go to table name execution
            task_logger.info("reading from snowflake table: %s",
            source["table_name"])
            schema_name =conn_details["database"]+'.'+ source["schema"]
            sql = f'SELECT count(0) from {schema_name}.{source["table_name"]};'
            cursor.execute(sql)
            myresult = cursor.fetchall()
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',myresult[-1][-1],
            iter_value)
            task_logger.info('the number of records present in source table before ingestion:%s',
            myresult[-1][-1])
            query = (f'select * from {conn_details["database"]}.'
                     f'{source["schema"]}.'
                     f'{source["table_name"]}')
            # task_logger.info(conn_details["database"])
            conn3.execution_options(autocommit=True).execute(query)
            for query in pd.read_sql(query,conn3,\
            chunksize = source["chunk_size"]):
                count1+=1
                task_logger.info('%s iteration' , str(count1))
                # task_logger.info(query)
                yield query
        else:
            #if query is  not empty, goes for query execution
            task_logger.info("reading from sql query")
            sql = f'SELECT count(0) from ({source["query"]}) as d;'
            # task_logger.info(sql)
            cursor.execute(sql)
            myresult = cursor.fetchall()
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',myresult[-1][-1],
            iter_value)
            task_logger.info('sql_query: %s',source["query"])
            for query in pd.read_sql(source["query"],
            conn3, chunksize = source["chunk_size"]):
                count1+=1
                task_logger.info('%s iteration' , str(count1))
                yield query
        conn3.dispose()
        return True
    except ProgrammingError : #to handle table not found issue
        task_logger.error("the table name or connection specified in the command is incorrect")
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        sys.exit()
    # except sqlalchemy.exc.OperationalError:
    #     task_logger.error("The details provided inside the connection file path is incorrect")
    #     status = 'FAILED'
    #     write_to_txt(task_id,status,run_id,paths_data)
    #     sys.exit()
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_snowflake() is %s", str(error))
        raise error
