""" importing required modules """
from datetime import datetime
import logging
import sys
import os
import fnmatch
import importlib
import pandas as pd
import requests

task_logger = logging.getLogger('task_logger')
QC_REPORT_LOG='QC for %s check %s|%s|%s'
DTE_FORMAT = "%Y-%m-%d %H:%M:%S"
JSON = '.json'

def dq_audit(task_name,run_id,paths_data,seq_no,check_name,params,active,th_bad_records,check_type,
             check_result, *args):
            #  start_time,end_time,src_rcrds_count,g_recrds_count,b_recrds_count):
    """ create audit json file and audits event records into it"""
    try:
        start_time = args[0]
        end_time = args[1]
        src_rcrds_count = args[2]
        g_recrds_count = args[3]
        b_recrds_count = args[4]
        url = paths_data['audit_api_url']
        new_url = url.replace("/audit", "") + '/dataquality_audit'
        audit_data = [{
                    "task_name": task_name,
                    "runid": run_id,
                    "seq_no": seq_no,
                    "check_name" : check_name,
                    "parameters": params,
                    "active": active,
                    "threshold_bad_records": th_bad_records,
                    "type": check_type,
                    "result": check_result,
                    "src_records_count": src_rcrds_count,
                    "good_records_count": g_recrds_count,
                    "bad_records_count": b_recrds_count,
                    "start_time": start_time,
                    "end_time": end_time
                }]
        response = requests.post(new_url, json=audit_data, timeout=100)
        task_logger.info("dq_audit status code is: %s",response.status_code)
    except Exception as error:
        task_logger.info("error in audit %s.", str(error))
        raise error

def get_files_from_bucket(conn, bucket_name, path, source):
    '''Function to get files from a folder in S3 based on extension'''
    extensions = {
        'csv': ['.csv', '.txt', '.dat'],  # Updated extensions for 'csv'
        'parquet': '.parquet',
        'excel': '.xlsx',
        'json': '.json',
        'xml': '.xml'
    }
    if '*' in path:
        # Handle wildcard path
        prefix, suffix = path.split('*', 1)  # Split only at the first asterisk
        response = conn.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        objects = response.get('Contents', [])

        # Filter the objects to exclude subfolders and retrieve matching files
        if suffix == '.txt':
            # Return only .txt files
            all_files = [obj['Key'] for obj in objects if not obj['Key'].endswith('/')
            and obj['Key'].lower().endswith('.txt')]
        elif suffix == '.dat':
            # Return only .dat files
            all_files = [obj['Key'] for obj in objects if not obj['Key'].endswith('/')
            and obj['Key'].lower().endswith('.dat')]
        else:
            # Return files matching the specified extension(s)
            all_files = [obj['Key'] for obj in objects if not obj['Key'].endswith('/')
            and any(obj['Key'].lower().endswith(ext) for ext in extensions.get(
                source['file_type'], []))]
    else:
        # Non-wildcard path, just list objects with the specified path
        response = conn.list_objects_v2(Bucket=bucket_name, Prefix=path)
        objects = response.get('Contents', [])

        # Filter the objects based on extension mentioned files
        all_files = [obj['Key'] for obj in objects if obj['Key'].lower().endswith(
        tuple(extensions.get(source['file_type'], '')))]
    return all_files

def recon_sum(index, output_df, inputs_required, tgt_df):
    '''function to check wheter the sum between the src and tgt is same or not.'''
    try:
        src_sum = float(inputs_required[0])
        tgt_sum = tgt_df[inputs_required[1]].sum()
        sum_res = 'PASS' if src_sum == tgt_sum else 'FAIL'
        output_df.at[index, 'result'] = sum_res
        task_logger.info('QC for reconciliation_sum check %s|%s|%s',
        src_sum, tgt_sum, sum_res)
        if sum_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Sum of the column-{ inputs_required[1]} is {tgt_sum}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in recon_sum function")
        raise err

