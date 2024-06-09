""" script for writing data to S3"""
import logging
import os
import importlib
import sys
from io import StringIO
from io import BytesIO
import zipfile
import gzip
import tarfile
import bz2
import io
import pandas as pd

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
module = importlib.import_module("connections")
establish_conn_for_s3 = getattr(module, "establish_conn_for_s3")

task_logger = logging.getLogger('task_logger')
ITERATION = '%s iteration'
CSV = '.csv'
JSON = '.json'

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
            source['object_type'], []))]
    else:
        # Non-wildcard path, just list objects with the specified path
        response = conn.list_objects_v2(Bucket=bucket_name, Prefix=path)
        objects = response.get('Contents', [])

        # Filter the objects based on extension mentioned files
        all_files = [obj['Key'] for obj in objects if obj['Key'].lower().endswith(
            tuple(extensions.get(source['object_type'], '')))]
    return all_files

def get_row_count(conn,bucket_name,file):
    '''Function to get the row count from diiferent file formats'''
    response = conn.get_object(Bucket=bucket_name, Key=file)
    file_object = response['Body'].read().decode('utf-8')
    dataframe = pd.read_csv(StringIO(file_object))
    rows_count = len(dataframe)
    return rows_count

def get_row_count_s3(conn,bucket_name,file_key,file_extension):
    '''function to get the row count of file from s3'''
    # Extract the bucket name and object key from the S3 file path
    # Download the file from S3
    response = conn.get_object(Bucket=bucket_name, Key=file_key)
    file_content = response['Body'].read()
    if file_extension == 'csv':
        # Count the rows using pandas
        data_frame = pd.read_csv(BytesIO(file_content))
        row_count = data_frame.shape[0]
    elif file_extension == 'excel':
        # Read the Parquet file using pandas
        data_frame = pd.read_excel(BytesIO(file_content))
        row_count = len(data_frame)
    elif file_extension == 'parquet':
        # Read the Parquet file using pandas
        data_frame = pd.read_parquet(BytesIO(file_content))
        row_count = len(data_frame)
    elif file_extension == 'json':
        # Decode the file content
        # decoded_content = file_content.decode('utf-8')
        # Count the rows using pandas
        data_frame = pd.read_json(BytesIO(file_content))
        row_count = len(data_frame)
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
            data_frame = pd.read_csv(BytesIO(decoded_content))
            row_count = len(data_frame)
        elif extracted_file_extension == 'parquet':
            # Read the extracted Parquet file using pandas
            data_frame = pd.read_parquet(BytesIO(extracted_file_content))
            row_count = len(data_frame)
        else:
            raise ValueError(f"Unsupported file format inside \
                             the ZIP archive: {extracted_file_extension}")
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")
    return row_count

def read_data_with_or_without_chunk(json_data,source,src_file,row_count,
        skip_header= 0, skip_footer= 0, escapechar = None):
    '''read data with or without considering the json'''
    default_skip_footer = skip_footer if source["skip_footer"]\
            is None else source["skip_footer"]
    default_skip_header = skip_header if source["skip_header"]\
            is None else source["skip_header"]
    default_escapechar=escapechar if source["escape_char"] in {None,"None","none",""}  \
    else source["escape_char"]
    default_escapechar = "\t" if default_escapechar == "\\t" else default_escapechar
    default_escapechar = "\n" if default_escapechar == "\\n" else default_escapechar
    default_encoding = "utf-8" if source["encoding"] in (None,"None","none","") else\
        source["encoding"]
    default_encoding = "latin1" if source["encoding"] == "other" else default_encoding
    task_logger.info("Source chunk size is: %s", source['chunk_size'])
    count1 = 0
    if json_data['chunk_size'] is None:
        #chunk size must be greater than or equal to one
        if source['object_type'] == 'csv':
            datafram = pd.read_csv(src_file)
            yield datafram
        if source['object_type'] == 'excel':
            datafram = pd.read_excel(src_file, skiprows=default_skip_header, nrows=row_count)
            yield datafram
        elif source['object_type'] == 'xml':
            datafram = pd.read_xml(src_file, encoding=default_encoding)
            yield datafram
        elif source['object_type'] == 'json':
            datafram = pd.read_json(src_file, encoding=default_encoding)
            yield datafram
        elif source['object_type'] == 'parquet':
            datafram = pd.read_parquet(src_file, engine='auto')
            yield datafram
        count1 = 1 + count1
        task_logger.info(ITERATION , str(count1))
        task_logger.info("Number of rowes presnt in the above file are %s", datafram.shape[0])
    else:
        if source['object_type'] == 'json':
            for chunk in pd.read_json(src_file, encoding=default_encoding,
                                      chunksize = json_data["chunk_size"],lines=True):
                count1 = 1 + count1
                task_logger.info(ITERATION , str(count1))
                yield chunk
        elif source['object_type'] == 'xlsx':
            sheet_name = 0
            if source["header"] == "Y":
                use_header = True
            else:
                use_header = False
            use_header=0 if use_header else None
            # Determine the compression format based on file extension
            file_extension = os.path.splitext(src_file)[1].lower()

            if file_extension == '.gz':
                with gzip.open(src_file, 'rb') as gz_file:
                    excel_data = pd.read_excel(gz_file, sheet_name=sheet_name)
            elif file_extension == '.zip':
                with zipfile.ZipFile(src_file, 'r') as zipf:
                    with zipf.open(zipf.namelist()[0]) as excel_file:
                        excel_data = pd.read_excel(excel_file, sheet_name=sheet_name)
            elif file_extension == '.tar':
                with tarfile.open(src_file, 'r') as tar:
                    with tar.extractfile(tar.getnames()[0]) as excel_file:
                        excel_data = pd.read_excel(excel_file, sheet_name=sheet_name)
            elif file_extension == '.bz2':
                with bz2.BZ2File(src_file, 'rb') as bz2_file:
                    excel_data = pd.read_excel(bz2_file, sheet_name=sheet_name)
            else:
                excel_data = pd.read_excel(src_file, sheet_name=sheet_name, header=use_header)

            row_count = excel_data.shape[0] - default_skip_header - default_skip_footer
            task_logger.info("The number of records in the source file is: %s", row_count)
            if use_header != 0:
                excel_data.columns = [f"column{i+1}" for i in range(len(excel_data.columns))]
            dataframe = excel_data.iloc[:row_count]
            yield dataframe
        elif source['object_type'] == 'xml':
            datafram = pd.read_xml(src_file,xpath='./*',parser='lxml',\
            encoding = source["encoding"])
            datafram.reset_index(drop=True, inplace=True)
            yield datafram
        elif source['object_type'] == 'parquet':
            datafram = pd.read_parquet(src_file, engine='auto')
            print("Dtataframe shape is:", datafram.shape)
            yield datafram

