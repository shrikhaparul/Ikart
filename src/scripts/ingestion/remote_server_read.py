""" script for writing data to S3"""
import logging
import os
import importlib
import sys
import fnmatch
import pandas as pd

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_remoteserver = getattr(module, "establish_conn_for_remoteserver")
module = importlib.import_module("csv_read")
csv_functionality = getattr(module, "csv_functionality")

task_logger = logging.getLogger('task_logger')
ITERATION = 'Number of records read - %s'
CSV = '.csv'
JSON = '.json'

def read_data(json_data, src_file, sftp_client,
              delimiter=",", skip_header=0, quotechar='"', escapechar=None):
    '''read data for different file formats'''
    source = json_data.get('task', {}).get('source', {})

    source_params = {
        'delimiter': source.get('delimiter', delimiter),
        'skip_header': source.get('skip_header', skip_header),
        'quotechar': source.get('quote_char', quotechar) if source.get(
            'quote_char', '') not in {None,'None', 'none', ''} else quotechar,
        'escapechar': source.get('escape_char', escapechar) if source.get(
            'escape_char', '') not in {None,'None', 'none', ''} else escapechar,
        'select_cols': None if not source.get('select_columns') \
        else source['select_columns'].split(','),
        'encoding': source.get('encoding', 'utf-8') if source.get(
            'encoding', '') not in {None,'None', 'none', ''} else 'utf-8'
    }

    default_encoding = "utf-8" if source["encoding"] in (
        None,"None","none","") else source["encoding"]
    default_encoding = "latin1" if source["encoding"] == "other" else default_encoding

    # Now update the 'encoding' parameter in source_params with the calculated default_encoding
    source_params['encoding'] = default_encoding

    remote_file = sftp_client.open(src_file)

    if source['file_type'] == 'json':
        for chunk in pd.read_json(remote_file, encoding=source_params['encoding'],
                                  chunksize=source['chunk_size'], lines=True):
            task_logger.info(ITERATION, chunk.shape[0])
            yield chunk

    elif source['file_type'] == 'parquet':
        datafram = pd.read_parquet(remote_file, engine='auto')
        task_logger.info(ITERATION, datafram.shape[0])
        yield datafram

    elif source['file_type'] == 'xml':
        datafram = pd.read_xml(remote_file)
        task_logger.info(ITERATION, datafram.shape[0])
        yield datafram

    elif source['file_type'] == 'xlsx':
        datafram = pd.read_excel(remote_file)
        task_logger.info(ITERATION, datafram.shape[0])
        yield datafram
    # sftp_client.close()

def read(json_data: dict,config_file_path,task_id,run_id,paths_data,file_path,
         iter_value, skip_header= 0,skip_footer= 0,
         delimiter = ",", quotechar = '"', escapechar = None):
    '''function to read s3 data'''
    try:
        source = json_data["task"]["source"]
        src_file_path = source["file_path"]
        file_name = source["file_name"]
        conn,_ = establish_conn_for_remoteserver(json_data,'source',config_file_path,paths_data)
        # Ensure src_file_path ends with a trailing slash
        if not src_file_path.endswith('/'):
            src_file_path = src_file_path + '/'
        # Open an SFTP connection
        sftp = conn.open_sftp()

        # Retrieve all files in the specified directory
        all_files = sftp.listdir(src_file_path)

        # Filter files based on the wildcard pattern
        matching_files = []
        for file in all_files:
            if fnmatch.fnmatch(file, file_name):
                matching_files.append(file)

        # Process the matching files
        all_files = [os.path.join(src_file_path, path) for path in matching_files]
        # task_logger.info("Matching files %s", all_files)
        task_logger.info("list of files which were read")
        task_logger.info(all_files)
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        if all_files == []:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            default_skip_footer = skip_footer if source["skip_footer"]\
            is None else source["skip_footer"]
            default_delimiter = delimiter if "delimiter" not in source else source["delimiter"]
            default_skip_header = skip_header if source["skip_header"]\
                    is None else source["skip_header"]
            default_quotechar = quotechar if source["quote_char"] in {None,"None","none",""}  else\
            source["quote_char"]
            default_escapechar=escapechar if source["escape_char"] in {None,"None","none",""}  \
            else source["escape_char"]
            default_escapechar = "\t" if default_escapechar == "\\t" else default_escapechar
            default_escapechar = "\n" if default_escapechar == "\\n" else default_escapechar
            default_select_cols = None if source["select_columns"] in (None,"None","none","") else \
            list(source["select_columns"].split(","))
            default_alias_cols = None if source["alias_columns"] in (None,"None","none","") else\
            list(source["alias_columns"].split(","))
            default_encoding = "utf-8" if source["encoding"] in (None,"None","none","") else\
                source["encoding"]
            default_encoding = "latin1" if source["encoding"] == "other" else default_encoding
            dataframes = []  # List to collect dataframes from all files
            for file in all_files:
                if source['file_type'] == 'csv':
                    remote_file = sftp.open(file)
                    data = pd.read_csv(remote_file,encoding=default_encoding,
                    low_memory=False)
                    audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',data.shape[0],
                    iter_value)
                    row_count = data.shape[0]-default_skip_footer
                    task_logger.info("Source file record count is: %s", data.shape[0])
                    var = list(csv_functionality(default_select_cols,default_alias_cols,source,
                                                row_count,file,default_delimiter,
                                                default_quotechar,default_escapechar,
                                                default_encoding,None,default_skip_header))
                elif source['file_type'] in ('json', 'parquet', 'xml', 'xlsx'):
                    var = list(read_data(json_data,file,sftp))
                dataframes.extend(var)  # Add dataframes to the list

            return dataframes  # Return the list of dataframes
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.info("reading_remote_server() is %s", str(error))
        raise error
    