def recon_avg(index, output_df, inputs_required, tgt_df):
    '''function to check wheter the avg between the src and tgt is same or not.'''
    try:
        src_avg = float(inputs_required[0])
        tgt_avg = tgt_df[inputs_required[1]].mean()
        avg_res = 'PASS' if src_avg == tgt_avg else 'FAIL'
        output_df.at[index, 'result'] = avg_res
        task_logger.info('QC for reconciliation_avg check %s|%s|%s',src_avg,
        tgt_avg, avg_res)
        if avg_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Avg of the column-{ inputs_required[1]} is {tgt_avg}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in recon_avg function")
        raise err

def recon_min(index, output_df, inputs_required, tgt_df):
    '''function to check wheter the min between the src and tgt is same or not.'''
    try:
        src_min = float(inputs_required[0])
        tgt_min = tgt_df[inputs_required[1]].min()
        min_res = 'PASS' if src_min == tgt_min else 'FAIL'
        output_df.at[index, 'result'] = min_res
        task_logger.info('QC for reconciliation_min check %s|%s|%s',src_min,
        tgt_min, min_res)
        if min_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Minimum Value of the column-{ inputs_required[1]} is {tgt_min}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in recon_min function")
        raise err

def recon_max(index, output_df, inputs_required, tgt_df):
    '''function to check wheter the max between the src and tgt is same or not.'''
    try:
        src_max = float(inputs_required[0])
        tgt_max = tgt_df[inputs_required[1]].max()
        max_res = 'PASS' if src_max == tgt_max else 'FAIL'
        output_df.at[index, 'result'] = max_res
        task_logger.info('QC for reconciliation_max check %s|%s|%s',src_max,
        tgt_max, max_res)
        if max_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Maximum Value of the column-{ inputs_required[1]} is {tgt_max}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in recon_max function")
        raise err

def recon_count(index, output_df, inputs_required, tgt_df):
    '''function to check wheter the count between the src and tgt is same or not.'''
    try:
        src_count = float(inputs_required[0])
        tgt_count = tgt_df[inputs_required[1]].count()
        count_res = 'PASS' if src_count == tgt_count else 'FAIL'
        output_df.at[index, 'result'] = count_res
        task_logger.info('QC for reconciliation_count check %s|%s|%s',src_count,
        tgt_count, count_res)
        if count_res == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'Count of the column-{ inputs_required[1]} is {tgt_count}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(
            DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in recon_count function")
        raise err

def column_count_comp(index, output_df, checks_name, main_json_file ,tgt_df, inputs_required):
    '''function to check whether the column count between the src and tgt are same or not.'''
    try:

        tgt_df.columns = map(str.upper, tgt_df.columns)
        if main_json_file['task']['target']['audit_columns'] == 'active':
            tgt_df = tgt_df.drop(columns=['CRTD_BY','CRTD_DTTM',
            'UPDT_BY','UPDT_DTTM'])

        src_shape = inputs_required[0]
        tgt_shape = tgt_df.shape[1]
        result = 'PASS' if src_shape == tgt_shape else 'FAIL'
        output_df.at[index, 'result'] = result
        task_logger.info(QC_REPORT_LOG, checks_name,src_shape,
        tgt_shape, result)
        if result == 'FAIL':
            output_df.at[index, 'output_reference'] = \
            f'source column count is-{src_shape} and\
            target column count is {tgt_shape}'
        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
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
        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in schema_comp function")
        raise err

