""" importing modules """
from datetime import datetime
import multiprocessing
from multiprocessing.pool import ThreadPool
import logging
import os
import sys
import glob
import importlib
import fnmatch
import re
import requests
import great_expectations as ge
import sqlalchemy
import numpy as np
import pandas as pd
import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from custom_qc import custom_checks, dq_audit

task_logger = logging.getLogger('task_logger')
TABLE_RECORD_COUNT='Total number of records present in above table are %s'
FILE_RECORD_COUNT='Total number of records present in above path are %s'
PRE_OP_STARTED = 'Pre-Check Operation Started'
PRE_OP_ENDED = 'Pre-Check Operation Completed'
DTE_FORMAT = "%Y-%m-%d %H:%M:%S"
JSON = '.json'
KEY = b'8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
IV = b'rBEssDfxofOveRxR'

def encrypt(message):
    '''function to encrypt the data'''
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(IV, message.encode('utf-8'), None)
    return ciphertext.hex()

def update_status_file(task_id,status,file_path):
    """updates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("status txt file does not exist")
    except Exception as error:
        task_logger.exception("update_status_file: %s.", str(error))
        raise error

def ge_checks(func_name,default_parameters_dtypes,inputs_required,output_df,index,
              control_table_df,ge_df,main_json_file,task_id,run_id,iter_value,paths_data,file_path):
    '''Function to perform Great_expectations check'''
    # Perform quality checks using Great Expectations library
    try:
        ge_df_func = f"ge_df.{func_name}(" + ','.join([f"'{{{i}}}'" if ele == 'string' else
            f"{{{i}}}" if ele != 'list' else "[{}]".format(','.join([f"'{val.strip()}'"
        for val in inputs_required[i].split(',')])) for i, ele in enumerate(
            default_parameters_dtypes)]) + ", result_format='COMPLETE')"
        ge_df_func = ge_df_func.format(*inputs_required)
        task_logger.info('GE function generated - %s', ge_df_func)
        res = eval(ge_df_func)
        if 'unexpected_percent' in res['result'] and control_table_df.at[
            index, 'threshold_bad_records'] is not None:
            output_df.at[index, 'unexpected_percent'] = round(res['result']['unexpected_percent'], 2)
            if control_table_df.at[index, 'threshold_bad_records'] < res[
                'result']['unexpected_percent']:
                task_logger.warning("Percentage of bad records is: %s which is exceeding "
                "Percentage of Threshold: %s",
                round(res['result']['unexpected_percent'], 2),
                control_table_df.at[index, 'threshold_bad_records'])
            output_df.at[index, 'result'] = 'PASS' if control_table_df.at[
            index, 'threshold_bad_records'] >= res['result']['unexpected_percent'] or res[
            'success'] is True else 'FAIL'
        else:
            output_df.at[index, 'result'] = 'PASS' if res['success'] is True else 'FAIL'
        task_logger.info('QC for %s check has been %s', control_table_df.at[
            index, "check"], output_df.at[index, "result"])
        # Handle bad records
        if not res['success']:
            output_df.at[index, 'output_reference'] = res['result']
            if 'unexpected_index_list' in res['result']:
                output_df.at[
                    index, 'unexpected_index_list'] = res['result']['unexpected_index_list']
                if control_table_df.at[index, 'threshold_bad_records'] < res[
                    'result']['unexpected_percent']:
                    output_df.at[index, 'threshold_voilated_flag'] = 'Y'
            else:
                output_df.at[index, 'unexpected_index_list'] = []
        # Update output_df with QA check metrics
        if isinstance(output_df.at[index, 'unexpected_index_list'], float):
            output_df.at[index, 'unexpected_index_list'] = []
        output_df.at[index, 'good_records_count'] = ge_df.shape[0] - len(output_df.at[
            index, 'unexpected_index_list'])
        output_df.at[index, 'bad_records_count'] = ge_df.shape[0] - output_df.at[
            index, 'good_records_count']
        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
        output_df.at[index, 'src_column_count'] = ge_df.shape[1]
        # task_logger.info("data quality dq_id number from json is:  %s",
        seq_no = int(control_table_df.at[index, 'seq_no'])
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        threshold_bad_records = 0 if pd.isna(control_table_df.at[index, "threshold_bad_records"]) else \
        int(control_table_df.at[index, "threshold_bad_records"])
        # print(output_df.to_string())
        dq_audit(task_id,run_id,paths_data,seq_no,control_table_df.at[index, "check"],
            control_table_df.at[index, "parameters"],control_table_df.at[index, "active"],
            threshold_bad_records,
            control_table_df.at[index, "type"],output_df.at[index, 'result'],
            output_df.at[index, 'start_time'],output_df.at[index, 'end_time'],
            ge_df.shape, int(output_df.at[index, 'good_records_count']),
            int(output_df.at[index,'bad_records_count']))
        audit(main_json_file, task_id,run_id,paths_data,'CHECK_PERFORMED',control_table_df.at[
            index, "check"],iter_value,None,seq_no)
        audit(main_json_file, task_id,run_id,paths_data,'RESULT',output_df.at[
            index, 'result'],iter_value,None,seq_no)
    # except AttributeError:
    #     task_logger.error('AttributeError: %s', sys.exc_info()[0])
        # engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        # sys.path.insert(0, engine_code_path)
        # module = importlib.import_module("engine_code")
        # audit = getattr(module, "audit")
        # update_status_file(task_id,'FAILED',file_path)
        # audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        # sys.exit()
    # except AttributeError:
    #     task_logger.error('AttributeError: %s', sys.exc_info()[0])
    #     update_status_file(task_id,'FAILED',file_path)
    #     audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,None)
    #     return None
    except Exception as error:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.exception("error in run_checks_in_parallel function %s.", str(error))
        sys.exit()

def run_checks_in_parallel(index, cols, control_table_df, checks_mapping_df, ge_df,
main_json_file,task_id,run_id, file_path,iter_value,paths_data):
    """Running all the checks specified in control table in parallel"""
    try:
        output_df = pd.DataFrame(columns=cols + ['unexpected_index_list', 'threshold_voilated_flag',
        'run_flag', 'result', 'output_reference','unexpected_percent', 'start_time', 'end_time',
        'good_records_file','bad_records_file', 'good_records_count', 'bad_records_count',
        'src_column_count'])
        output_df.at[index,'threshold_voilated_flag'] = 'N'
        output_df.at[index, 'run_flag'] = 'N'
        for col in cols:
            output_df.at[index, col] = control_table_df.at[index, col]
        if control_table_df.at[index, 'active'] == 'Y':
            # set run_flag and start_time
            task_logger.info('QC for %s check started', control_table_df.at[index, "check"])
            output_df.at[index, 'run_flag'] = 'Y'
            output_df.at[index, 'start_time'] = datetime.now().strftime(DTE_FORMAT)
            # retrieve check name and input parameters
            checks_nm = control_table_df.at[index, 'check']
            func_name = 'expect_' + checks_nm
            mapping_order = checks_mapping_df[checks_mapping_df['func_name'] == func_name][
                'arguments'].values[0].split('|')
            # Create a new dictionary with sorted values
            sorted_parameters = {}
            for key in mapping_order:
                if key in control_table_df.at[index, 'parameters']:
                    sorted_parameters[key] = control_table_df.at[index, 'parameters'][key]
                else:
                    task_logger.error("Parameter key is not correct ")
            # Update the 'parameters' column in the DataFrame
            control_table_df.at[index, 'parameters'] = sorted_parameters
            date_formats_pattern = r'%[mMdDyYHhIiSs/\-]+'  # Regex pattern to match date formats
            parameters_values = list(control_table_df.at[index, 'parameters'].values())
            # Convert each value to uppercase, except for values that match the date format regex pattern
            if checks_nm not in 'file_existance_check':
                inputs_required = [str(value).upper() if not re.match(date_formats_pattern, str(value)) \
                                else str(value) for value in parameters_values]
            else:
                inputs_required = list(control_table_df.at[index, 'parameters'].values())

            # retrieve function name and parameters for great expectations QA check
            ge_flag = checks_mapping_df[checks_mapping_df['func_name'] == func_name]['type'].item()
            default_parameters_dtypes = checks_mapping_df[
                checks_mapping_df['func_name'] == func_name]['parameters'].item().split('|')
            # perform great expectations QA check
            if ge_flag == 'GE':
                ge_checks(func_name,default_parameters_dtypes,inputs_required,output_df,index,
              control_table_df,ge_df,main_json_file,task_id,run_id,iter_value,paths_data,file_path)
            else:
                custom_checks(task_id, run_id, paths_data, iter_value, control_table_df,
                              main_json_file,index,inputs_required,output_df,ge_df,file_path)
        return output_df
    except KeyError as error:
        task_logger.error("Key Error Occured %s", str(error))
        update_status_file(task_id,'FAILED',file_path)
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,None)
    # Add a return statement here to handle the exception
    except ValueError:
        task_logger.error("func name(check_name) mentioned in the json is \
                          incorrect please check it.")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,None)
        return None  # Add a return statement here to handle the exception
    # except AttributeError:
    #     task_logger.error('AttributeError: %s', sys.exc_info()[0])
    #     update_status_file(task_id,'FAILED',file_path)
    #     audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,None)
    #     return None
    except Exception as error:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.exception("error in run_checks_in_parallel function %s.", str(error))
        sys.exit()

def connections(paths_data,ing_type, main_json_file,task_id,file_path,
                iter_value, run_id):
    '''function to establish the different db connections'''
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        new_path = os.path.expanduser(paths_data["folder_path"])+\
        paths_data['src']+paths_data[ "ingestion_path"]
        sys.path.insert(0, new_path)
        connection_code = importlib.import_module("connections")
        config_file_path = os.path.expanduser(paths_data[
                "folder_path"])+paths_data["config_path"]
        if ing_type in ('postgres_read','mysql_read', 'snowflake_read', 'mssql_read',
                        'oracle_read','remote_server_read'):
            json_section = 'source'
        else:
            json_section = 'target'
        if ing_type in {'postgres_read', 'postgres_write'}:
            conn, _ = connection_code.establish_conn_for_postgres(
            main_json_file,json_section,config_file_path,paths_data)
            task_logger.info("Postgres connection established successfully!")
        elif ing_type in {'mysql_read', 'mysql_write'}:
            conn, _ = connection_code.establish_conn_for_mysql(
            main_json_file,json_section,config_file_path,paths_data)
            task_logger.info("mysql connection established successfully!")
        elif ing_type in {'snowflake_read', 'snowflake_write'}:
            conn, _ = connection_code.establish_conn_for_snowflake(
            main_json_file,json_section,config_file_path,paths_data)
            task_logger.info("snowflake connection established successfully!")
        elif ing_type in {'mssql_read', 'mssql_write'}:
            conn, _ = connection_code.establish_conn_for_sqlserver(
            main_json_file,json_section,config_file_path,paths_data)
        elif ing_type in {'oracle_read', 'oracle_write'}:
            conn, _ =  connection_code.establish_conn_for_oracle(
             main_json_file,json_section,config_file_path,paths_data)
        elif ing_type in  ('remote_server_read', 'remote_server_write'):
            conn, _ = connection_code.establish_conn_for_remoteserver(
            main_json_file,json_section,config_file_path,paths_data)
        else:
            update_status_file(task_id,'FAILED',file_path)
            audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
            task_logger.error("only ingestion available currently!")
        return conn
    except sqlalchemy.exc.ProgrammingError:
        task_logger.error("the table or connection specified in the command is incorrect")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        sys.exit()
    except sqlalchemy.exc.OperationalError:
        task_logger.error("The details provided inside the connection file path "
        " is incorrect")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',
              iter_value,paths_data,None,None)
        sys.exit()
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED',
              iter_value,paths_data,None,None)
        task_logger.exception("error in connections function %s.", str(error))
        raise error

def aws_s3_conn(ing_type,paths_data,conn_str):
    '''establishing connection for aws s3'''
    if ing_type in {'aws_s3_read', 'aws_s3_write'}:
        decrypt_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+paths_data[
        "ingestion_path"]
        sys.path.insert(0, decrypt_path)
        utility = importlib.import_module("utility")
        decrypt = getattr(utility, "decrypt")
        d_aws_access_key_id = decrypt(conn_str["access_key"],paths_data)
        d_aws_secret_access_key = decrypt(conn_str["secret_access_key"],paths_data)
        conn = boto3.client( service_name= 's3',region_name=
        conn_str["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        task_logger.info("s3 connection established successfully!")
    return conn

def file_reading_df(ing_type, encoding, loc,task_id,file_path,sheetnum,
                 main_json_file, run_id, iter_value,paths_data):
    '''function to read files to convert data into ge dataframe'''
    try:
        if ing_type in {'csv_read', 'csv_write'}:
            pd_df = pd.read_csv(loc, encoding=encoding)
            ge_df = ge.from_pandas(pd_df)
            task_logger.info('Reading csv file started at %s', loc)
        elif ing_type in {'parquet_read', 'parquet_write'}:
            ge_df = ge.read_parquet(loc)
            task_logger.info('Reading parquet file started at %s', loc)
        elif ing_type in {'json_read', 'json_write'}:
            ge_df = ge.read_json(loc, encoding=encoding)
            task_logger.info('Reading json file started at %s', loc)
        elif ing_type in {'xlsx_read', 'xlsx_write'}:
            ge_df = ge.read_excel(loc, sheet_name=sheetnum)
            task_logger.info('Reading excel file started at %s', loc)
        elif ing_type in {'xml_read', 'xml_write'}:
            pd_df = pd.read_xml(loc)
            ge_df = ge.from_pandas(pd_df)
            task_logger.info('Reading xml file started at %s', loc)
        shape_of_records = ge_df.shape
        task_logger.info(FILE_RECORD_COUNT, shape_of_records)
        return ge_df
    except FileNotFoundError:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        task_logger.error("the input source file  does not exists or not found")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        sys.exit()

def postgres_conn(paths_data, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions):
    '''function to establish postgres connection'''
    try:
        task_logger.info("entered into postgres read")
        conn = connections(paths_data,ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type == 'postgres_read':
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                loc = main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from {loc};', conn)
                sql = f'SELECT count(0) from ({loc})'
            else:
                loc = main_json_file['task']['source']['query']
                pd_df = pd.read_sql(f'{loc}', conn)
                sql = f'SELECT count(0) from ({loc}) as d;'
            cursor.execute(sql)
            myresult = cursor.fetchall()
        if ing_type == 'postgres_write':
            conn = sessions.connection()
            schema_name = main_json_file['task']['target']['schema']
            pd_df = pd.read_sql(f'select * from {schema_name}.{loc};', conn)
            sql = f'SELECT count(0) from {schema_name}.{loc}'
            myresult = conn.execute(sql).fetchall()
        task_logger.info('Reading postgres db started at %s table', loc)
        ge_df = ge.from_pandas(pd_df)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in postgres function %s", str(err))
        raise err

def sqlserver_conn(paths_data, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions):
    '''function to establish postgres connection'''
    try:
        task_logger.info("entered into sqlserver read")
        conn = connections(paths_data, ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type == 'mssql_read':
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                loc = main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from {loc};', conn)
                sql = f'SELECT count(0) from ({loc})'
            else:
                loc = main_json_file['task']['source']['query']
                pd_df = pd.read_sql(f'{loc}', conn)
                sql = f'SELECT count(0) from ({loc}) as d;'
                task_logger.info(sql)
            cursor.execute(sql)
            myresult = cursor.fetchall()
        if ing_type == 'mssql_write':
            conn = sessions.connection()
            pd_df = pd.read_sql(f'select * from {loc};', conn)
            sql = f'SELECT count(0) from {loc}'
            myresult = sessions.execute(sql).fetchall()
        task_logger.info('Reading sqlserver db started at %s table', loc)
        ge_df = ge.from_pandas(pd_df)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in sqlserver function %s", str(err))
        raise err

def mysql_conn(paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions):
    '''function to establish mysql connection'''
    try:
        conn = connections(paths_data, ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type in ('mysql_read'):
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                loc = main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from ({loc})', conn)
                sql = f'SELECT count(0) from  ({loc})'
            else:
                loc = main_json_file['task']['source']['query']
                pd_df = pd.read_sql(f'{loc}', conn)
                sql = f'SELECT count(0) from  ({loc}) as d;'
            cursor.execute(sql)
            myresult = cursor.fetchall()
        if ing_type in ( 'mysql_write'):
            conn = sessions.connection()
            pd_df = pd.read_sql(f'select * from ({loc})', conn)
            sql = text(f'SELECT count(0) from  ({loc})')
            myresult = sessions.execute(sql).fetchall()
        ge_df = ge.from_pandas(pd_df)
        task_logger.info("Query using: %s", loc)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in mysql function %s", str(err))
        raise err

def oracle_conn(paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions):
    '''function to establish mysql connection'''
    try:
        conn = connections(paths_data, ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type in ('oracle_read'):
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                location = main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from ({location})', conn)
                sql = f'SELECT count(0) from  ({location})'
            else:
                location = main_json_file['task']['source']['query']
                location = location.replace(";","")
                pd_df = pd.read_sql(location, conn)
                sql = f'SELECT count(*) from ({location})'
            cursor.execute(sql)
            myresult = cursor.fetchall()
        if ing_type in ('oracle_write'):
            conn = sessions.connection()
            schema_name = main_json_file['task']['target']['schema']
            pd_df = pd.read_sql(f'select * from {schema_name}.{loc}', conn)
            sql = text(f'SELECT count(0) from  ({schema_name}.{loc})')
            myresult = sessions.execute(sql).fetchall()
        ge_df = ge.from_pandas(pd_df)
        task_logger.info("Query using: %s", loc)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in oracle function %s", str(err))
        raise err

def snowflake_conn(conn_str, paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions):
    '''function to establish mysql connection'''
    try:
        conn = connections(paths_data,ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type == 'snowflake_read':
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                loc = conn_str["database"]+'.'+main_json_file["task"]["source"][
                "schema"]+'.'+main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from ({loc})', conn)
                sql = f'SELECT count(0) from  ({loc})'
                task_logger.info('Reading snowflake db started at %s table', loc)
            else:
                loc = main_json_file['task']['source']['query']
                pd_df = pd.read_sql(f'{loc}', conn)
                sql = f'SELECT count(0) from  ({loc}) as d;'
            cursor.execute(sql)
            myresult = cursor.execute(sql).fetchall()
        if ing_type == 'snowflake_write':
            conn = sessions.connection()
            pd_df = pd.read_sql(f'select * from ({loc})', conn)
            task_logger.info('Reading snowflake db started at %s table', loc)
            sql = f'SELECT count(0) from  ({loc})'
            myresult = sessions.execute(sql).fetchall()
            task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        ge_df = ge.from_pandas(pd_df)
        return ge_df
    except Exception as err:
        task_logger.info("error in snowflake function %s", str(err))
        raise err

def aws_s3_rw(conn_str, ing_type,paths, section, paths_data):
    '''function to read data from aws s3'''
    conn = aws_s3_conn(ing_type, paths_data, conn_str)
    bucket_name = conn_str["bucket_name"]
    ge_df_list = []
    task_logger.info("List of file which were read for DQ is: %s", paths)
    for path in paths:
        src_file = conn.get_object(Bucket=bucket_name, Key=path)['Body']
        if section['file_type'] == 'csv':
            ge_df = ge.read_csv(src_file)
        elif section['file_type'] == 'xlsx':
            ge_df = ge.read_excel(src_file)
        elif section['file_type'] == 'parquet':
            ge_df = ge.read_parquet(src_file)
        elif section['file_type'] == 'json':
            ge_df = ge.read_json(src_file)
        elif section['file_type'] == 'xml':
            pd_df = pd.read_xml(src_file)
            ge_df = ge.from_pandas(pd_df)
        ge_df_list.append(ge_df)

    # Concatenate all DataFrames
    ge_df = pd.concat(ge_df_list, ignore_index=True)
    record_count = ge_df.shape[0]
    task_logger.info(TABLE_RECORD_COUNT, record_count)
    return ge_df

def remote_server_rw(paths_data, ing_type, main_json_file,
               section,task_id,file_path,iter_value, run_id):
    """function to read data from remote server"""
    conn = connections(paths_data,ing_type, main_json_file,
                task_id,file_path,iter_value, run_id)
    # Open an SFTP connection
    sftp = conn.open_sftp()
    file_path = section["file_path"]
    file_name = section["file_name"]
    # Retrieve all files in the specified directory
    all_files = sftp.listdir(file_path)

    # Filter files based on the wildcard pattern
    matching_files = []
    for file in all_files:
        if fnmatch.fnmatch(file, file_name):
            matching_files.append(file)
    # Process the matching files
    all_files = [os.path.join(file_path, path) for path in matching_files]
    if all_files != []:
        ge_df_list = []
        task_logger.info("List of file which were read for DQ is: %s", all_files)
        for file in all_files:
            remote_file = sftp.open(file)
            if section['file_type'] == 'csv':
                ge_df = ge.read_csv(remote_file)
            elif section['file_type'] == 'xlsx':
                ge_df = ge.read_excel(remote_file)
            elif section['file_type'] == 'parquet':
                ge_df = ge.read_parquet(remote_file)
            elif section['file_type'] == 'json':
                ge_df = ge.read_json(remote_file)
            elif section['file_type'] == 'xml':
                pd_df = pd.read_xml(remote_file)
                ge_df = ge.from_pandas(pd_df)
            ge_df_list.append(ge_df)

        # Concatenate all DataFrames
        ge_df = pd.concat(ge_df_list, ignore_index=True)
        record_count = ge_df.shape[0]
        task_logger.info(TABLE_RECORD_COUNT, record_count)
        sftp.close()
    return ge_df


def qc_check(prj_nm,control_table_df, checks_mapping_df, src_file_name, check_type, *arguments):
#              ing_type,
# loc,encoding,sheetnum, conn_str,main_json_file,task_id,run_id, paths_data,file_path,iter_value,
# sessions, dq_output_loc=None):
    """Extaracting qc_check related details"""
    try:
        ing_type = arguments[0]
        loc = arguments[1]
        encoding = arguments[2]
        sheetnum = arguments[3]
        conn_str = arguments[4]
        main_json_file = arguments[5]
        task_id = arguments[6]
        run_id = arguments[7]
        paths_data = arguments[8]
        file_path = arguments[9]
        iter_value = arguments[10]
        sessions = arguments[11]
        dq_output_loc=arguments[12] if arguments[12] else None

        control_table_df = control_table_df[control_table_df[
            'type'] == check_type].reset_index(drop=True)
        cols = control_table_df.columns.tolist()
        resultset = pd.DataFrame(
            columns=cols + [
                'unexpected_index_list', 'threshold_voilated_flag', 'run_flag', 'result',
                'output_reference', 'unexpected_percent','start_time', 'end_time',
                'good_records_file','bad_records_file', 'good_records_count',
                'bad_records_count', 'src_column_count'])
        row_val = control_table_df.index.values.tolist()
        pool = ThreadPool(multiprocessing.cpu_count())
        #Creating conditions for different file formats
        if ing_type in {'csv_read', 'csv_write', 'parquet_read', 'parquet_write', 'json_read',
                        'json_write', 'xlsx_read', 'xlsx_write', 'xml_read', 'xml_write'}:
            ge_df = file_reading_df(ing_type, encoding, loc,task_id,file_path,sheetnum,
                 main_json_file, run_id, iter_value, paths_data)
        elif ing_type in {'aws_s3_read', 'aws_s3_write'}:
            section = main_json_file['task']['source'] if ing_type == 'aws_s3_read'  else \
                main_json_file['task']['target']
            ge_df = aws_s3_rw(conn_str, ing_type, loc, section, paths_data)
        elif ing_type in {'remote_server_read', 'remote_server_write'}:
            section = main_json_file['task']['source'] if ing_type == 'remote_server_read'  else \
                main_json_file['task']['target']
            ge_df = remote_server_rw(paths_data, ing_type, main_json_file, section, task_id,
                                     file_path,iter_value, run_id)
        else:
            if ing_type in {'postgres_read', 'postgres_write', 'mysql_read', 'mysql_write',
                            'snowflake_read','snowflake_write','mssql_read',
                            'mssql_write','oracle_read', 'oracle_write'}:
                if ing_type in {'postgres_read', 'postgres_write'}:
                    ge_df = postgres_conn(paths_data, loc,ing_type,main_json_file,task_id,
                            file_path,iter_value, run_id,sessions)
                elif ing_type in {'mysql_read', 'mysql_write'}:
                    ge_df = mysql_conn(paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions)
                elif ing_type in {'oracle_read', 'oracle_write'}:
                    ge_df = oracle_conn(paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions)
                elif ing_type in {'snowflake_read', 'snowflake_write'}:
                    ge_df = snowflake_conn(conn_str,paths_data, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions)
                elif ing_type in {'mssql_read', 'mssql_write'}:
                    ge_df = sqlserver_conn(paths_data, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions)
        ge_df.columns = [col.upper() for col in ge_df.columns]
        datasets = pool.map(
            lambda x:run_checks_in_parallel(
            x, cols, control_table_df, checks_mapping_df, ge_df, main_json_file, task_id,
            run_id,file_path,iter_value,paths_data), row_val)
        pool.close()
        for datas in datasets:
            resultset = pd.concat([resultset, datas])
        # print(resultset.to_string())
        resultset['unexpected_index_list'] = resultset['unexpected_index_list'].replace(np.nan,'')
        bad_records_indexes = list({
            item for sublist in resultset['unexpected_index_list'].tolist() for item in sublist})
        bad_file_loc = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "local_repo"]+paths_data["programs"]+prj_nm+paths_data["rejected_path"]
        if 'PASS' in resultset.result.values or 'FAIL' in resultset.result.values:
            indexes = list(set(bad_records_indexes))
            bad_records_df = ge_df[ge_df.index.isin(indexes)]
            src_file_name = src_file_name.split(".")[0]
            write_header = not os.path.exists(bad_file_loc + task_id +'_' + run_id + '.csv')
            if bad_records_df.shape[0] >  0:
                bad_records_df.to_csv(
                    bad_file_loc + task_id +'_' + run_id + '.csv', index=False, mode='a',
                    header=write_header)
                task_logger.info("Rejected Records path: %s", bad_file_loc +
                                task_id +'_' + run_id + '.csv')
            if 'Y' in resultset['threshold_voilated_flag']:
                good_records_df = pd.DataFrame(columns=ge_df.columns.tolist())
            else:
                good_records_df = ge_df[~ge_df.index.isin(indexes)]
        else:
            resultset['good_records_file'] = ""
            resultset['bad_records_file'] = ""
            good_records_df = ge_df
        resultset['bad_records_file'] = dq_output_loc + task_id + '_' + run_id + '.csv'
        resultset = resultset.drop(
        columns = ['ignore_bad_records','good_records_file','bad_records_file',
        'unexpected_index_list','output_reference','threshold_voilated_flag','run_flag'])
        return resultset, good_records_df
    except Exception as error:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.exception("error in qc_check function %s.", str(error))
        sys.exit()

def get_source_connection_details(main_json_file, config_file_path, paths_data):
    '''function to get the connection strings for source and targets'''
    try:
        src_conn_str = ''
        source_type = main_json_file['task']['source']['source_type']
        get_config_section_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
            "src"]+paths_data["ingestion_path"]
        sys.path.insert(0, get_config_section_path)
        utility = importlib.import_module("utility")
        get_config_section = getattr(utility, "get_config_section")
        if source_type in {'postgres_read','mysql_read','snowflake_read',
            'oracle_read', 'mssql_read','aws_s3_read', 'remote_server_read'}:
            if main_json_file['task']['source']['connection_name'] != '':
                src_conn_str = get_config_section(config_file_path + main_json_file[
                'task']['source']['connection_name'] + JSON)
        return src_conn_str
    except KeyError:
        task_logger.error('Connection name might incorrect check once')
        sys.exit()

def get_default_encoding(main_json_file):
    '''function to get the default encoding'''
    source_type = main_json_file['task']['source']['source_type']
    return 'utf-8' if source_type in {'csv_read', 'json_read'} and main_json_file[
        'task']['source']['encoding'] == '' else None

def get_default_sheetnum(main_json_file):
    '''function to get the default sheetnum'''
    source_type = main_json_file['task']['source']['source_type']
    return '0' if source_type == 'xlsx_read' and main_json_file[
        'task']['source']['sheet_name'] == '' else None

def get_table_or_query(main_json_file):
    '''function to get the table or query mentioned in the json'''
    if main_json_file['task']['source']['query'] not in main_json_file['source']:
        src_tbl_name = main_json_file['task']['source']['table_name']
    else:
        src_tbl_name = main_json_file['task']['source']['query']
    return src_tbl_name

def get_file_lists(ing_type, paths_data, conn_str, section):
    """function  to get file list from awss3 bucket"""
    conn = aws_s3_conn(ing_type, paths_data, conn_str)
    if section['file_type'] in {'csv', 'json', 'xlsx', 'parquet', 'xml'}:
        extensions = {'csv': ['.csv', '.txt', '.dat'],
                      'parquet': '.parquet',
                      'xlsx': '.xlsx',
                      'json': '.json',
                      'xml': '.xml'}
        _ = extensions.get(section['file_type'], '')
        file_obj = section['file_path'] + section['file_name']
        bucket_name = conn_str["bucket_name"]

        if '*' in file_obj:
            # Handle wildcard path
            prefix, _ = file_obj.split('*', 1)  # Split only at the first asterisk
            response = conn.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            objects = response.get('Contents', [])
            paths = [obj['Key'] for obj in objects if not obj['Key'].endswith('/')
                     and any(obj['Key'].lower().endswith(ext)
                            for ext in extensions.get(section['file_type'], []))]
        else:
            paths = [file_obj]
    return paths

def qc_check_function_calling(prj_nm,main_json_file,paths_data,task_id,
    run_id,file_path,iter_value,cm_json_file, config_file_path):
    '''function to call the qc_check function based on source type'''
    control_table = pd.DataFrame(main_json_file['task']['data_quality'])
    checks_mapping = pd.DataFrame(cm_json_file['checks_mapping'])
    output_loc = os.path.expanduser(paths_data["folder_path"])+paths_data[
    "local_repo"]+paths_data["programs"]+prj_nm+paths_data["source_files_path"]
    conn_str = get_source_connection_details(main_json_file,
                                            config_file_path, paths_data)
    default_encoding = get_default_encoding(main_json_file)
    default_sheetnum = get_default_sheetnum(main_json_file)
    # defaault file path based on source_type
    # def_loc = get_default_file_location(main_json_file)
    source = main_json_file['task']['source']
    if source['source_type'] in {'csv_read', 'parquet_read', \
                                'xlsx_read', 'xml_read', 'json_read','aws_s3_read'}:
        pattern = f'{source["file_path"]}{source["file_name"]}'
        all_files = glob.glob(pattern)
        if all_files:
            for file in all_files:
                pre_check_result, g_rcrds_df = qc_check(
                prj_nm,control_table, checks_mapping, source[
                'file_name'],'pre_check', source['source_type'],
                file, default_encoding, default_sheetnum,conn_str,
                main_json_file,task_id,run_id,paths_data,file_path,iter_value,None,output_loc)
    if source['source_type'] in {'aws_s3_read'}:
        file = get_file_lists(source['source_type'], paths_data, conn_str, source)
        pre_check_result,g_rcrds_df = qc_check(
        prj_nm,control_table, checks_mapping, source[
        'file_name'],'pre_check', source['source_type'],
        file, default_encoding, default_sheetnum,conn_str,
        main_json_file,task_id,run_id,paths_data,file_path,iter_value,None,output_loc)
    if source['source_type'] in {'remote_server_read'}:
        file = f'{source["file_path"]}{source["file_name"]}'
        pre_check_result,g_rcrds_df = qc_check(
        prj_nm,control_table, checks_mapping, source[
        'file_name'],'pre_check', source['source_type'],
        file, default_encoding, default_sheetnum,conn_str,
        main_json_file,task_id,run_id,paths_data,file_path,iter_value,None,output_loc)
    if source['source_type'] in {'postgres_read', 'mysql_read',
        'snowflake_read', 'mssql_read', 'oracle_read'}:
        src_tbl_name = get_table_or_query(main_json_file)
        pre_check_result,g_rcrds_df = qc_check(
        prj_nm, control_table, checks_mapping, source[
        'table_name'],'pre_check', main_json_file['task'][
        'source']['source_type'], src_tbl_name,default_encoding, default_sheetnum,
        conn_str,main_json_file,task_id,run_id,paths_data,file_path,
        iter_value,None,output_loc)
    return pre_check_result, g_rcrds_df

def qc_pre_check(prj_nm,main_json_file,cm_json_file,paths_data,config_file_path,task_id,run_id,
                 file_path,iter_value):
    """Function to perform pre_check operation"""
    try:
        task_logger.info(PRE_OP_STARTED)
        pre_check_result, g_rcrds_df = qc_check_function_calling(prj_nm,main_json_file,paths_data,
        task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
        task_logger.info(PRE_OP_ENDED)
        return pre_check_result, g_rcrds_df
    except Exception as error:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.exception("error in qc_pre_check function %s.", str(error))
        raise error

def get_target_connection_details(main_json_file, config_file_path, paths_data):
    '''function to get the connection strings for source and targets'''
    try:
        get_config_section_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
        'src']+paths_data["ingestion_path"]
        sys.path.insert(0, get_config_section_path)
        utility = importlib.import_module("utility")
        get_config_section = getattr(utility, "get_config_section")
        if main_json_file['task']['target']['target_type'] in {'postgres_write', 'mysql_write',
        'snowflake_write','mssql_write', 'aws_s3_write', 'remote_server_write', 'oracle_write'}:
            tgt_conn_str =  get_config_section(
                config_file_path+main_json_file["task"]['target']["connection_name"]+JSON
                ) if main_json_file['task']['target']['connection_name'] != '' else ''
        else:
            tgt_conn_str = 'None'
        return tgt_conn_str
    except KeyError:
        task_logger.error('Connection name might incorrect check once')

def def_encoding(main_json_file):
    '''function to get the default encoding'''
    if main_json_file['task']['target']['target_type'] in {'csv_write', 'json_write'}:
        default_encoding = 'utf-8' if main_json_file['task']['target']['encoding']=='' else \
            main_json_file['task']['target']['encoding']
    else:
        default_encoding='None'
    return default_encoding

def def_sheetnum(main_json_file):
    '''function to get the default sheetnum'''
    if main_json_file['task']['target']['target_type'] == 'xlsx_write':
        default_sheetnum = '0' if main_json_file['task']['target']['sheet_name']=='' else \
            main_json_file['task']['target']['sheet_name']
    else:
        default_sheetnum='None'
    return default_sheetnum

def qc_post_check(prj_nm,main_json_file,cm_json_file,paths_data,config_file_path, task_id,run_id,
                  file_path,iter_value,sessions):
    """Function to perform post_check operation"""
    try:
        control_table = pd.DataFrame(main_json_file['task']['data_quality'])
        checks_mapping = pd.DataFrame(cm_json_file['checks_mapping'])
        tgt_conn_str =  get_target_connection_details(main_json_file, config_file_path, paths_data)
        default_encoding = def_encoding(main_json_file)
        default_sheetnum = def_sheetnum(main_json_file)
        task_logger.info("Post_check operation started")
        output_loc = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "local_repo"]+paths_data["programs"]+prj_nm+paths_data["rejected_path"]
        target = main_json_file['task']['target']
        # Reprocessing of bad records file
        if target['target_type'] in {'csv_write',
            'parquet_write', 'xlsx_write', 'xml_write', 'json_write'}:
            post_check_result,_ = qc_check(
            prj_nm, control_table, checks_mapping, target[
            'file_name'],'post_check', main_json_file['task'][
            'target']['target_type'], target[
            'file_path']+target[
            'file_name'], default_encoding, default_sheetnum,tgt_conn_str,
            main_json_file,task_id,run_id, paths_data,file_path,iter_value,None,output_loc)
        elif target['target_type'] in {'aws_s3_write'}:
            file = get_file_lists(target['target_type'], paths_data, tgt_conn_str, target)
            post_check_result,_ = qc_check(
            prj_nm, control_table, checks_mapping, target[
            'file_name'],'post_check', target['target_type'],
            file, default_encoding, default_sheetnum,tgt_conn_str,
            main_json_file,task_id,run_id, paths_data,file_path,iter_value,None,output_loc)
        elif target['target_type'] in {'remote_server_write'}:
            file = f'{target["file_path"]}{target["file_name"]}'
            post_check_result,_ = qc_check(
            prj_nm, control_table, checks_mapping, target[
            'file_name'],'post_check', target['target_type'],
            file, default_encoding, default_sheetnum,tgt_conn_str,
            main_json_file,task_id,run_id, paths_data,file_path,iter_value,None,output_loc)
        elif target['target_type'] in {'postgres_write','mysql_write','mssql_write','oracle_write'}:
            post_check_result,_ = qc_check(
            prj_nm, control_table, checks_mapping, target[
            'table_name'],'post_check', main_json_file['task'][
            'target']['target_type'], target[
            'table_name'], default_encoding, default_sheetnum,tgt_conn_str,
            main_json_file,task_id,run_id, paths_data,file_path,iter_value,sessions,output_loc)
        elif target['target_type'] in {'snowflake_write'}:
            post_check_result,_ = qc_check(
            prj_nm, control_table, checks_mapping, target[
            'table_name'],'post_check', target['target_type'], tgt_conn_str[
            "database"]+'.'+target['schema']+'.'+target[
            'table_name'], default_encoding, default_sheetnum, tgt_conn_str,
            main_json_file,task_id,run_id,paths_data,file_path,iter_value,sessions,output_loc)
        task_logger.info("Post_check operation completed")
        return post_check_result
    except Exception as error:
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.error("error in qc_post_check function %s.", str(error))
        raise error

def qc_report(pre_check_result,post_check_result,new_path,file_path,iter_value,json_data,
              task_id,run_id,paths_data):
    """Function to generate qc_report"""
    try:
        #Concatinating the pre_check and post_check results into final_check_result
        output_loc = new_path
        final_check_result = pd.concat([pre_check_result, post_check_result], axis=0)
        final_check_result = final_check_result.reset_index(drop=True)
        final_check_result.to_csv(output_loc + task_id + "_" + run_id + '.csv',index=False)
        task_logger.info("qc_report generated")
        return final_check_result
    except Exception as error:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,None)
        task_logger.exception("error in qc_report function %s.", str(error))
        raise error
