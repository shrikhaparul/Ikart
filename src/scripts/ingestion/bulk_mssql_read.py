""" importing modules """
import logging
import os
import sys
import importlib
import pymssql
import pandas as pd

module = importlib.import_module("utility")
update_status_file = getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_sqlserver = getattr(module, "establish_conn_for_sqlserver")

task_logger = logging.getLogger('task_logger')

def read(json_data, config_file_path, task_id, run_id, paths_data,
         file_path, iter_value, source, group_no, subtask_no):
    """ function for reading data from mssql table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+\
            paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3, _ = establish_conn_for_sqlserver(json_data, 'source', config_file_path, paths_data)
        task_logger.info('reading data from mssql started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        count1 = 0
        task_logger.info("reading from mssql table: %s",
        source["object_name"])
        extraction_type = source["extraction_type"]
        extraction_criteria = source["extraction_criteria"]
        if extraction_type == 'Full':
            sql = f'SELECT count(0) from {source["object_name"]};'
            sql_to_exec = f'SELECT * from {source["object_name"]};'
        elif extraction_type == 'Filter':
            if len(extraction_criteria) == 0:
                sql = f'SELECT count(0) from {source["object_name"]};'
                sql_to_exec = f'SELECT * from {source["object_name"]};'
            else:
                sql = f'SELECT count(0) from {source["object_name"]} where {extraction_criteria};'
                sql_to_exec = f'SELECT * from {source["object_name"]} where {extraction_criteria};'
        task_logger.info("sorce SQL:%s", sql_to_exec)
        cursor.execute(sql)
        myresult = cursor.fetchall()
        audit(json_data, task_id, run_id, paths_data, 'SRC_RECORD_COUNT', myresult[-1][-1],
        iter_value, group_no, subtask_no)
        task_logger.info('the number of records read from source table before ingestion:%s',
        myresult[-1][-1])
        for query in pd.read_sql(sql_to_exec,
            conn3, chunksize = json_data["chunk_size"],dtype_backend="pyarrow"):
            count1+=1
            task_logger.info('%s iteration' , str(count1))
            yield query
        conn3.dispose()
        return True
    except pymssql.OperationalError as e:
        # Extract error details from the exception message
        error_code, error_message = e.args[0], e.args[1]
        task_logger.error("OperationalError:%s,%s", error_code, error_message)
        # Check if the error code is 20009
        if error_code == 20009:
            # Handle the specific error code 20009
            task_logger.error("Error code 20009 occurred.")
            update_status_file(task_id,'FAILED', file_path)
            audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED',
                  iter_value, group_no, subtask_no)
        sys.exit()
    except Exception as e:
        error_message = str(e)
        if isinstance(e, pymssql.DatabaseError):
            inner_exception = e.args[0] if len(e.args) > 0 else None
            if inner_exception:
                error_message = str(inner_exception)
        task_logger.error("Error reading data from SQL Server:%s", error_message)
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS',
              'FAILED', iter_value, group_no, subtask_no)
        sys.exit()
