""" script for reading data from snowflake table"""
import logging
import sys
import importlib
import pandas as pd
import snowflake.connector
import sqlalchemy

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_snowflake = getattr(module, "establish_conn_for_snowflake")

def read(json_data,connection_file_path,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from snowflake table"""
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from engine_code script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")

        conn3,conn_details = establish_conn_for_snowflake(json_data,'source',
        connection_file_path,paths_data)

        task_logger.info('reading data from snowflake started')
        #task_logger.info('Snowflake connection details: %s', conn_details)
        connection = conn3.raw_connection()
        cursor = connection.cursor()
        database_name = conn_details['database']
        query = f'USE DATABASE {database_name};'
        cursor.execute(query)
        count1 = 0
        sql = f'SELECT count(0) from ({json_data["task"]["source"]["query"]}) as d;'
        cursor.execute(sql)

        myresult = cursor.fetchall()

        audit(json_data, task_id,run_id, paths_data,'SRC_RECORD_COUNT',myresult[-1][-1],iter_value)
        task_logger.info('the number of records present in source table before ingestion:%s',
        myresult[-1][-1])

        task_logger.info('sql_query: %s',json_data["task"]["source"]["query"])

        for query in pd.read_sql(json_data["task"]["source"]["query"],conn3,
        chunksize = json_data["task"]["source"]["chunk_size"],dtype_backend="pyarrow"):
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
