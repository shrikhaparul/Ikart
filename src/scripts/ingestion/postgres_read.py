""" script for reading data from postgres table"""
import logging
import os
import sys
import importlib
import pandas as pd
import psycopg2
import sqlalchemy

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_postgres = getattr(module, "establish_conn_for_postgres")

task_logger = logging.getLogger('task_logger')

def read(json_data,config_file_path,task_id,run_id,paths_data,file_path,iter_value) -> bool:
    """ function for reading data from postgres table"""
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data["src"]+\
        paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        postgres_conn,_=establish_conn_for_postgres(json_data,'source',config_file_path,paths_data)
        task_logger.info('reading data from postgres started')
        connection = postgres_conn.raw_connection()
        cursor = connection.cursor()
        source = json_data["task"]["source"]
        count1 = 0
        sql = f'SELECT count(0) from ({source["query"]}) as d;'
        task_logger.info(sql)
        cursor.execute(sql)
        myresult = cursor.fetchall()
        audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',myresult[-1][-1],
        iter_value)
        task_logger.info('the number of records read from source table:%s',
        myresult[-1][-1])
        task_logger.info('sql_query: %s',source["query"])
        for query in pd.read_sql(source["query"],
        postgres_conn, chunksize = source["chunk_size"],dtype_backend="pyarrow"):
            count1+=1
            task_logger.info('%s iteration' , str(count1))
            yield query
        postgres_conn.dispose()
        return True
    except psycopg2.ProgrammingError as error:  # Handle table not found issue
        task_logger.error("schema does not exist %s",str(error))
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED',
              iter_value)
        sys.exit()
    except sqlalchemy.exc.OperationalError as error:
        error_message = str(error)
        if "connection failed" in error_message:
            task_logger.error("PostgreSQL connection failed: %s", error_message)
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED', iter_value)
        task_logger.error("PostgreSQL connection failed: %s", error_message)
        sys.exit()
    except psycopg2.Error as e:
        task_logger.error("PostgreSQL error: %s", str(e))
        update_status_file(task_id, 'FAILED', file_path)
        audit(json_data, task_id, run_id, paths_data, 'STATUS', 'FAILED', iter_value)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("read_data_from_postgres() is %s", str(error))
        raise error
