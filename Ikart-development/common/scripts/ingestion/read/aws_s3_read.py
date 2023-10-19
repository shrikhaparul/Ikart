""" script for writing data to S3"""
import logging
import os
import importlib
import sys
from io import StringIO
from io import BytesIO
import zipfile
import pandas as pd

module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
module = importlib.import_module("connections")
establish_conn_for_s3 = getattr(module, "establish_conn_for_s3")

task_logger = logging.getLogger('task_logger')
ITERATION = '%s iteration'
CSV = '.csv'
JSON = '.json'

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

def get_files_from_bucket(conn, bucket_name, path, json_data):
    '''Function to get the mentioned files from s3'''
    # List all objects in the bucket
    response = conn.list_objects_v2(Bucket=bucket_name, Prefix=path)
    objects = response.get('Contents', [])
    source = json_data['task']['source']
    if source['file_type'] in {'csv', 'json','excel', 'parquet', 'xml'}:
        extensions = {'csv': '.csv',
            'parquet': '.parquet',
            'excel': '.xlsx',
            'json': '.json',
            'xml': '.xml'}
        # extension = extensions.get(source['file_type'], '')
    # Filter the objects based on extension mentioned files
    return [obj['Key'] for obj in objects if obj['Key'].lower().endswith(extensions.get(
        source['file_type'], ''))]

def get_row_count(conn,bucket_name,file):
    '''Function to get the row count from diiferent file formats'''
    response = conn.get_object(Bucket=bucket_name, Key=file)
    file_object = response['Body'].read().decode('utf-8')
    dataframe = pd.read_csv(StringIO(file_object))
    rows_count = len(dataframe)
    return rows_count

def get_row_count_s3(conn,bucket_name,file_key,file_extension):
    '''function to get the row count of file from s3'''
    # Extract the bucket name and object key from the S3 file pat
    # Download the file from S3
    response = conn.get_object(Bucket=bucket_name, Key=file_key)
    file_content = response['Body'].read()
    if file_extension == 'csv':
        # Count the rows using pandas
        df = pd.read_csv(BytesIO(file_content))
        row_count = len(df)
    elif file_extension == 'excel':
        # Read the Parquet file using pandas
        df = pd.read_excel(BytesIO(file_content))
        row_count = len(df)
    elif file_extension == 'parquet':
        # Read the Parquet file using pandas
        df = pd.read_parquet(BytesIO(file_content))
        row_count = len(df)
    elif file_extension == 'json':
        # Decode the file content
        # decoded_content = file_content.decode('utf-8')
        # Count the rows using pandas
        df = pd.read_json(BytesIO(file_content))
        row_count = len(df)
    elif file_extension == 'zip':
        # Extract the file from the ZIP archive
        zip_archive = zipfile.ZipFile(BytesIO(file_content))
        extracted_file_name = zip_archive.namelist()[0]
        extracted_file_content = zip_archive.read(extracted_file_name)
        # Determine the file format of the extracted file
        extracted_file_extension = extracted_file_name.split('.')[-1].lower()
        if extracted_file_extension == 'csv':
            # Decode the extracted file content
            decoded_content = extracted_file_content.decode('utf-8')
            # Count the rows using pandas
            df = pd.read_csv(BytesIO(decoded_content))
            row_count = len(df)
        elif extracted_file_extension == 'parquet':
            # Read the extracted Parquet file using pandas
            df = pd.read_parquet(BytesIO(extracted_file_content))
            row_count = len(df)
        else:
            raise ValueError(f"Unsupported file format inside \
                             the ZIP archive: {extracted_file_extension}")
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    return row_count

