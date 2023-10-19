""" importing modules """
from datetime import datetime
import multiprocessing
from multiprocessing.pool import ThreadPool
import logging
import os
import sys
import base64
import glob
import importlib
import great_expectations as ge
import sqlalchemy
import requests
import numpy as np
import pandas as pd
import boto3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

task_logger = logging.getLogger('task_logger')
TABLE_RECORD_COUNT='Total number of records present in above table are %s'
FILE_RECORD_COUNT='Total number of records present in above path are %s'
PRE_OP_STARTED = 'Pre-Check Operation Started'
PRE_OP_ENDED = 'Pre-Check Operation Completed'
QC_REPORT_LOG='QC for %s check %s|%s|%s'
JSON = '.json'

# def encrypt(data):
#     '''function to Encrypting the data'''
#     crypto_key= '8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
#     crypto_iv= 'rBEssDfxofOveRxR'
#     block_size=16
#     key = bytes(crypto_key, 'utf-8')
#     key2 = bytes(crypto_iv, 'utf-8')
#     aes = AES.new(key, AES.MODE_CBC, key2)
#     encrypted = aes.encrypt(pad(data.encode(), block_size))
#     # Make sure to strip "=" padding since urlsafe-base64 node module strips "=" as well
#     return base64.urlsafe_b64encode(encrypted).decode("utf-8").rstrip("=")

def encrypt(message):
    '''function to encrypt the data'''
    KEY = b'8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
    IV = b'rBEssDfxofOveRxR'
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(IV, message.encode('utf-8'), None)
    return ciphertext.hex()

def write_to_txt1(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            # task_logger.info("txt getting called")
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
    except Exception as error:
        task_logger.exception("write_to_txt1: %s.", str(error))
        raise error

def audit(json_data, task_name,run_id,status,value,itervalue,seq_no = None):
    """ create audit json file and audits event records into it"""
    try:
        url = "http://localhost:8080/api/audit"
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    "task/pipeline_name": task_name,
                    "run_id": run_id,
                    "sequence": seq_no,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]
        requests.post(url, json=audit_data, timeout=60)
    except Exception as error:
        task_logger.exception("error in audit %s.", str(error))
        raise error

def recon_sum(index, output_df, inputs_required , src_df, tgt_df):
    '''function to check wheter the sum between the src and tgt is same or not.'''
    try:
        src_sum = src_df[inputs_required[1]].sum()
        tgt_sum = tgt_df[inputs_required[2]].sum()
        sum_res = 'PASS' if src_sum == tgt_sum else 'FAIL'
        output_df.at[index, 'result'] = sum_res
        task_logger.info('QC for reconciliation_sum check %s|%s|%s',
        src_sum, tgt_sum, sum_res)
        if sum_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Sum of the source column-{ inputs_required[1]} is {src_sum},\
            Sum of the target column {inputs_required[2]} is {tgt_sum}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in recon_sum function")
        raise err

def recon_avg(index, output_df, inputs_required , src_df, tgt_df):
    '''function to check wheter the avg between the src and tgt is same or not.'''
    try:
        src_avg = src_df[inputs_required[1]].mean()
        tgt_avg = tgt_df[inputs_required[2]].mean()
        avg_res = 'PASS' if src_avg == tgt_avg else 'FAIL'
        output_df.at[index, 'result'] = avg_res
        task_logger.info('QC for reconciliation_avg check %s|%s|%s',src_avg,
        tgt_avg, avg_res)
        if avg_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Avg of the source column-{inputs_required[1]} is {src_avg},\
            Avg of the target column {inputs_required[2]} is {tgt_avg}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in recon_avg function")
        raise err

def recon_min(index, output_df, inputs_required , src_df, tgt_df):
    '''function to check wheter the min between the src and tgt is same or not.'''
    try:
        src_min = src_df[inputs_required[1]].min()
        tgt_min = tgt_df[inputs_required[2]].min()
        min_res = 'PASS' if src_min == tgt_min else 'FAIL'
        output_df.at[index, 'result'] = min_res
        task_logger.info('QC for reconciliation_min check %s|%s|%s',src_min,
        tgt_min, min_res)
        if min_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Min of the source column-{inputs_required[1]} is {src_min},\
            Min of the target column {inputs_required[2]} is {tgt_min}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in recon_min function")
        raise err

def recon_max(index, output_df, inputs_required , src_df, tgt_df):
    '''function to check wheter the max between the src and tgt is same or not.'''
    try:
        src_max = src_df[inputs_required[1]].max()
        tgt_max = tgt_df[inputs_required[2]].max()
        max_res = 'PASS' if src_max == tgt_max else 'FAIL'
        output_df.at[index, 'result'] = max_res
        task_logger.info('QC for reconciliation_max check %s|%s|%s',src_max,
        tgt_max, max_res)
        if max_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Max of the source column-{inputs_required[1]} is {src_max},\
            Max of the target column {inputs_required[2]} is {tgt_max}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in recon_max function")
        raise err

def recon_count(index, output_df, inputs_required , src_df, tgt_df):
    '''function to check wheter the count between the src and tgt is same or not.'''
    try:
        src_count = src_df[inputs_required[1]].count()
        tgt_count = tgt_df[inputs_required[2]].count()
        count_res = 'PASS' if src_count == tgt_count else 'FAIL'
        output_df.at[index, 'result'] = count_res
        task_logger.info('QC for reconciliation_count check %s|%s|%s',src_count,
        tgt_count, count_res)
        if count_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Count of the source column-{inputs_required[1]} is {src_count},\
            Count of the target column {inputs_required[2]} is {tgt_count}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in recon_count function")
        raise err