def one_to_one_map(index, checks_name, inputs_required, control_table_df, output_df, source_df):
    '''function to check the one to one mapping between the columns'''
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
            # Find duplicates in column 1 and create a list of values
            or_df_1 = source_df.groupby(inputs_required[0])[inputs_required[1]].count()
            dups_1 = list(or_df_1[or_df_1 > 1].index.astype(str))
            # Find duplicates in column 2 and create a list of values
            or_df_2 = source_df.groupby(inputs_required[1])[inputs_required[0]].count()
            dups_2 = list(or_df_2[or_df_2 > 1].index.astype(str))
            # Merge dataframes to get duplicate values and create a set of all duplicates
            if first_max > 1 and second_max == 1:
                out_df = source_df.merge(or_df_1.reset_index(), on=inputs_required[0], how='inner')
                dups = set(out_df[inputs_required[0]+'_x'].astype(str) + '|' + out_df[
                    inputs_required[1]].astype(str))
            elif second_max > 1 and first_max == 1:
                out_df = source_df.merge(or_df_2.reset_index(), on=inputs_required[1], how='inner')
                dups = set(out_df[inputs_required[0]+'_x'].astype(str) + '|' + out_df[
                    inputs_required[1]].astype(str))
            elif second_max > 1 and first_max > 1:
                out_df_1 = source_df.merge(or_df_1.reset_index(),
                                           on=inputs_required[0], how='inner')
                dups_1 = set(out_df_1[inputs_required[0]].astype(str) + '|' + out_df_1[
                    inputs_required[1].astype(str)+'_x'])
                out_df_2 = source_df.merge(or_df_2.reset_index(),
                                           on=inputs_required[1], how='inner')
                dups_2 = set(out_df_2[inputs_required[0]+'_x'].astype(str) + '|' + out_df_2[
                    inputs_required[1]].astype(str))
                dups = dups_1.union(dups_2)
            # Set output reference to list of duplicate values
            output_df.at[index, 'output_reference'] = f'{list(dups)}'
            # Get the entire record for duplicates
            duplicate_records = source_df[source_df[inputs_required[0]].astype(str).isin(dups_1) |
                                           source_df[inputs_required[1]].astype(str).isin(dups_2)]
            output_df.at[
                index, 'unexpected_percent'] = round((len(duplicate_records)/len(source_df))*100, 2)
            output_df.at[
                index, 'unexpected_index_list'] = list(duplicate_records.index)
            # Remove the duplicate records from source_df
            source_df = source_df[~(source_df[inputs_required[0]].astype(str).isin(dups_1) |
                                     source_df[inputs_required[1]].astype(str).isin(dups_2))]
            if control_table_df.at[index, 'threshold_bad_records'] < output_df.at[
                index, 'unexpected_percent']:
                task_logger.warning("Percentage of bad records is: %s which is exceeding"
                "Percentage of Threshold: %s",
                output_df.at[index, 'unexpected_percent'],
                control_table_df.at[index, 'threshold_bad_records'])
            output_df.at[index, 'result'] = 'PASS' if control_table_df.at[
            index, 'threshold_bad_records'] >= output_df.at[index, 'unexpected_percent'] else 'FAIL'
        task_logger.info(QC_REPORT_LOG, checks_name,
                         inputs_required[0], inputs_required[1], output_df.at[index, "result"])
        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in one_to_one_map function")
        raise err

def multi_to_one_map(index, inputs_required, checks_name,control_table_df, output_df, source_df1):
    '''function to check  the multi to one mapping between the columns'''
    try:
        source_df1['compound_check_column'] = source_df1[inputs_required[0]]+'|'+ \
        source_df1[inputs_required[1]]

        if source_df1.shape[0] == source_df1[inputs_required[0]].nunique():
            output_df.at[index,'result'] = 'PASS'
        else:
            list1 = source_df1[inputs_required[0]].tolist()
            duplicates = [i for i in list1 if list1.count(i)>1]
            dups = []
            for row in source_df1['compound_check_column'].tolist():
                if row.rsplit('|',1)[0] in duplicates:
                    dups.append(row)
            output_df.at[index,'output_reference'] = f'{dups}'
            # Find the indices of records in source_df1 that have values in dups
            dups_indices = source_df1[source_df1['compound_check_column'].isin(dups)].index.tolist()

            output_df.at[
                index, 'unexpected_percent'] = round((len(dups)/len(source_df1))*100, 2)
            output_df.at[
                index, 'unexpected_index_list'] = dups_indices
            if control_table_df.at[index, 'threshold_bad_records'] < output_df.at[
            index, 'unexpected_percent']:
                task_logger.warning("Percentage of bad records is: %s which is exceeding"
                " Percentage of Threshold: %s",
                output_df.at[index, 'unexpected_percent'],
                control_table_df.at[index, 'threshold_bad_records'])
            output_df.at[index, 'result'] = 'PASS' if control_table_df.at[
            index, 'threshold_bad_records'] >= output_df.at[index, 'unexpected_percent'] else 'FAIL'
        source_df1.drop('compound_check_column', axis=1, inplace=True)
        task_logger.info(QC_REPORT_LOG, checks_name,
            inputs_required[0], inputs_required[1], output_df.at[index, "result"])
        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
    except Exception as err:
        task_logger.info("error in multi_to_one_map function")
        raise err

