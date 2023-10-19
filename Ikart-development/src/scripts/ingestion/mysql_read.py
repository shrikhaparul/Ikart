""" importing modules """
import logging
import os
import sys
import importlib
import pymysql
import pandas as pd

module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
module = importlib.import_module("connections")
establish_conn_for_mysql = getattr(module, "establish_conn_for_mysql")

task_logger = logging.getLogger('task_logger')

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

def read(json_data,config_file_path,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from mysql table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data["src"]+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3,_ = establish_conn_for_mysql(json_data, 'source',config_file_path)
        task_logger.info('reading data from mysql started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        source = json_data["task"]["source"]
        count1 = 0
        if source["query"] == " ":
            task_logger.info("reading from mysql table: %s",
            source["table_name"])
            sql = f'SELECT count(0) from {source["table_name"]};'
            cursor.execute(sql)
            myresult = cursor.fetchall()
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',myresult[-1][-1],
            iter_value)
            task_logger.info('the number of records present in source table before ingestion:%s',
            myresult[-1][-1])
            default_columns = None if source["select_columns"]==" "\
            else list(source["select_columns"].split(","))
            for query in pd.read_sql_table(source["table_name"], conn3,\
            columns = default_columns, \
            chunksize = source["chunk_size"]):
                count1+=1
                task_logger.info('%s iteration' , str(count1))
                yield query
        else:
            task_logger.info("reading from sql query")
            sql = f'SELECT count(*) from ({source["query"]}) as d;'
            task_logger.info(sql)
            cursor.execute(sql)
            myresult = cursor.fetchall()
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',myresult[-1][-1],
            iter_value)
            task_logger.info('the number of records present in source table before ingestion:%s',
            myresult[-1][-1])
            task_logger.info('sql_query: %s',source["query"])
            for query in pd.read_sql(source["query"],
            conn3, chunksize = source["chunk_size"]):
                count1+=1
                task_logger.info('%s iteration' , str(count1))
                yield query
        conn3.dispose()
        return True
    # except pymysql.err.ProgrammingError: #to handle table not found issue
    #     task_logger.error("the table name or connection specified in the "
    #                       "task is incorrect/doesnot exists")
    #     write_to_txt(task_id,'FAILED',file_path)
    #     audit(json_data, task_id,run_id,'STATUS','FAILED',
    #     iter_value)
    #     sys.exit()
    # except pymysql.err.OperationalError as e:
    #     task_logger.exception(f"Caught an OperationalError: {e}")
    #     error_code, error_message = e.args
    #     if error_code == 2013:
    #         task_logger.exception("Lost connection to MySQL server during query")
    #     write_to_txt(task_id,'FAILED',file_path)
    #     audit(json_data, task_id,run_id,'STATUS','FAILED',
    #     iter_value)
    #     sys.exit()
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_mysql() is %s", str(error))
        raise error
