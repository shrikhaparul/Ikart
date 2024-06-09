""" importing modules """
import logging
import os
import sys
import importlib
import pymysql
import pandas as pd

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_mysql = getattr(module, "establish_conn_for_mysql")

task_logger = logging.getLogger('task_logger')

def read(json_data,config_file_path,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from mysql table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3,_ = establish_conn_for_mysql(json_data, 'source',config_file_path,paths_data)
        task_logger.info('reading data from mysql started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        source = json_data["task"]["source"]
        count1 = 0
        sql = f'SELECT count(*) from ({source["query"]}) as d;'
        task_logger.info(sql)
        cursor.execute(sql)
        myresult = cursor.fetchall()
        audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',myresult[-1][-1],
        iter_value)
        task_logger.info('the number of records read from source table:%s',
        myresult[-1][-1])
        task_logger.info('sql_query: %s',source["query"])
        for query in pd.read_sql(source["query"],
        conn3, chunksize = source["chunk_size"],dtype_backend="pyarrow"):
            count1+=1
            task_logger.info('%s iteration' , str(count1))
            yield query
        conn3.dispose()
        return True
    except pymysql.err.ProgrammingError: #to handle table not found issue
        task_logger.error("the table name or connection specified in the "
                          "task is incorrect/doesnot exists")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',
        iter_value)
        sys.exit()
    except pymysql.err.OperationalError as e:
        # task_logger.exception("Caught an OperationalError:%s",str(e))
        source = json_data["task"]["source"]
        error_code, _ = e.args
        if error_code == 2013:
            task_logger.exception("Lost connection to MySQL server during query")
        elif error_code == 1049:
            task_logger.error("Database %s does not exist.", source["schema"])
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',
            iter_value)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_mysql() is %s", str(error))
        raise error