# def file_existance_check(index, checks_name, output_df, paths_data,inputs_required,main_json_file):
#     "To check whether mentioned file exists or not"
#     try:
#         filepath = inputs_required[0]
#         filename = inputs_required[1]
#         src = main_json_file['source']
#         tgt = main_json_file['target']
#         new_path = os.path.expanduser(paths_data["folder_path"])+\
#         paths_data['src']+paths_data[ "ingestion_path"]
#         sys.path.insert(0, new_path)
#         connection_code = importlib.import_module("connections")
#         config_file_path = os.path.expanduser(paths_data[
#         "folder_path"])+paths_data["config_path"]
#         local_server = "Local Server"
#         s3 = "AWS S3"
#         remote_server = "Remote Server"
#         # if src in (AWS S3,Local Server,Remote Server):
#         if src in local_server or tgt in local_server:
#             print(filepath+filename)
#             if os.path.exists(filepath+filename):
#                 task_logger.info("File exists")
#             else:
#                 raise FileNotFoundError(f"The file '{filename}' does not exist at '{filepath}'.")
#         elif src in s3 or tgt in s3:
#             json_section = 'source' if src in s3 else 'target'
#             conn, conn_str = connection_code.establish_conn_for_s3(
#             main_json_file,json_section,config_file_path,paths_data)
#             path = filepath+filename
#             bucket_name = conn_str["bucket_name"]
#             source = main_json_file['task']['source'] if src in s3 else \
#             main_json_file['task']['target']
#             all_files = get_files_from_bucket(conn, bucket_name, path, source)
#             # conn.get_object(Bucket=bucket_name, Key=path)['Body']
#             if all_files:
#                 output_df.at[index, 'result'] = 'PASS'
#                 task_logger.info("QC for %s check has been %s", checks_name,
#                                 output_df.at[index, 'result'])
#             else:
#                 output_df.at[index, 'result'] = 'FAIL'
#                 task_logger.info("The file %s does not exist at %s",
#                                 filename, filepath)
#         elif src in remote_server or tgt in remote_server:
#             json_section = 'source' if src in remote_server else 'target'
#             conn, _ = connection_code.establish_conn_for_remoteserver(
#             main_json_file,json_section,config_file_path,paths_data)
#             # Open an SFTP connection
#             sftp = conn.open_sftp()
#             # Retrieve all files in the specified directory
#             all_files = sftp.listdir(filepath)

#             # Filter files based on the wildcard pattern
#             matching_files = []
#             for file in all_files:
#                 if fnmatch.fnmatch(file, filename):
#                     matching_files.append(file)
#             # Process the matching files
#             all_files = [os.path.join(filepath, path) for path in matching_files]
#             if all_files:
#                 output_df.at[index, 'result'] = 'PASS'
#                 task_logger.info("QC for %s check has been %s", checks_name,
#                                 output_df.at[index, 'result'])
#             else:
#                 output_df.at[index, 'result'] = 'FAIL'
#                 task_logger.info("The file %s does not exist at %s",
#                                 filename, filepath)
#         output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)
#     except Exception as error:
#         task_logger.info("error in file existance check function")
#         raise error

def check_local_file(filepath, filename):
    """Check if the file exists locally."""
    full_path = os.path.join(filepath, filename)
    if os.path.exists(full_path):
        task_logger.info("File exists")
        return True
    else:
        task_logger.info("The file '%s' does not exist at '%s'",filename, filepath)

def check_s3_file(filepath, filename, connection_code, main_json_file, config_file_path, paths_data):
    """Check if the file exists in S3."""
    s3 = "AWS S3"
    src = main_json_file['source']
    json_section = 'source' if src == s3 else 'target'
    conn, conn_str = connection_code.establish_conn_for_s3(main_json_file, json_section,
                                                           config_file_path, paths_data)
    path = os.path.join(filepath, filename)
    bucket_name = conn_str["bucket_name"]
    source = main_json_file['task']['source'] if src == s3 else \
    main_json_file['task']['target']
    all_files = get_files_from_bucket(conn, bucket_name, path, source)
    return bool(all_files)

