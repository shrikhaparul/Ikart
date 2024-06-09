""" importing modules """
import logging
import os
import sys
import importlib
import pandas as pd
import snowflake.connector
import sqlalchemy

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_snowflake = getattr(module, "establish_conn_for_snowflake")
task_logger = logging.getLogger('task_logger')

def read(json_data,config_file_path,task_id,run_id,paths_data,
    file_path,iter_value,source,group_no,subtask_no):
    """ function for reading data from snowflake table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+\
        paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        conn3,_ = establish_conn_for_snowflake(json_data, 'source',config_file_path,paths_data)
        task_logger.info('reading data from snowflake started')
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        database_name = source['database_name']
        query = f"USE DATABASE {database_name};"
        cursor.execute(query)
        count1 = 0
        tbl_name = source["object_name"]
        task_logger.info("reading from snowflake table: %s",tbl_name)
        schema_name =source["database_name"]+'.'+ source["schema_name"]
        extraction_type = source["extraction_type"]
        extraction_criteria = source["extraction_criteria"]
        if extraction_type == 'Full':
            sql = f'SELECT count(0) from {schema_name}.{tbl_name};'
            sql_to_exec = f'SELECT * from {schema_name}.{tbl_name};'
        elif extraction_type == 'Filter':
            if len(extraction_criteria) == 0:
                sql = f'SELECT count(0) from {source["schema_name"]}.{tbl_name};'
                sql_to_exec = f'SELECT * from {source["schema_name"]}.{tbl_name};'
            else:
                sql = f'SELECT count(0) from {source["schema_name"]}.{tbl_name}'\
                f'where {extraction_criteria};'
                sql_to_exec = f'SELECT * from {source["schema_name"]}.{tbl_name}'\
                f' where {extraction_criteria};'
        task_logger.info("source SQL:%s",sql_to_exec)
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
    except sqlalchemy.exc.ProgrammingError as e:
        # Handle the ProgrammingError
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error("Make sure to call 'USE DATABASE' or use "
                    "qualified names before executing SELECT queries%s",str(e))
        sys.exit()
    except snowflake.connector.Error as e:
        # Handle any invalid schema Snowflake connector errors
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error("the table name or schema in the "
                          "task is incorrect/doesnot exists %s",str(e))
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id, paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_snowflake() is %s", str(error))
        raise error