def column_count_comp(index, output_df, checks_name, main_json_file , src_df, tgt_df):
    '''function to check whether the column count between the src and tgt are same or not.'''
    try:
        src_df.columns = map(str.upper, src_df.columns)
        tgt_df.columns = map(str.upper, tgt_df.columns)
        if main_json_file['task']['target']['audit_columns'] == 'active':
            tgt_df = tgt_df.drop(columns=['CRTD_BY','CRTD_DTTM',
            'UPDT_BY','UPDT_DTTM'])
        src_shape = src_df.shape[1]
        tgt_shape = tgt_df.shape[1]
        result = 'PASS' if src_df.shape[1] == tgt_df.shape[1] else 'FAIL'
        output_df.at[index, 'result'] = result
        task_logger.info(QC_REPORT_LOG, checks_name,src_shape,
        tgt_shape, result)
        if result == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'source column count is-{src_shape} and\
            target column count is {tgt_shape}'
        output_df.at[index, 'end_time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in column_count_comp function")
        raise err

def schema_comp(index, output_df, checks_name, src_df, tgt_df, main_json_file):
    '''function to check whether the columns and datatype is same or not between the src and tgt.'''
    try:
        src_df.columns = map(str.upper, src_df.columns)
        tgt_df.columns = map(str.upper, tgt_df.columns)
        if main_json_file['task']['target']['audit_columns'] == 'active':
            tgt_df = tgt_df.drop(columns=['CRTD_BY','CRTD_DTTM','UPDT_BY','UPDT_DTTM'])
        src_columns = src_df.columns
        tgt_columns = tgt_df.columns
        src_dtypes = src_df.dtypes
        tgt_dtypes = tgt_df.dtypes
        dtypes1 = [str(i) for i in src_dtypes.tolist()]
        res1 = [i+'|'+j for i,j in zip(src_columns,dtypes1)]
        dtypes2 = [str(i) for i in tgt_dtypes.tolist()]
        res2 = [i+'|'+j for i,j in zip(tgt_columns,dtypes2)]
        if res1 == res2:
            output_df.at[index, 'result'] = "PASS"
        else:
            output_df.at[index, 'result'] = "FAIL"
            source_set = set(res1)
            target_set = set(res2)
            diff_cols = [x for x in source_set if x not in target_set]
            if not diff_cols:
                diff_cols = [x for x in target_set if x not in source_set]
            diff_cols = ','.join(diff_cols)
            output_df.at[index, 'output_reference'] = \
            f'These columns {diff_cols} are creating a schema difference'
        task_logger.info('QC for %s check has been %s', checks_name,
            output_df.at[index, "result"])
        output_df.at[index, 'end_time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in schema_comp function")
        raise err

def one_to_one_map(index, checks_name, inputs_required, output_df, source_df):
    '''function to check  the one to one mapping between the columns'''
    try:
        # Drop duplicate rows based on first two columns
        source_df = source_df.drop_duplicates(subset=[inputs_required[0],
        inputs_required[1]], keep='first')
        # Get maximum count of unique values for both columns
        first_max = source_df.groupby(inputs_required[0])[inputs_required[1]].count().max()
        second_max = source_df.groupby(inputs_required[1])[inputs_required[0]].count().max()
        # Set result to PASS if both maximum counts are 1, else set to FAIL and find duplicates
        if first_max == 1 and second_max == 1:
            output_df.at[index, 'result'] = 'PASS'
        else:
            output_df.at[index, 'result'] = 'FAIL'
            # Find duplicates in column 1 and create a list of values
            or_df_1 = source_df.groupby(inputs_required[0])[inputs_required[1]].count()
            dups_1 = list(or_df_1[or_df_1 > 1].index.str.cat(sep='|'))
            # Find duplicates in column 2 and create a list of values
            or_df_2 = source_df.groupby(inputs_required[1])[inputs_required[0]].count()
            dups_2 = list(or_df_2[or_df_2 > 1].index.str.cat(sep='|'))
            # Merge dataframes to get duplicate values and create a set of all duplicates
            if first_max > 1 and second_max == 1:
                out_df = source_df.merge(or_df_1.reset_index(), on=inputs_required[0], how='inner')
                dups = set(out_df[inputs_required[0]] + '|' + out_df[inputs_required[1]+'_x'])
            elif second_max > 1 and first_max == 1:
                out_df = source_df.merge(or_df_2.reset_index(), on=inputs_required[1], how='inner')
                dups = set(out_df[inputs_required[0]+'_x'] + '|' + out_df[inputs_required[1]])
            elif second_max > 1 and first_max > 1:
                out_df_1 = source_df.merge(or_df_1.reset_index(),
                                           on=inputs_required[0], how='inner')
                dups_1 = set(out_df_1[inputs_required[0]] + '|' + out_df_1[
                    inputs_required[1]+'_x'])
                out_df_2 = source_df.merge(or_df_2.reset_index(),
                                           on=inputs_required[1], how='inner')
                dups_2 = set(out_df_2[inputs_required[0]+'_x'] + '|' + out_df_2[
                    inputs_required[1]])
                dups = dups_1.union(dups_2)
            # Set output reference to list of duplicate values
            output_df.at[index, 'output_reference'] = f'{list(dups)}'
            task_logger.info(QC_REPORT_LOG, checks_name,
            inputs_required[0], inputs_required[1], output_df.at[index, "result"])
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in one_to_one_map function")
        raise err

def multi_to_one_map(index, inputs_required, checks_name, output_df, sr_df):
    '''function to check  the multi to one mapping between the columns'''
    try:
        source_df1 = pd.read_csv(sr_df, na_filter=False)
        source_df1['compound_check_column'] = source_df1[inputs_required[0]]+'|'+ \
        source_df1[inputs_required[1]]
        if source_df1.shape[0] == source_df1['compound_check_column'].nunique():
            if source_df1.shape[0] == source_df1[inputs_required[0]].nunique():
                output_df.at[index,'result'] = 'PASS'
                task_logger.info(QC_REPORT_LOG, checks_name,
            inputs_required[0], inputs_required[1], output_df.at[index, "result"])
            else:
                output_df.at[index,'result'] = 'FAIL'
                list1 = source_df1[inputs_required[0]].tolist()
                duplicates = [i for i in list1 if list1.count(i)>1]
                dups = []
                for row in source_df1['compound_check_column'].tolist():
                    if row.rsplit('|',1)[0] in duplicates:
                        dups.append(row)
                output_df.at[index,'output_reference'] = f'{dups}'
                task_logger.info(QC_REPORT_LOG, checks_name,
            inputs_required[0], inputs_required[1], output_df.at[index, "result"])
        else:
            output_df.at[index,'result'] = 'FAIL'
            list1 = source_df1['compound_check_column'].tolist()
            duplicates = [i for i in list1 if list1.count(i)>1]
            output_df.at[index,'output_reference'] = \
            f'The combination of {inputs_required[0]} and {inputs_required[1]} \
             is not unique - {duplicates}'
            task_logger.info(QC_REPORT_LOG, checks_name,
            inputs_required[0], inputs_required[1], output_df.at[index, "result"])
        output_df.at[index, 'end_time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    except Exception as err:
        task_logger.info("error in multi_to_one_map function")
        raise err

def ge_checks(func_name,default_parameters_dtypes,inputs_required,output_df,index,
              control_table_df,ge_df,main_json_file,task_id,run_id,iter_value):
    '''Function to perform Great_expectations check'''
    # Perform quality checks using Great Expectations library
    try:
        ge_df_func = f"ge_df.{func_name}(" + ','.join([f"'{{{i}}}'" if ele == 'string' else
         f"{{{i}}}" for i, ele in enumerate(
            default_parameters_dtypes)]) + ", result_format='COMPLETE')"
        # task_logger.info("ge_function for default_parameters_dtypes ########### %s", ge_df_func)
        ge_df_func = ge_df_func.format(*inputs_required)
        task_logger.info('GE function generated - %s', ge_df_func)
        res = eval(ge_df_func)
        # Update output_df with result of QA check
        output_df.at[index, 'result'] = 'PASS' if res['success'] is True else 'FAIL'
        task_logger.info('QC for %s check has been %s', control_table_df.at[
            index, "check"], output_df.at[index, "result"])
        # Handle bad records if ignore_bad_records flag is set
        if not res['success'] and control_table_df.at[index, 'ignore_bad_records'] == 'Y':
            output_df.at[index, 'output_reference'] = res['result']
            if 'unexpected_index_list' in res['result']:
                output_df.at[
                    index, 'unexpected_index_list'] = res['result']['unexpected_index_list']
                if control_table_df.at[index, 'threshold_bad_records'] < res[
                    'result']['unexpected_percent']:
                    task_logger.info("$$$$$$$$$$$$$$ %s",(control_table_df.at[index,
                    'threshold_bad_records']))
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
        output_df.at[index, 'end_time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        # task_logger.info("data quality dq_id number from json is:  %s",
        seq_no = int(control_table_df.at[index, 'seq_no'])
        audit(main_json_file, task_id,run_id,'CHECK_PERFORMED',control_table_df.at[
            index, "check"],iter_value,seq_no)
        audit(main_json_file, task_id,run_id,'RESULT',output_df.at[
            index, 'result'],iter_value,seq_no)
        audit(main_json_file, task_id,run_id,'GOOD_RECORD_COUNT',output_df.at[
            index, 'good_records_count'],iter_value,seq_no)
        audit(main_json_file, task_id,run_id,'BAD_RECORD_COUNT',output_df.at[
            index, 'bad_records_count'],iter_value,seq_no)
    except Exception as err:
        task_logger.info("error in GE_check function")
        raise err

def custom_checks(control_table_df,main_json_file,index,inputs_required,output_df,ge_df):
    '''function to perform custom_checks'''
    try:
        check_name = control_table_df.at[index, "check"]
        file_name = main_json_file['task']['source']['file_name']
        source_file_path = main_json_file['task']['source'][
            'file_path'] + file_name + '.csv'
        # Reconciliation or Column Count Comparison check
        if check_name in ('reconciliation', 'column_count_comparison'):
            src_df = pd.read_csv(source_file_path)
            tgt_df = ge_df
            if check_name == 'reconciliation' and inputs_required:
                func = {'sum': recon_sum, 'avg': recon_avg, 'min': recon_min,
                        'max': recon_max, 'count': recon_count}.get(inputs_required[0])
                if func:
                    func(index, output_df, inputs_required, src_df, tgt_df)
            if check_name == 'column_count_comparison' and not inputs_required:
                column_count_comp(index,output_df,check_name,main_json_file,src_df,tgt_df)
        # Schema Comparison check
        elif check_name == 'schema_comparison':
            src_df = pd.read_csv(source_file_path)
            tgt_df = ge_df
            schema_comp(index, output_df, check_name, src_df, tgt_df, main_json_file)
        # if "check" is "multi_to_one_mapping", read source data from file
        elif check_name == 'multi_to_one_mapping':
            sr_df = main_json_file['task']['source']['file_path'] + file_name + '.csv'
            multi_to_one_map(index, inputs_required, check_name, output_df, sr_df)
    except Exception as err:
        task_logger.info("error in Custom_checks function")
        raise err

def run_checks_in_parallel(index, cols, control_table_df, checks_mapping_df, ge_df,
main_json_file,task_id,run_id, file_path,iter_value):
    """Running all the checks specified in control table in parallel"""
    try:
        output_df = pd.DataFrame(columns=cols + ['unexpected_index_list', 'threshold_voilated_flag',
        'run_flag', 'result', 'output_reference', 'start_time', 'end_time','good_records_file',
        'bad_records_file', 'good_records_count', 'bad_records_count'])
        output_df.at[index,'threshold_voilated_flag'] = 'N'
        output_df.at[index, 'run_flag'] = 'N'
        task_logger.info('QC for %s check started', control_table_df.at[index, "check"])
        for col in cols:
            output_df.at[index, col] = control_table_df.at[index, col]
        if control_table_df.at[index, 'active'] == 'Y':
            # set run_flag and start_time
            output_df.at[index, 'run_flag'] = 'Y'
            output_df.at[index, 'start_time'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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
                    task_logger.info("Parameter key is not correct ")
            # Update the 'parameters' column in the DataFrame
            control_table_df.at[index, 'parameters'] = sorted_parameters
            inputs_required = list(control_table_df.at[index, 'parameters'].values())
            # retrieve function name and parameters for great expectations QA check
            ge_flag = checks_mapping_df[checks_mapping_df['func_name'] == func_name]['type'].item()
            default_parameters_dtypes = checks_mapping_df[
                checks_mapping_df['func_name'] == func_name]['parameters'].item().split('|')
            # perform great expectations QA check
            if ge_flag == 'GE':
                ge_checks(func_name,default_parameters_dtypes,inputs_required,output_df,index,
                control_table_df,ge_df,main_json_file,task_id,run_id,iter_value)
            else:
                custom_checks(control_table_df,main_json_file,index,inputs_required,output_df,ge_df)
        return output_df
    except ValueError:
        task_logger.error("func name(check_name) mentioned in the json is \
                          incorrect please check it.")
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED',iter_value)
        return None  # Add a return statement here to handle the exception
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("error in run_checks_in_parallel function %s.", str(error))
        raise error

def connections(ing_type, conn_str, password, main_json_file,task_id,file_path,
                iter_value, run_id):
    '''function to establish the different db connections'''
    try:
        if ing_type in {'postgres_read', 'postgres_write'}:
            conn = sqlalchemy.create_engine(f'postgresql://{conn_str["username"]}'
                f':{password.replace("@", "%40")}@{conn_str["hostname"]}'
                f':{int(conn_str["port"])}/{conn_str["database"]}', encoding='utf-8')
            task_logger.info("Postgres connection established successfully!")
        elif ing_type in {'mysql_read', 'mysql_write'}:
            conn = sqlalchemy.create_engine(f'mysql+pymysql://{conn_str["username"]}'
            f':{password.replace("@", "%40")}@{conn_str["hostname"]}'
            f':{int(conn_str["port"])}/{conn_str["database"]}', encoding='utf-8')
            task_logger.info("mysql connection established successfully!")
        elif ing_type in {'snowflake_read', 'snowflake_write'}:
            if ing_type == 'snowflake_read':
                conn = sqlalchemy.create_engine(f'snowflake://{conn_str["username"]}'
                f':{password.replace("@", "%40")}@{conn_str["account"]}/'
                f':{conn_str["database"]}/{main_json_file["task"]["source"]["schema"]}'
                f'?warehouse={conn_str["warehouse"]}&role={conn_str["role"]}')
            else:
                conn = sqlalchemy.create_engine(f'snowflake://{conn_str["username"]}'
                f':{password.replace("@", "%40")}@{conn_str["account"]}/'
                f':{conn_str["database"]}/{main_json_file["task"]["target"]["schema"]}'
                f'?warehouse={conn_str["warehouse"]}&role={conn_str["role"]}')
                task_logger.info("snowflake connection established successfully!")
        elif ing_type in {'sqlserver_read', 'sqlserver_write'}:
            conn = sqlalchemy.create_engine(f'mssql+pymssql://{conn_str["username"]}'
            f':{password.replace("@", "%40")}@{conn_str["hostname"]}'
            f':{conn_str["port"]}/{conn_str["database"]}', encoding='utf-8')
        else:
            task_logger.info("only ingestion available currently!")
        return conn
    except sqlalchemy.exc.ProgrammingError:
        task_logger.error("the table or connection specified in the command is incorrect")
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        sys.exit()
    except sqlalchemy.exc.OperationalError:
        task_logger.error("The details provided inside the connection file path "
        " is incorrect")
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        sys.exit()
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        task_logger.exception("error in qc_check function %s.", str(error))
        raise error

def aws_s3_conn(ing_type,paths_data,conn_str):
    '''establishing connection for aws s3'''
    if ing_type in {'aws_s3_read', 'aws_s3_write'}:
        decrypt_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
        "ingestion_path"]
        sys.path.insert(0, decrypt_path)
        module = importlib.import_module("utility")
        decrypt = getattr(module, "decrypt")
        d_aws_access_key_id = decrypt(conn_str["access_key"])
        d_aws_secret_access_key = decrypt(conn_str["secret_access_key"])
        conn = boto3.client( service_name= 's3',region_name=
        conn_str["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        task_logger.info("s3 connection established successfully!")
    return conn

def file_reading_df(ing_type, encoding, loc,task_id,file_path,sheetnum,
                 main_json_file, run_id, iter_value):
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
        elif ing_type in {'excel_read', 'excel_write'}:
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
        task_logger.error("the input source file  does not exists or not found")
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        sys.exit()

def postgres_conn(conn_str, password, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions):
    '''function to establish postgres connection'''
    try:
        task_logger.info("entered into postgres read")
        conn = connections(ing_type, conn_str, password, main_json_file,
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
            pd_df = pd.read_sql(f'select * from {loc};', conn)
            sql = f'SELECT count(0) from {loc}'
            myresult = sessions.execute(sql).fetchall()
        task_logger.info('Reading postgres db started at %s table', loc)
        ge_df = ge.from_pandas(pd_df)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in postgres function %s", str(err))
        raise err

def sqlserver_conn(conn_str, password, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions):
    '''function to establish postgres connection'''
    try:
        task_logger.info("entered into sqlserver read")
        conn = connections(ing_type, conn_str, password, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type == 'sqlserver_read':
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
        if ing_type == 'sqlserver_write':
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

def mysql_conn(conn_str, password, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions):
    '''function to establish mysql connection'''
    try:
        conn = connections(ing_type, conn_str, password, main_json_file,
                task_id,file_path,iter_value, run_id)
        if ing_type == 'mysql_read':
            connection = conn.raw_connection()
            cursor = connection.cursor()
            if main_json_file['task']['source']['query'] == " ":
                loc = main_json_file['task']['source']['table_name']
                pd_df = pd.read_sql(f'select * from ({loc})', conn)
                task_logger.info('Reading mysql db started at %s table', loc)
                sql = f'SELECT count(0) from  ({loc})'
            else:
                loc = main_json_file['task']['source']['query']
                pd_df = pd.read_sql(f'{loc}', conn)
                sql = f'SELECT count(0) from  ({loc}) as d;'
            cursor.execute(sql)
            myresult = cursor.fetchall()
        if ing_type == 'mysql_write':
            conn = sessions.connection()
            pd_df = pd.read_sql(f'select * from ({loc})', conn)
            task_logger.info('Reading mysql db started at %s table', loc)
            sql = f'SELECT count(0) from  ({loc})'
            myresult = sessions.execute(sql).fetchall()
        ge_df = ge.from_pandas(pd_df)
        task_logger.info(TABLE_RECORD_COUNT, myresult[-1][-1])
        return ge_df
    except Exception as err:
        task_logger.info("error in mysql function %s", str(err))
        raise err

def snowflake_conn(conn_str, password, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions):
    '''function to establish mysql connection'''
    try:
        conn = connections(ing_type, conn_str, password, main_json_file,
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

def aws_s3_read(conn_str, ing_type, main_json_file,paths_data):
    '''function to read data from aws s3'''
    conn = aws_s3_conn(ing_type,paths_data,conn_str)
    source = main_json_file['task']['source']
    if source['file_type'] in {'csv', 'json','excel', 'parquet', 'xml'}:
        extensions = {'csv': '.csv',
            'parquet': '.parquet',
            'excel': '.xlsx',
            'json': JSON,
            'xml': '.xml'}
        extension = extensions.get(source['file_type'], '')
        file_obj = source['file_path']+source['file_name']+extension
        bucket_name = conn_str["bucket_name"]
        src_file = conn.get_object(Bucket=bucket_name, Key=file_obj)['Body']
        ge_df = ge.read_csv(src_file)
        record_count = ge_df.shape[0]
        task_logger.info(TABLE_RECORD_COUNT, record_count)
    return ge_df

def qc_check(prj_nm,control_table_df, checks_mapping_df, src_file_name, check_type, ing_type,
loc,encoding,sheetnum, conn_str,main_json_file,task_id,run_id, paths_data,file_path,iter_value,
sessions, dq_output_loc=None):
    """Extaracting qc_check related details"""
    try:
        control_table_df = control_table_df[control_table_df[
            'type'] == check_type].reset_index(drop=True)
        cols = control_table_df.columns.tolist()
        resultset = pd.DataFrame(
            columns=cols + [
                'unexpected_index_list', 'threshold_voilated_flag', 'run_flag', 'result',
                'output_reference', 'start_time', 'end_time', 'good_records_file',
                 'bad_records_file', 'good_records_count', 'bad_records_count'])
        row_val = control_table_df.index.values.tolist()
        pool = ThreadPool(multiprocessing.cpu_count())
        #Creating conditions for different file formats
        if ing_type in {'csv_read', 'csv_write', 'parquet_read', 'parquet_write', 'json_read',
                        'json_write', 'excel_read', 'excel_write', 'xml_read', 'xml_write'}:
            ge_df = file_reading_df(ing_type, encoding, loc,task_id,file_path,sheetnum,
                 main_json_file, run_id, iter_value)
        elif ing_type in {'aws_s3_read', 'aws_s3_write'}:
            ge_df = aws_s3_read(conn_str, ing_type, main_json_file,paths_data)
        else:
            if ing_type in {'postgres_read', 'postgres_write', 'mysql_read', 'mysql_write',
                            'snowflake_read','snowflake_write','sqlserver_read',
                            'sqlserver_write'}:
                decrypt_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
                    "ingestion_path"]
                sys.path.insert(0, decrypt_path)
                module = importlib.import_module("utility")
                decrypt = getattr(module, "decrypt")
                password = decrypt(conn_str['password'])
                if ing_type in {'postgres_read', 'postgres_write'}:
                    ge_df = postgres_conn(conn_str, password, loc,ing_type,main_json_file,task_id,
                            file_path,iter_value, run_id,sessions)
                elif ing_type in {'mysql_read', 'mysql_write'}:
                    ge_df = mysql_conn(conn_str, password, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions)
                elif ing_type in {'snowflake_read', 'snowflake_write'}:
                    ge_df = snowflake_conn(conn_str, password, ing_type, main_json_file, loc,
               task_id,file_path,iter_value, run_id,sessions)
                elif ing_type in {'sqlserver_read', 'sqlserver_write'}:
                    ge_df = sqlserver_conn(conn_str, password, loc,ing_type,main_json_file,task_id,
                  file_path,iter_value, run_id,sessions)
        datasets = pool.map(
            lambda x:run_checks_in_parallel(
            x, cols, control_table_df, checks_mapping_df, ge_df, main_json_file, task_id,
            run_id,file_path,iter_value), row_val)
        pool.close()
        for datas in datasets:
            resultset = pd.concat([resultset, datas])
        resultset['unexpected_index_list'] = resultset['unexpected_index_list'].replace(np.nan,'')
        bad_records_indexes = list({
            item for sublist in resultset['unexpected_index_list'].tolist() for item in sublist})
        bad_file_loc = os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["rejected_path"]
        if 'FAIL' in resultset.result.values:
            indexes = list(set(bad_records_indexes))
            bad_records_df = ge_df[ge_df.index.isin(indexes)]
            no_of_bad_records = bad_records_df.shape[0]
            task_logger.info('Total number of bad records are %s', no_of_bad_records)
            bad_records_df.to_csv(
                bad_file_loc + src_file_name +'_' + 'rejected_records_' +
                    datetime.now().strftime("%d_%m_%Y_%H_%M_%S") + '.csv', index=False)
            if 'Y' in resultset['threshold_voilated_flag']:
                good_records_df = pd.DataFrame(columns=ge_df.columns.tolist())
                good_records_df.to_csv(
                    dq_output_loc + src_file_name + '.csv', index=False)
            else:
                good_records_df = ge_df[~ge_df.index.isin(indexes)]
                no_of_good_records = good_records_df.shape[0]
                task_logger.info('Total number of good records are %s', no_of_good_records)
                good_records_df.to_csv(
                    dq_output_loc + src_file_name + '.csv', index=False)
        else:
            resultset['good_records_file'] = ""
            resultset['bad_records_file'] = ""
        resultset['good_records_file'] = dq_output_loc +\
            src_file_name + '_' + datetime.now().strftime("%d_%m_%Y_%H_%M_%S") + '.csv'
        resultset['bad_records_file'] = dq_output_loc +\
            src_file_name + '_' + datetime.now().strftime("%d_%m_%Y_%H_%M_%S") + '.csv'
        resultset = resultset.drop(
        columns = ['unexpected_index_list','output_reference','threshold_voilated_flag',
                   'run_flag'])
        return resultset
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        task_logger.exception("error in qc_check function %s.", str(error))
        raise error

def auto_correction(main_json_file):
    '''function to perform auto correction'''
    task_logger.info("Auto correction process started")
    source = main_json_file['task']['source']
    dq_feature = main_json_file['task']['data_quality_features']
    output_loc = source['file_path']
    src_file_name = source['file_name']
    df1 = pd.read_csv(output_loc+source['file_name']+'.csv')
    df2 = pd.read_csv(dq_feature['dq_lookup_file_path'])
    #Creating Temprary new column(id) in source dataframe
    df1.insert(0, 'temp_id', range(0, 0 + len(df1)))
    #Assigning key_col variable to perform the key_column operation
    key_col = dq_feature['dq_lkup_key_column']
    #merging both dataframe to replace the null values
    for s_col, t_col in key_col.items():
        res=pd.merge(df1, df2, left_on=s_col, right_on=t_col)
        res1 = res.drop(columns=[t_col])
    var = dq_feature['dq_auto_correct_columns']
    for i,j in var.items():
        res1[i] = res1[i].fillna(res[j])
        res1.sort_values(by=['temp_id'],ascending=True,inplace=True)
        res1.pop(j)
        res2 = res1.drop(columns=['temp_id'])
    os.makedirs(output_loc, exist_ok=True)
    res2.to_csv(output_loc+ src_file_name + '.csv', index=False)
    task_logger.info("Generates auto_corrected_records file at %s", output_loc)
    task_logger.info("Auto correction process ended")

def date_mask(msk_date, srcdf):
    '''function to mask the date fields'''
    default_date_pattern = '0' if msk_date[0] == '' else msk_date[0]
    for col in msk_date[1:]:
        if col:
            srcdf[col] = srcdf[col].replace(r'\w', default_date_pattern, regex=True)

def mask_alpha(msk_alpha, srcdf):
    '''function to mask the string fields'''
    default_alpha_pattern = '*' if msk_alpha[0] == '' else msk_alpha[0]
    for col in msk_alpha[1:]:
        if col:
            srcdf[col] = srcdf[col].replace(r'\w', default_alpha_pattern, regex=True)

def data_masking(main_json_file):
    '''Function to perform data_masking'''
    task_logger.info("Data Masking Operation Started")
    source = main_json_file['task']['source']
    src_file_name = source['file_name']
    mask_columns = main_json_file['task']['data_quality_features']['data_masking_columns']
    msk_date = mask_columns.get('msk_date', '').split(',')
    msk_alpha = mask_columns.get('msk_alpha', '').split(',')
    msk_numeric = mask_columns.get('msk_numeric', '').split(',')
    output_loc = source['file_path']
    file_name = output_loc + src_file_name + '.csv'
    srcdf = pd.read_csv(file_name)
    if msk_date:
        date_mask(msk_date, srcdf)
    if msk_alpha:
        mask_alpha(msk_alpha, srcdf)
    if msk_numeric:
        srcdf[msk_numeric] = np.nan
    else:
        print('Error in data_masking_column formats.')
    srcdf.to_csv(output_loc+ src_file_name +'.csv',encoding='utf-8', index=False)
    task_logger.info("generates data_masking_file at: %s", output_loc)
    task_logger.info("Data masking Operation Ended")

def data_encryption(main_json_file):
    '''function to perform data_encryption'''
    task_logger.info("Data Encryption Started")
    src_file_name=main_json_file['task']['source']['file_name']
    output_loc = main_json_file['task']['source']['file_path']
    cols_required = main_json_file['task']['data_quality_features'][
                    'data_encryption_columns']
    cols=cols_required
    source_file = output_loc+ src_file_name +'.csv'
    encrypt_df = pd.read_csv(source_file)
    for val in cols.split(','):
        for vals in encrypt_df[val]:
            res1 = vals
            res = encrypt(vals)
            encrypt_df[val] = encrypt_df[val].replace(res1, res)
    encrypt_df.to_csv(output_loc+ src_file_name +'.csv',encoding='utf-8', index=False)
    task_logger.info("Generates data_encrypted_records file at %s", output_loc)
    task_logger.info("Data Encryption Completed")

def get_source_connection_details(main_json_file, config_file_path, paths_data):
    '''function to get the connection strings for source and targets'''
    try:
        src_conn_str = ''
        source_type = main_json_file['task']['source']['source_type']
        get_config_section_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
        "ingestion_path"]
        sys.path.insert(0, get_config_section_path)
        module = importlib.import_module("utility")
        get_config_section = getattr(module, "get_config_section")
        if source_type in {'postgres_read','mysql_read','snowflake_read',
                           'sqlserver_read','aws_s3_read'}:
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
    return '0' if source_type == 'excel_read' and main_json_file[
        'task']['source']['sheet_name'] == '' else None

def get_default_file_location(main_json_file):
    '''function to get the default file extension based on source type'''
    source_type = main_json_file['task']['source']['source_type']
    if source_type in {'csv_read', 'json_read','excel_read', 'parquet_read'}:
        file_name = main_json_file['task']['source']['file_name']
        file_path = main_json_file['task']['source']['file_path']
        extensions = {'csv_read': '.csv',
            'parquet_read': '.parquet',
            'excel_read': '.xlsx',
            'json_read': JSON}
        extension = file_path + file_name + extensions.get(source_type, '')
    else:
        extension = 'None'
    return extension

def get_table_or_query(main_json_file):
    '''function to get the table or query mentioned in the json'''
    if main_json_file['task']['source']['query'] == " ":
        src_tbl_name = main_json_file['task']['source']['table_name']
    else:
        src_tbl_name = main_json_file['task']['source']['query']
    return src_tbl_name

def qc_check_function_calling(prj_nm,main_json_file,paths_data,task_id,
    run_id,file_path,iter_value,cm_json_file, config_file_path):
    '''function to call the qc_check function based on source type'''
    control_table = pd.DataFrame(main_json_file['task']['data_quality'])
    checks_mapping = pd.DataFrame(cm_json_file['checks_mapping'])
    output_loc = os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
    paths_data["source_files_path"]
    conn_str = get_source_connection_details(main_json_file,
                                            config_file_path, paths_data)
    default_encoding = get_default_encoding(main_json_file)
    default_sheetnum = get_default_sheetnum(main_json_file)
    # defaault file path based on source_type
    def_loc = get_default_file_location(main_json_file)
    source = main_json_file['task']['source']
    if source['source_type'] in {'csv_read', 'parquet_read', \
                         'excel_read', 'xml_read', 'json_read','aws_s3_read'}:
        pre_check_result = qc_check(
        prj_nm,control_table, checks_mapping, source[
        'file_name'],'pre_check', source['source_type'],
        def_loc, default_encoding, default_sheetnum,conn_str,
        main_json_file,task_id,run_id,paths_data,file_path,iter_value,None,output_loc)
    elif source['source_type'] in {'postgres_read', 'mysql_read',
                                    'snowflake_read', 'sqlserver_read'}:
        src_tbl_name = get_table_or_query(main_json_file)
        pre_check_result = qc_check(
        prj_nm, control_table, checks_mapping, source[
        'table_name'],'pre_check', main_json_file['task'][
        'source']['source_type'], src_tbl_name,default_encoding, default_sheetnum,
        conn_str,main_json_file,task_id,run_id,paths_data,file_path,
        iter_value,None,output_loc)
    return pre_check_result

def qc_pre_check(prj_nm,main_json_file,cm_json_file,paths_data,config_file_path,task_id,run_id,
                 file_path,iter_value):
    """Function to perform pre_check operation"""
    try:
        if "task" in main_json_file and "data_quality_features" in main_json_file["task"]:
            task_logger.info("Data quality feature is present in the json")
            #if all the data_quality features set to N then precheck operation started
            dq_features = main_json_file['task']['data_quality_features']
            task_logger.info(PRE_OP_STARTED)
            if dq_features['dq_auto_correction_required']=='N' and \
            dq_features['data_masking_required'] == 'N' and \
            dq_features['data_encryption_required'] == 'N' and \
            dq_features['data_decryption_required'] == 'N':
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            #auto_correction, data_masking and data_encryption enabling
            elif dq_features['dq_auto_correction_required'] == 'Y' and dq_features[
                'data_masking_required'] == 'Y' and dq_features['data_encryption_required'] == 'Y':
                auto_correction(main_json_file)
                data_masking(main_json_file)
                data_encryption(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            # both auto_correction and data_masking enabling
            elif dq_features['dq_auto_correction_required'] == 'Y' \
                and dq_features['data_masking_required'] == 'Y':
                auto_correction(main_json_file)
                data_masking(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            #both auto_correction and data_encryption enabling
            elif dq_features['dq_auto_correction_required'] == 'Y' \
                and dq_features['data_encryption_required'] == 'Y':
                auto_correction(main_json_file)
                data_encryption(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            # calling auto_correction function
            elif dq_features['dq_auto_correction_required'] == 'Y':
                auto_correction(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            #Data Masking
            elif dq_features['data_masking_required'] == 'Y':
                data_masking(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            #Data Encryption
            elif dq_features['data_encryption_required']=='Y':
                data_encryption(main_json_file)
                pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
                task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            task_logger.info(PRE_OP_ENDED)
        else:
            task_logger.info("Data quality feature is not present in the json")
            task_logger.info(PRE_OP_STARTED)
            pre_check_result = qc_check_function_calling(prj_nm,main_json_file,paths_data,
            task_id,run_id,file_path,iter_value,cm_json_file, config_file_path)
            task_logger.info(PRE_OP_ENDED)
        return pre_check_result
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        task_logger.exception("error in qc_pre_check function %s.", str(error))
        raise error

def get_target_connection_details(main_json_file, config_file_path, paths_data):
    '''function to get the connection strings for source and targets'''
    try:
        get_config_section_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
        "ingestion_path"]
        sys.path.insert(0, get_config_section_path)
        module = importlib.import_module("utility")
        get_config_section = getattr(module, "get_config_section")
        if main_json_file['task']['target']['target_type'] in {'postgres_write', 'mysql_write',
        'snowflake_write','sqlserver_write'}:
            tgt_conn_str =  get_config_section(
                config_file_path+main_json_file["task"]['target']["connection_name"]+JSON
                ) if main_json_file['task']['target']['connection_name'] != '' else ''
        else:
            tgt_conn_str = 'None'
        return tgt_conn_str
    except KeyError:
        task_logger.error('Connection name might incorrect check once')

def decryption(main_json_file, paths_data, output_loc):
    '''function to decrypt the data'''
    try:
        # Get columns to be decrypted and file paths
        cols_required = main_json_file['task']['data_quality_features'][
            'data_decryption_columns']
        src_file_name = main_json_file['task']['source']['source_file_nmae']
        output_file_path = main_json_file['task']['data_quality_features'][
            'dq_output_file_path']
        decrypt_path = output_file_path + paths_data["engine_path"]
        list_of_files = glob.glob(f'{output_file_path}*.csv')
        list_of_encrypted_files = [f for f in list_of_files if f.startswith(
            f'{output_file_path}{src_file_name}')]
        source_file = max(list_of_encrypted_files, key=os.path.getctime, default=None)
        decrypt_df = pd.read_csv(source_file)
        # Decrypt columns
        sys.path.insert(0, decrypt_path)
        module = importlib.import_module("utility")
        decrypt = getattr(module, "decrypt")
        for col in cols_required.split(','):
            decrypt_df[col] = decrypt_df[col].apply(decrypt)
        # Write decrypted data to file
        output_file_name = \
        f'{src_file_name}_decrypted_records_{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.csv'
        output_file_path = output_loc + output_file_name
        decrypt_df.to_csv(output_file_path, encoding='utf-8', index=False)
        return output_file_path
    except Exception as err:
        task_logger("Error in decryption function %s", str(err))
        raise err

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
    if main_json_file['task']['target']['target_type'] == 'excel_write':
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
        output_loc = os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["rejected_path"]
        target = main_json_file['task']['target']
        # Reprocessing of bad records file
        if "task" in main_json_file and "data_quality_features" in main_json_file["task"]:
            if main_json_file['task']['data_quality_features']['data_decryption_required']=='N':
                if target['target_type'] in {'csv_write',
                'parquet_write', 'excel_write', 'xml_write', 'json_write'}:
                    post_check_result = qc_check(
                    prj_nm, control_table, checks_mapping, target[
                    'file_name'],'post_check', target['target_type'], target[
                    'file_path']+target[
                    'file_name'], default_encoding, default_sheetnum,tgt_conn_str,
                    main_json_file,task_id,run_id, paths_data,file_path,iter_value,None,output_loc)
                elif target['target_type'] in {'postgres_write',
                'mysql_write','sqlserver_write'}:
                    post_check_result = qc_check(prj_nm, control_table, checks_mapping, target[
                    'table_name'],'post_check', target['target_type'], target[
                    'table_name'], default_encoding, default_sheetnum,tgt_conn_str,
                    main_json_file,task_id,run_id, paths_data,file_path,iter_value,
                    sessions,output_loc)
                elif target['target_type'] in {'snowflake_write'}:
                    post_check_result = qc_check(prj_nm, control_table, checks_mapping, target[
                    'table_name'],'post_check', main_json_file['task'][
                    'target']['target_type'], tgt_conn_str["database"]+'.'+main_json_file[
                    'task']['target']['schema']+'.'+target[
                    'table_name'], default_encoding, default_sheetnum, tgt_conn_str,
                    main_json_file,task_id,run_id,paths_data,file_path,iter_value,
                    sessions,output_loc)
            if main_json_file['task']['data_quality_features']['data_decryption_required'] == 'Y':
                output_file_path = decryption(main_json_file, paths_data, output_loc)
                target_type = target['target_type']
                if target_type in {'csv_write', 'parquet_write', 'excel_write', 'xml_write',
                                'json_write'}:
                    target_file = target['file_name']
                    post_check_result = qc_check(control_table, checks_mapping, target_file,
                    'post_check', target_type, output_file_path,default_encoding, default_sheetnum,
                    tgt_conn_str, main_json_file, task_id, run_id,output_file_path,
                    file_path, iter_value,sessions, output_loc)
                elif target_type in {'postgres_write', 'mysql_write', 'snowflake_write',
                                     'sqlserver_write'}:
                    target_table = target['table_name']
                    post_check_result = qc_check(control_table, checks_mapping, target_table,
                    'post_check',target_type, target_table,default_encoding, default_sheetnum,
                    tgt_conn_str,main_json_file, task_id, run_id,output_file_path,
                    file_path, iter_value,sessions, output_loc)
        else:
            if target['target_type'] in {'csv_write',
                'parquet_write', 'excel_write', 'xml_write', 'json_write'}:
                post_check_result = qc_check(
                prj_nm, control_table, checks_mapping, target[
                'file_name'],'post_check', main_json_file['task'][
                'target']['target_type'], target[
                'file_path']+target[
                'file_name'], default_encoding, default_sheetnum,tgt_conn_str,
                main_json_file,task_id,run_id, paths_data,file_path,iter_value,None,output_loc)
            elif target['target_type'] in {'postgres_write','mysql_write','sqlserver_write'}:
                post_check_result = qc_check(
                prj_nm, control_table, checks_mapping, target[
                'table_name'],'post_check', main_json_file['task'][
                'target']['target_type'], target[
                'table_name'], default_encoding, default_sheetnum,tgt_conn_str,
                main_json_file,task_id,run_id, paths_data,file_path,iter_value,sessions,output_loc)
            elif target['target_type'] in {'snowflake_write'}:
                post_check_result = qc_check(
                prj_nm, control_table, checks_mapping, target[
                'table_name'],'post_check', target['target_type'], tgt_conn_str[
                "database"]+'.'+target['schema']+'.'+target[
                'table_name'], default_encoding, default_sheetnum, tgt_conn_str,
                main_json_file,task_id,run_id,paths_data,file_path,iter_value,sessions,output_loc)
        task_logger.info("Post_check operation completed")
        return post_check_result
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,'STATUS','FAILED', iter_value)
        task_logger.error("error in qc_post_check function %s.", str(error))
        raise error

def qc_report(pre_check_result,post_check_result,new_path,file_path,iter_value,json_data,
              task_id,run_id):
    """Function to generate qc_report"""
    try:
        #Concatinating the pre_check and post_check results into final_check_result
        output_loc = new_path
        final_check_result = pd.concat([pre_check_result, post_check_result], axis=0)
        final_check_result = final_check_result.reset_index(drop=True)
        final_check_result.to_csv(output_loc + 'qc_report_' + datetime.now().strftime(
            "%d_%m_%Y_%H_%M_%S") + '.csv',index=False)
        task_logger.info("qc_report generated")
        return final_check_result
    except Exception as error:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED', iter_value)
        task_logger.exception("error in qc_report function %s.", str(error))
        raise error