def check_remote_file(filepath, filename, connection_code, main_json_file, config_file_path, paths_data, src):
    """Check if the file exists in remote server."""
    json_section = 'source' if src == "Remote Server" else 'target'
    conn, _ = connection_code.establish_conn_for_remoteserver(
        main_json_file, json_section, config_file_path, paths_data)
    sftp = conn.open_sftp()
    all_files = sftp.listdir(filepath)
    matching_files = [file for file in all_files if fnmatch.fnmatch(file, filename)]
    all_files = [os.path.join(filepath, path) for path in matching_files]
    return bool(all_files)

def file_existance_check(index, checks_name, output_df, paths_data, inputs_required, main_json_file):
    "To check whether mentioned file exists or not"
    # try:
    filepath, filename = inputs_required
    src, tgt = main_json_file['source'], main_json_file['target']
    new_path = os.path.expanduser(paths_data["folder_path"]) + paths_data[
        'src'] + paths_data["ingestion_path"]
    sys.path.insert(0, new_path)
    connection_code = importlib.import_module("connections")
    config_file_path = os.path.expanduser(paths_data["folder_path"]) + paths_data["config_path"]

    local_server = "Local Server"
    s3 = "AWS S3"
    remote_server = "Remote Server"

    if src == local_server or tgt == local_server:
        file_exists = check_local_file(filepath, filename)
    elif src == s3 or tgt == s3:
        file_exists = check_s3_file(filepath, filename, connection_code, main_json_file,
                                    config_file_path, paths_data)
    elif src == remote_server or tgt == remote_server:
        file_exists = check_remote_file(filepath, filename, connection_code, main_json_file,
                                        config_file_path, paths_data, src)
    else:
        task_logger.warning("File Existance check can't be performed on Database Level")
        file_exists = False

    if not file_exists:
        task_logger.info("The file %s does not exist at %s", filename, filepath)

    result = 'PASS' if file_exists else 'FAIL'
    output_df.at[index, 'result'] = result
    task_logger.info("QC for %s check has been %s", checks_name, result)
    output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)

    # except Exception as error:
    #     task_logger.info("error in file existance check function")
    #     raise error

def duplicate_row_check(index, output_df, checks_name, ge_df, control_table_df):
    """To check whether duplicate rows exist or not and apply threshold logic."""
    try:
        duplicates = ge_df.duplicated()
        duplicate_count = duplicates.sum()

        # Get the entire record for duplicates
        duplicate_records = ge_df[duplicates]

        # Calculate the percentage of duplicate records
        unexpected_percent = round((len(duplicate_records) / len(ge_df)) * 100, 2)
        output_df.at[index, 'unexpected_percent'] = unexpected_percent
        output_df.at[index, 'unexpected_index_list'] = list(duplicate_records.index)

        # Threshold check
        threshold = control_table_df.at[index, 'threshold_bad_records']
        result = 'PASS' if threshold >= unexpected_percent else 'FAIL'
        output_df.at[index, 'result'] = result

        # Log the result
        task_logger.info("QC for %s check has been: %s",checks_name,result)

        # Remove the duplicate records from ge_df
        ge_df = ge_df[~duplicates]

        if result == 'FAIL':
            output_df.at[index, 'output_reference'] = \
                f'Number of duplicate rows found: {duplicate_count}\n{duplicate_records}'

        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)

        # Log if the percentage of bad records exceeds the threshold
        if threshold < unexpected_percent:
            task_logger.warning("Percentage of bad records is: %s which is exceeding "
                                "Percentage of Threshold: %s",
                                unexpected_percent,
                                threshold)
            print("control_table_df.at[index, 'threshold_bad_records']", threshold)
            print("output_df.at[index, 'unexpected_percent']", unexpected_percent)

    except Exception as error:
        task_logger.info("error in duplicate_row_check function")
        raise error

