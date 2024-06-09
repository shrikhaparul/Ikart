""" importing modules """
import logging
import os
import sys
import importlib
import pandas as pd
import sqlalchemy
import cx_Oracle


module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_oracle = getattr(module, "establish_conn_for_oracle")

task_logger = logging.getLogger('task_logger')

def read(json_data,config_file_path,task_id,run_id,paths_data,
    file_path,iter_value,source,group_no,subtask_no):
    """ function for reading data from oracle table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3,_ = establish_conn_for_oracle(json_data, 'source',config_file_path,paths_data)
        task_logger.info('reading data from oracle started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        count1 = 0
        task_logger.info("reading from oracle table: %s",
        source["object_name"])
        extraction_type = source["extraction_type"]
        extraction_criteria = source["extraction_criteria"]
        if extraction_type == 'Full':
            sql = f'SELECT count(0) from {source["schema_name"]}.{source["object_name"]}'
            sql_to_exec = f'SELECT * from {source["schema_name"]}.{source["object_name"]}'
        elif extraction_type == 'Filter':
            if len(extraction_criteria) == 0:
                sql = f'SELECT count(0) from {source["schema_name"]}.{source["object_name"]};'
                sql_to_exec = f'SELECT * from {source["schema_name"]}.{source["object_name"]};'
            else:
                sql = (f'SELECT count(0) from {source["schema_name"]}.{source["object_name"]}'
                f'where {extraction_criteria};')
                sql_to_exec = (f'SELECT * from {source["schema_name"]}.'
                f'{source["object_name"]} where {extraction_criteria};')
        task_logger.info("Executing SQL query:%s", sql)
        task_logger.info("sorce SQL:%s",sql_to_exec)
        cursor.execute(sql)
        myresult = cursor.fetchall()
        audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',myresult[-1][-1],
        iter_value,group_no,subtask_no)
        task_logger.info('the number of records read from source table before ingestion:%s',
        myresult[-1][-1])
        for query in pd.read_sql(sql_to_exec,
            conn3, chunksize = json_data["chunk_size"],dtype_backend="pyarrow"):
            count1+=1
            task_logger.info('%s iteration' , str(count1))
            yield query
        conn3.dispose()
        return True
    except sqlalchemy.exc.DatabaseError as error:
        if "ORA-12541" in str(error):
            task_logger.error("No Oracle connection: Check the Oracle Listener")
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id,paths_data, 'STATUS', 'FAILED', iter_value)
        sys.exit()
    except cx_Oracle.DatabaseError as e:
        error, = e.args
        if error.code == 1918:
            task_logger.error("Schema %s does not exist.",{source["schema_name"]})
        elif error.code == 942:  # ORA-00942: table or view does not exist
            task_logger.error("Table or view does not exist.")
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id,paths_data, 'STATUS', 'FAILED', iter_value)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_oracle() is %s", str(error))
        raise error