def csv_functionality(json_data,source,row_count,file,default_delimiter,
    default_quotechar,default_escapechar,default_encoding,compression,default_skip_header):
    """function to consider different parameters in place"""
    if source["header"] == "Y":
        use_header = True
    else:
        row_count = row_count + 1
        use_header = False
    # Read the CSV data from the file
    for csv_chunk in pd.read_csv(file, header=0 if  use_header else None,
    chunksize=json_data["chunk_size"], names = None,
    sep = default_delimiter, usecols = None,
    nrows = row_count,
    quotechar = default_quotechar, escapechar = default_escapechar,
    encoding = default_encoding,compression=compression):
        if not use_header:
            csv_chunk.columns = [
                f"column{i+1}" for i in range(len(csv_chunk.columns))]
        if default_skip_header > 0:
            csv_chunk = csv_chunk.iloc[default_skip_header:]
        yield csv_chunk

def read(json_data: dict,config_file_path,task_id,run_id,paths_data,file_path,
         iter_value,source,group_no,subtask_no, skip_header= 0,skip_footer= 0,
         delimiter = ",", quotechar = '"', escapechar = None):
    '''function to read s3 data'''
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        conn,connection_details = establish_conn_for_s3(json_data,'source',config_file_path,
        paths_data)
        bucket_name = connection_details["bucket_name"]
        path = source['file_path']+source['object_name']
        all_files = get_files_from_bucket(conn, bucket_name, path, source)
        task_logger.info("list of files which were read")
        task_logger.info(all_files)
        if all_files == []:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["object_name"])
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',
            iter_value,group_no,subtask_no)
            sys.exit()
        else:
            default_skip_footer = skip_footer if source["skip_footer"]\
            is None else source["skip_footer"]
            dataframes = []  # List to collect dataframes from all files
            for file in all_files:
                file_extension = source['object_type']
                rows_count = get_row_count_s3(conn,bucket_name,file,file_extension)
                audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',rows_count,
                iter_value,group_no,subtask_no)
                default_delimiter = delimiter if "delimiter" not in source else source["delimiter"]
                default_skip_header = skip_header if source["skip_header"]\
                        is None else source["skip_header"]
                default_quotechar = quotechar if source["quote_char"] in {None,"None","none",""}\
                 else source["quote_char"]
                default_escapechar=escapechar if source["escape_char"] in {None,"None","none",""}  \
                else source["escape_char"]
                default_escapechar = "\t" if default_escapechar == "\\t" else default_escapechar
                default_escapechar = "\n" if default_escapechar == "\\n" else default_escapechar
                default_encoding = "utf-8" if source["encoding"] in (None,"None","none","") else\
                    source["encoding"]
                default_encoding = "latin1" if source["encoding"] == "other" else default_encoding
                row_count = rows_count-default_skip_footer
                task_logger.info("source record count is: %s",row_count)
                # Get the object from S3
                response = conn.get_object(Bucket=bucket_name, Key=file)
                # Get the streaming body from the response
                streaming_body = response['Body']
                # Read the streaming body into a buffer
                buffer_data = io.BytesIO(streaming_body.read())

                if source['object_type'] == 'csv':
                    var = list(csv_functionality(json_data,source,
                                                row_count,buffer_data,default_delimiter,
                                                default_quotechar,default_escapechar,
                                                default_encoding,None,default_skip_header))
                elif source['object_type'] in ('json', 'parquet', 'xml', 'xlsx'):
                    var = list(read_data_with_or_without_chunk(json_data,source,buffer_data,
                                                            row_count))

                dataframes.extend(var)  # Add dataframes to the list

            return dataframes  # Return the list of dataframes
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value,group_no,subtask_no)
        task_logger.info("reading_s3() is %s", str(error))
        raise error