def duplicate_column_check(index, output_df, checks_name, ge_df, control_table_df):
    """To check whether duplicate columns exist or not and apply threshold logic."""
    try:
        # Check for duplicate columns
        duplicate_columns = ge_df.columns[ge_df.columns.duplicated()]
        duplicate_count = len(duplicate_columns)

        # Calculate the percentage of duplicate columns
        unexpected_percent = round((duplicate_count / len(ge_df.columns)) * 100, 2)
        output_df.at[index, 'unexpected_percent'] = unexpected_percent
        output_df.at[index, 'unexpected_index_list'] = list(duplicate_columns)

        # Threshold check
        threshold = control_table_df.at[index, 'threshold_bad_records']
        result = 'PASS' if threshold >= unexpected_percent else 'FAIL'
        output_df.at[index, 'result'] = result

        # Log the result
        task_logger.info("QC for %s check has been:%s",checks_name,result)

        if result == 'FAIL':
            output_df.at[index, 'output_reference'] = \
                f'Number of duplicate columns found: {duplicate_count}\n{list(duplicate_columns)}'

        output_df.at[index, 'end_time'] = datetime.now().strftime(DTE_FORMAT)

        # Log if the percentage of bad records exceeds the threshold
        if threshold < unexpected_percent:
            task_logger.warning("Percentage of bad records is: %s which is exceeding "
                                "Percentage of Threshold: %s",
                                unexpected_percent,
                                threshold)
            print("control_table_df.at[index, 'threshold_bad_records']", threshold)
            print("output_df.at[index, 'unexpected_percent']", unexpected_percent)

    except Exception as error:
        task_logger.info("error in duplicate_column_check function")
        raise error


def custom_checks(task_id, run_id, paths_data, iter_value, control_table_df,main_json_file,
                  index,inputs_required,output_df,ge_df,file_path):
    '''function to perform custom_checks'''
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        check_name = control_table_df.at[index, "check"]
        seq_no = int(control_table_df.at[index, 'seq_no'])
        good_records_cnt = 0 if pd.isna(output_df.at[index, 'good_records_count']) else \
        int(output_df.at[index, 'good_records_count'])
        bad_records_cnt = 0 if pd.isna(output_df.at[index,'bad_records_count']) else \
        int(output_df.at[index,'bad_records_count'])
        recon_functions = {
            'avg_reconciliation': recon_avg,
            'min_reconciliation': recon_min,
            'max_reconciliation': recon_max,
            'count_reconciliation': recon_count,
            'sum_reconciliation': recon_sum
        }
        if check_name in recon_functions:
            recon_functions[check_name](index, output_df, inputs_required, ge_df)
        elif check_name == 'column_count_comparison':
            column_count_comp(index,output_df,check_name,main_json_file,ge_df,inputs_required)
        elif check_name == 'one_to_one_mapping':
            one_to_one_map(index, check_name, inputs_required, control_table_df,
                                       output_df, ge_df)
        elif check_name == 'multi_to_one_mapping':
            multi_to_one_map(index, inputs_required, check_name, control_table_df,
                             output_df, ge_df)
        elif check_name == 'duplicate_rows_check':
            duplicate_row_check(index, output_df, check_name, ge_df, control_table_df)
        elif check_name == 'file_existance_check':
            file_existance_check(index,check_name, output_df, paths_data,inputs_required,
                                 main_json_file)
        dq_audit(task_id,run_id,paths_data,seq_no,check_name,
            control_table_df.at[index, "parameters"],control_table_df.at[index, "active"],
            int(control_table_df.at[index, "threshold_bad_records"]),
            control_table_df.at[index, "type"],output_df.at[index, 'result'],
            output_df.at[index, 'start_time'],output_df.at[index, 'end_time'],
            ge_df.shape, good_records_cnt,bad_records_cnt)
        audit(main_json_file, task_id,run_id,paths_data,'CHECK_PERFORMED',control_table_df.at[
            index, "check"],iter_value,None,seq_no)
        audit(main_json_file, task_id,run_id,paths_data,'RESULT',output_df.at[
            index, 'result'],iter_value,None,seq_no)
    except Exception as err:
        update_status_file = getattr(module, "update_status_file")
        update_status_file(task_id,'FAILED',file_path)
        audit(main_json_file, task_id,run_id,paths_data,'STATUS','FAILED', iter_value,None,None)
        task_logger.exception("error in Custom_checks function %s.", str(err))
        sys.exit()
