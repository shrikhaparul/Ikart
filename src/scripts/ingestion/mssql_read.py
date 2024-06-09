""" script for reading data from sql server table"""
import logging
import importlib
import os
import sys
import pandas as pd
import sqlalchemy
import pymssql

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_sqlserver = getattr(module, "establish_conn_for_sqlserver")

task_logger = logging.getLogger('task_logger')

def read(json_data,config_file_path,task_id,run_id,paths_data,file_path,iter_value) -> bool:
    """ function for reading data from sql server table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        sqlserver_conn,_ = establish_conn_for_sqlserver(json_data,
        'source',config_file_path,paths_data)
        task_logger.info('reading data from sql server started')
        connection = sqlserver_conn.raw_connection()
        cursor = connection.cursor()
        source = json_data["task"]["source"]
        count1 = 0
        sql = f'SELECT count(0) from ({source["query"]}) as d;'
        task_logger.info(sql)
        cursor.execute(sql)
        myresult = cursor.fetchall()
        audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',myresult[-1][-1],
        iter_value)
        task_logger.info('the number of records present in source table before ingestion:%s',
        myresult[-1][-1])
        task_logger.info('sql_query: %s',source["query"])
        for query in pd.read_sql(source["query"],
        sqlserver_conn, chunksize = source["chunk_size"],dtype_backend="pyarrow"):
            count1+=1
            task_logger.info('%s iteration' , str(count1))
            yield query
        sqlserver_conn.dispose()
        return True
    except sqlalchemy.exc.OperationalError as e:
        if "Unable to connect: Adaptive Server is unavailable or does not exist"in str(e):
            task_logger.error("connection failed,Unable to connect %s",str(e))
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()
    except pymssql.DatabaseError as e:
        error_message=str(e)
        if error_message:
            task_logger.error("Invalid Schema: %s", error_message)
            sys.exit()
        else:
            task_logger.error("An unknown Database Error occurred")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()  
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_sql() is %s", str(error))
        raise error