def read_data_with_or_without_chunk(json_data,src_file,default_header,row_count,
        delimiter = ",", skip_header= 0, quotechar = '"', escapechar = None):
    '''read data with or without considering the json'''
    source = json_data['task']['source']
    default_delimiter = delimiter if source["delimiter"]==" " else\
    source["delimiter"]
    default_skip_header = skip_header if source["skip_header"]==" " else \
    source["skip_header"]
    default_quotechar = quotechar if source["quote_char"]==" " else\
    source["quote_char"]
    default_escapechar=escapechar if source["escape_char"]=="none" \
    else source["escape_char"]
    default_select_cols = None if source["select_columns"]==" " else\
    list(source["select_columns"].split(","))
    default_alias_cols = None if source["alias_columns"]==" " else\
    list(source["alias_columns"].split(","))
    default_encoding = "utf-8" if source["encoding"]==" " else\
    source["encoding"]
    count1 = 0
    if source['chunk_size'] == "None":
        #chunk size must be greater than or equal to one
        if source['file_type'] == 'csv':
            datafram = pd.read_csv(src_file,
            names = default_alias_cols,header = default_header,sep = default_delimiter,
            usecols = default_select_cols,skiprows = default_skip_header,nrows = row_count,
            quotechar = default_quotechar,escapechar = default_escapechar,
            encoding = default_encoding)
            yield datafram
        if source['file_type'] == 'excel':
            datafram = pd.read_excel(src_file, names=default_alias_cols,
                                      header=default_header,usecols=default_select_cols,
                                      skiprows=default_skip_header, nrows=row_count)
            yield datafram
        elif source['file_type'] == 'xml':
            datafram = pd.read_xml(src_file, encoding=default_encoding, names=default_alias_cols)
            yield datafram
        elif source['file_type'] == 'json':
            datafram = pd.read_json(src_file, encoding=default_encoding)
            yield datafram
        elif source['file_type'] == 'parquet':
            datafram = pd.read_parquet(src_file, engine='auto')
            yield datafram
        count1 = 1 + count1
        task_logger.info(ITERATION , str(count1))
        task_logger.info("Number of rowes presnt in the above file are %s", datafram.shape[0])
    else:
        if source['file_type'] == 'csv':
            for chunk in pd.read_csv(src_file,
            names = default_alias_cols,header = default_header,sep = default_delimiter,
            usecols = default_select_cols,skiprows = default_skip_header,nrows = row_count,
            chunksize = source["chunk_size"],
            quotechar = default_quotechar, escapechar = default_escapechar,
            encoding = default_encoding):
                count1 = 1 + count1
                task_logger.info(ITERATION , str(count1))
                yield chunk
        elif source['file_type'] == 'json':
            for chunk in pd.read_json(src_file, encoding=default_encoding,
                                      chunksize = source["chunk_size"],lines=True):
                count1 = 1 + count1
                task_logger.info(ITERATION , str(count1))
                yield chunk
        task_logger.info("Reading data without using chunk")

def read(json_data: dict,config_file_path,task_id,run_id,paths_data,file_path,
         iter_value, skip_header= 0,skip_footer= 0):
    '''function to read s3 data'''
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        source = json_data['task']['source']
        conn,connection_details = establish_conn_for_s3(json_data,'source',config_file_path)
        bucket_name = connection_details["bucket_name"]
        path = source['file_path']+source['file_name']
        all_files = get_files_from_bucket(conn, bucket_name, path, json_data)
        task_logger.info("list of files which were read")
        task_logger.info(all_files)
        if all_files == []:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            default_skip_header = skip_header if source["skip_header"] ==" " else \
            source["skip_header"]
            default_skip_footer = skip_footer if source["skip_footer"] ==" " else \
            source["skip_footer"]
            for file in all_files:
                file_extension = source['file_type']
                rows_count = get_row_count_s3(conn,bucket_name,file,file_extension)
                audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',rows_count,
                iter_value)
                row_count = rows_count-default_skip_header-default_skip_footer
                src_file = conn.get_object(Bucket=bucket_name, Key=file)['Body']
                if source["select_columns"] != " " and source["alias_columns"] != " ":
                    default_header = 0
                    var = read_data_with_or_without_chunk(json_data,src_file,
                                                          default_header,row_count)
                elif (source["select_columns"] != " " and source["alias_columns"] == " ") or \
                (source["select_columns"] == " " and source["alias_columns"] != " "):
                    default_header = 'infer' if source["alias_columns"]== " " else 0
                    var = read_data_with_or_without_chunk(json_data,src_file,
                                                            default_header,row_count)
                elif source["select_columns"] == " " and source["alias_columns"] == " ":
                    default_header ='infer' if source["alias_columns"] ==\
                    " " else None
                    var = read_data_with_or_without_chunk(json_data,src_file,
                                                          default_header,row_count)
                return var
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.info("reading_s3() is %s", str(error))
        raise error
