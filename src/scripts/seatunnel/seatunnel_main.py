"""importing modules"""
import importlib
import os
import sys
import json
import logging
import shutil
import time
import re
import subprocess
import datetime
import gzip
import bz2
from io import BytesIO
from io import StringIO
import io
import multiprocessing as mp
import pandas as pd
import boto3
import csv
from io import BytesIO
from io import StringIO
import tempfile
from plugin.seatunnel_operations import operations_performed, get_src_col_nm, get_tgt_col_nm,connect_to_db,get_columns_info_details,get_src_count, get_tgt_count,src_query_funct
from seatunnel_ingestion import SeaTunnel
from plugin.jdbc_plugin import JDBCInPlugin, JDBCOutPugin,FILEINPlugin, FILEOUTPlugin
from plugin.s3_plugin import S3FileOUTPlugin, S3FileINPlugin
from plugin.sftp_plugin import SFTPFILEINPlugin, SFTPFileOUTPlugin

# Initialize the loggers
seatunnel_task_logger = logging.getLogger('seatunnel_task_logger')
task_logger = logging.getLogger('task_logger')
XLSX = '.xlsx'
TXT = '.txt'
JSON = '.json'
CURRENT_TIMESTAMP = "%Y-%m-%d %H:%M:%S"
LOCAL_SERVER = 'Local Server'
AWS_S3= 'AWS S3'
REMOTE_SERVER = 'Remote Server'

###########################################################################################
def get_subtask_details(subtask_section,subtask):
    """ function to get the subtask details"""
    task_logger.info("Getting subtask details for subtask: %s", subtask)
    for i in subtask_section:
        if i['subtask']==subtask:
            return i["source"],i["target"]

##############################################################################################
def get_conn_subtype_type(config_path:str):
    """reads the connection file and returns connection_subtype details as per
       connection name you pass it through the json"""
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            task_logger.info("Fetching connection details from config file: %s", config_path)
            json_data = json.load(jsonfile)
            return json_data["connection_details"],json_data["connection_subtype"]
    except Exception as error:
        task_logger.exception("Error occurred in get_conn_subtype_type(): %s", str(error))
        raise error

############################################################################################
def read_file(file_path,extension,data_pkg):
    """" read different file formats """
    task_logger.info("Reading the file data.")
    if extension in ['xls', 'xlsx']:
        extension = 'excel'
    if extension == 'csv':
        if data_pkg['src_type'] in (LOCAL_SERVER,AWS_S3,REMOTE_SERVER):
            df = pd.read_csv(file_path, dtype_backend="pyarrow",nrows=1000)
        if data_pkg['tgt_type'] in (LOCAL_SERVER,AWS_S3,REMOTE_SERVER) :
            df = pd.read_csv(file_path, dtype_backend="pyarrow")
    elif extension == 'txt':
        df = pd.read_csv(file_path)
    elif extension == 'json':
        try:
            if data_pkg['src_type'] == LOCAL_SERVER or data_pkg['tgt_type'] == LOCAL_SERVER:
                with open(file_path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                    # Attempt to load the entire file as JSON
                    try:
                        data = json.loads("".join(lines))
                        df = pd.DataFrame(data)
                    except json.JSONDecodeError:
                        # If JSONDecodeError occurs, try loading each line as a separate JSON object
                        data = [json.loads(line) for line in lines if line.strip()]
                        df = pd.DataFrame(data)
            elif data_pkg['src_type'] == AWS_S3 or data_pkg['tgt_type'] == AWS_S3:
                task_logger.info("in read_file aws s3 block.")
                json_data = [json.loads(line) for line in file_path.split('\n') if line.strip()]

                # Create DataFrame from JSON data
                df = pd.DataFrame(json_data,dtype_backend="pyarrow")
            elif data_pkg['src_type'] == REMOTE_SERVER or data_pkg['tgt_type'] == REMOTE_SERVER:
                task_logger.info("in read_file remote server block.")
                df = pd.read_json(file_path, dtype_backend='pyarrow', lines=True)
        except FileNotFoundError:
            task_logger.info("File not found: %s", file_path)
        except Exception as error:
            task_logger.info("Error occurred while reading JSON file: %s", error)
            raise error
    elif extension == 'parquet':
       
        df = pd.read_parquet(file_path,dtype_backend='pyarrow')
        
    elif extension == 'excel':
        df = pd.read_excel(file_path, engine='openpyxl')
    else:
        raise ValueError("Unsupported file format. Supported formats are CSV, JSON, and Parquet.")
    return df,"No val"

############################################################################################
def get_fields_n_src_count(content,extension,data_pkg):
    """ getting field and src count"""   
    df,src_cnt = read_file(content,extension,data_pkg)      
    fields = {}
    for col_name, col_type in df.dtypes.items():
        if col_type == 'object':
            col_type = 'string'
        elif col_type == 'int64':
            col_type = 'bigint'
        elif col_type in ('int16', 'int32') :
            col_type = 'int'
        elif col_type == 'float64':
            col_type = 'double'
        elif col_type == 'float32':
            col_type = 'float'
        else:
            col_type = 'string'
        fields[col_name] = col_type
       
    return fields, src_cnt

############################################################################################
def load_parquet_file(data_pkg, local_path):
    """loading parquet file"""
    try:
        task_logger.info("In load_parquet_file function")
        if data_pkg['src_type'] == REMOTE_SERVER:
            local_file_path = local_path + data_pkg['src_details']['object_name']
            remote_filepath = f"{data_pkg['src_details']['file_path']}/{data_pkg['src_details']['object_name']}"
            sftp_conn, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
            sftp_client = sftp_conn.open_sftp()
            sftp_client.get(remote_filepath, local_file_path)
            skip_head = data_pkg['src_details']['skip_header']
            
            fields, _ = get_fields_n_src_count(local_file_path,'parquet',REMOTE_SERVER)
            schema3 = {"fields":fields} 

            source: FILEINPlugin =  FILEINPlugin(file_path = local_file_path, 
                        file_type = 'parquet', skip_header = skip_head,
                        schema = schema3, delimiter =  " ")
        return source, fields
    except Exception:
        task_logger.error("Error in load_parquet_file function")
############################################################################################
def load_zip_files(data_pkg, local_path):
    """Downloads the files to local and process the files using localfile plugin"""
    try:
        if data_pkg['src_type'] == AWS_S3:
            s3_conn, _ = connect_to_db(AWS_S3, data_pkg,'source')
            zip_local_file_path = local_path + data_pkg['src_details']['object_name']
            #downlaod the compressed file from aws.
            s3_conn.download_file(data_pkg['src_conn']['bucket_name'], data_pkg['src_details']['file_path'], zip_local_file_path)
            task_logger.info(f"File copied from S3 to {zip_local_file_path}")
        elif data_pkg['src_type'] == LOCAL_SERVER:
            zip_local_file_path = local_path + data_pkg['src_details']['object_name']
            source_file = f"{data_pkg['src_details']['file_path']}/{data_pkg['src_details']['object_name']}"
            shutil.copy2(source_file, local_path)
        elif data_pkg['src_type'] == REMOTE_SERVER:
            zip_local_file_path = local_path + data_pkg['src_details']['object_name']
            sftp_conn, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
            sftp_client = sftp_conn.open_sftp()
            remote_file = f"{data_pkg['src_details']['file_path']}/{data_pkg['src_details']['object_name']}"
            sftp_client.get(remote_file,zip_local_file_path)
        if data_pkg['src_details']['object_type'] == 'gz':
            with gzip.open(zip_local_file_path, 'rb') as gz_file:
                # Uncompressing the contents of gzip file
                uncompressed_data = gz_file.read()
            file_name = os.path.basename(zip_local_file_path)

            # Construct the path for the extracted file
            extracted_file_path = os.path.join(local_path, file_name[:-3])
            new_file = file_name[:-3]
            _, file_extension = os.path.splitext(new_file)
            # Write the uncompressed data to a new file
            with open(extracted_file_path, 'wb') as extracted_file:
                extracted_file.write(uncompressed_data)

            os.remove(zip_local_file_path)
            extension = file_extension[1:].lower()
        elif data_pkg['src_details']['object_type'] == 'bz2':
            with bz2.open(zip_local_file_path, 'rb') as bz_file:
                # Uncompressing the contents of bzip2 file
                uncompressed_data = bz_file.read()
            file_name = os.path.basename(zip_local_file_path)

            # Construct the path for the extracted file
            extracted_file_path = os.path.join(local_path, file_name[:-4])
            new_file = file_name[:-4]
            _, file_extension = os.path.splitext(new_file)
            # Write the uncompressed data to a new file
            with open(extracted_file_path, 'wb') as extracted_file:
                extracted_file.write(uncompressed_data)

            os.remove(zip_local_file_path)
            extension = file_extension[1:].lower()
        
        
        if extension in ['xls', 'xlsx']:
            extension = 'excel'
        
        fields, src_cnt = get_fields_n_src_count(extracted_file_path,extension,data_pkg['src_type'])
        schema3 = {"fields":fields} 
        src_file_path = extracted_file_path
        skip_head = data_pkg['src_details']['skip_header']
        delimiter = data_pkg['src_details']['delimiter']

        source: FILEINPlugin =  FILEINPlugin(file_path = src_file_path, 
                        file_type =  extension, skip_header = skip_head,
                        schema = schema3, delimiter = delimiter)
        return source, fields, src_cnt 
    except Exception as e:
        task_logger.error("Exception occured in load_zip_files function")
        task_logger.error(e)


############################################################################################
def seatunnel_params(src_inges_type,data_pkg):
    """Function to get the seatunnel parameters based on the type of ingestion."""
    src_details = data_pkg['src_details']
    if src_inges_type == 'DB':
        content = str(src_details['file_path']) + str(src_details['object_name'])
    elif src_inges_type == AWS_S3:
        
        bucket_name = data_pkg['src_conn']['bucket_name']
        s3_file_path = data_pkg['src_details']['file_path']
        s3_conn, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
        response = s3_conn.get_object(Bucket=bucket_name, Key=s3_file_path)
        
        # Read the content of the object
        if data_pkg['src_details']['object_type'] == 'json':
            content = response['Body'].read().decode('utf-8')
        else:
            content = response['Body'].read()
            content = BytesIO(content)
    elif src_inges_type == REMOTE_SERVER:
        
        sftp_conn, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
        sftp_client = sftp_conn.open_sftp()
        file_path = str(src_details['file_path']) + str(src_details['object_name'])

    extension = str(src_details['object_type'])
    
    if extension in ['xls', 'xlsx']:
        extension = 'excel'
    if src_inges_type == REMOTE_SERVER:
        with sftp_client.open(file_path, 'r') as file:
            df,src_cnt = read_file(file,extension,data_pkg)
    else:
        df,src_cnt = read_file(content,extension,data_pkg)   
    fields = {}
    for col_name, col_type in df.dtypes.items():
        if col_type == 'object':
            col_type = 'string'
        elif col_type == 'int64':
            col_type = 'bigint'
        elif col_type in ('int16', 'int32') :
            col_type = 'int'
        elif col_type == 'float64':
            col_type = 'double'
        elif col_type == 'float32':
            col_type = 'float'
        else:
            col_type = 'string'
        fields[col_name] = col_type
        
    return fields, src_cnt
######################################################################################################
def compress_file(directory, file_name, compression):
    """Function to compress a file with options for gzip or bzip2."""
    file_path = os.path.join(directory, file_name)
    try:
        if compression == 'gzip':
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_name}.gz"
        elif compression == 'bzip':
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.bz2", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_name}.bz2"
        else:
            raise ValueError("Unsupported compression type. Supported types are 'gzip' and 'bzip'")
    except Exception as e:
        task_logger.exception("An error occurred: %s", e)
        raise e
############################################################################################
def compress_file_s3(bucket_name, file_key, s3_conn,compression):
    """Compresses a file located in an S3 bucket."""
    try:
        # Download the file object from S3
        response = s3_conn.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response['Body'].read()
        if compression == 'gzip':
            # Compress the file content using gzip
            compressed_file_content = gzip.compress(file_content)
            compressed_file_key = f"{file_key}.gz"
        elif compression == 'bzip':
            # Compress the file content using bzip
            compressed_file_content = bz2.compress(file_content)
            compressed_file_key = f"{file_key}.bz2"
        else:
            raise ValueError("Invalid compression method. Supported methods are 'gzip' and 'bzip'.")
        s3_conn.put_object(Bucket=bucket_name, Key=compressed_file_key,
        Body=compressed_file_content)
        s3_conn.delete_object(Bucket=bucket_name, Key=file_key)
        return compressed_file_key
    except Exception as error:
        # Handle any errors that occur during compression or upload
        task_logger.info("An error occurred: %s", error)
        return None
    
def compress_file_sftp(sftp, filepath, compression):
    """function to compress sftp files"""
    if compression == 'gzip':
        with io.BytesIO() as f_out:
            with gzip.GzipFile(fileobj=f_out, mode='wb') as gz_file:
                with sftp.open(filepath, 'rb') as f_in:  # Open file in binary mode
                    gz_file.write(f_in.read())  # Read and write binary data
            with sftp.open(f"{filepath}.gz", 'wb') as gz_out:  # Open compressed file in binary mode
                gz_out.write(f_out.getvalue())  # Write binary data
        # Remove the original file after compression
        sftp.remove(filepath)
    elif compression == 'bzip':
        with sftp.open(filepath, 'rb') as f_in:
            compressed_data = bz2.compress(f_in.read())

        with sftp.open(f"{filepath}.bz2", 'wb') as bz2_out:
            bz2_out.write(compressed_data)
        sftp.remove(filepath)
############################################################################################
def rename_or_concat_files(directory, prefix, suffix, data_pkg):
    """Rename or concat files based on the number of files generated"""
    files = [filename for filename in os.listdir(directory) if filename.startswith(prefix) and filename.endswith(suffix)]
    
    if len(files) == 1:
        new_filenames = rename_files(directory, prefix, suffix)
    elif len(files) > 1:
        task_logger.info(" concating files")
        new_filenames = concat_files(directory, prefix, suffix, data_pkg)
    else:
        task_logger.info("No files found with the specified prefix and suffix.")
    return new_filenames

##########################################################################################   
def rename_files(directory, prefix, suffix):
    """Rename files"""
    task_logger.info("Renaming the file")
    name_pattern = f"{prefix}_(\d+){suffix}"
    pattern = re.compile(name_pattern)
    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            new_filename = f"{prefix}{suffix}"
            os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))
    return new_filename


############################################################################################
def process_files(data_pkg):
    """Process files for renaming and compression after SeaTunnel job completes."""
    directory = data_pkg['tgt_details'].get("file_path", "")
    object_prefix_name = data_pkg['tgt_details'].get("object_prefix_name", "")
    file_name = data_pkg['tgt_details'].get("object_name", "")
    object_sufix_name = data_pkg['tgt_details'].get("object_sufix_name", "")
    prefix = f"{object_prefix_name}{file_name}_{object_sufix_name}"
    if data_pkg['tgt_details'].get('target_file_format') == "excel":
        suffix = ".xlsx"  # Assuming XLSX is a string constant
    elif data_pkg['tgt_details'].get('target_file_format') == "text":
        suffix = ".txt"   # Assuming TXT is a string constant
    else:
        suffix = f".{data_pkg['tgt_details'].get('target_file_format', '')}"
    compression = data_pkg['tgt_details'].get('compression')
    if compression in ("", None):
        task_logger.info("No compression specified")
    else:
       task_logger.info("compressing the file as %s", compression)

    try:
        if data_pkg['tgt_type'] == LOCAL_SERVER:
            process_local_server(directory, prefix, suffix, compression,data_pkg)

        elif data_pkg['tgt_type'] == AWS_S3:
            bucket_name = data_pkg['tgt_conn']['bucket_name']
            s3_conn, _ = connect_to_db(data_pkg['tgt_type'], data_pkg, 'target')
            local_path = data_pkg['paths_data']["folder_path"] + data_pkg['paths_data']['local_repo'] + data_pkg['paths_data']['programs'] + \
                    data_pkg['json_data']['project_name']+'/'  +data_pkg['paths_data']['pipelines']+data_pkg['paths_data']['tasks'] + data_pkg['paths_data']['source_files']
    
            new_filenames = process_local_server(local_path, prefix, suffix, compression,data_pkg)
            task_logger.info(new_filenames)
            local_file_path = str(local_path) +str(new_filenames)
            s3_folder=data_pkg['tgt_details']['file_path']
            s3_key = str(s3_folder) + str(new_filenames)
            s3_conn.upload_file(local_file_path, bucket_name, s3_key)
            task_logger.info("file uploaded to s3 bucket: %s",s3_key )
            os.remove(local_file_path)
            task_logger.info("File deleted from source location: %s", local_file_path)


        elif data_pkg['tgt_type'] == REMOTE_SERVER:
            local_path = data_pkg['paths_data']["folder_path"] + data_pkg['paths_data']['local_repo'] + data_pkg['paths_data']['programs'] + \
                    data_pkg['json_data']['project_name']+'/'  +data_pkg['paths_data']['pipelines']+data_pkg['paths_data']['tasks'] + data_pkg['paths_data']['source_files']
    
            new_filenames = process_local_server(local_path, prefix, suffix, compression, data_pkg)
            local_file_path = str(local_path) +str(new_filenames)
            remote_folder=data_pkg['tgt_details']['file_path']
            remote_filepath = str(remote_folder) + str(new_filenames)
            sftp_conn, _ = connect_to_db(data_pkg['tgt_type'], data_pkg, 'target')
            sftp_client = sftp_conn.open_sftp()
            sftp_client.put(local_file_path, os.path.join(remote_folder, new_filenames))
            task_logger.info("File uploaded to target location: %s", remote_filepath )
            os.remove(local_file_path)
            task_logger.info("File deleted from source location: %s", local_file_path)      
    except Exception as error:
        task_logger.error("Exception occurred in process_files: %s", error)
        raise error

def process_local_server(directory, prefix, suffix, compression,data_pkg):
    """function to process local files"""
    new_filenames = rename_or_concat_files(directory, prefix, suffix, data_pkg)
    task_logger.info("processed files as: %s", new_filenames)
    if compression:
        task_logger.info("Compressing the file as %s", compression)
        new_filenames =compress_file(directory,new_filenames, compression)
        task_logger.info("Compressed the file as %s ",new_filenames) 
        
    return new_filenames

def concat_files(directory, prefix, suffix,data_pkg):
    """Concatenate files"""
    dataframes = []
    name_pattern = f"{prefix}_(\d+){suffix}"
    pattern = re.compile(name_pattern)
    extension = suffix[1:]
    # List all files in the directory
    files = os.listdir(directory)   
    # Filter files based on the pattern
    matching_files = [filename for filename in files if pattern.match(filename)]    
    # Sort the list of matching files based on numerical order of filenames
    matching_files.sort(key=lambda x: int(re.search(name_pattern, x).group(1)))
    for filename in matching_files:
        file_path = os.path.join(directory, filename)
        try:
            if filename.endswith('.json'):
                json_data = []
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        try:
                            json_obj = json.loads(line)
                            json_data.append(json_obj)
                        except json.JSONDecodeError as error:
                            task_logger.error("Error decoding JSON in file: %s", error)
                df = pd.DataFrame(json_data)
            else:
                df,_ = read_file(file_path,extension,data_pkg)
            task_logger.info("File read successfully.")
            dataframes.append(df)
            task_logger.info("Appended DataFrame to dataframes")
        except Exception :
            task_logger.error("Error reading file :%s",filename)
        
    concatenated_df = pd.concat(dataframes, axis=0, ignore_index=True)
    concatenated_filename = f"{prefix}{suffix}"
    # Save the concatenated DataFrame based on the output format
    if filename.endswith('.xlsx'):
        concatenated_df.to_excel(os.path.join(directory, concatenated_filename), index=False)
    elif filename.endswith('.json'):
        concatenated_df.to_json(os.path.join(directory, concatenated_filename), orient='records')
    elif filename.endswith('.parquet'):
        concatenated_df.to_parquet(os.path.join(directory, concatenated_filename), index=False)
    else:
        concatenated_df.to_csv(os.path.join(directory, concatenated_filename), index=False)
    for filename in matching_files:
        os.remove(os.path.join(directory, filename))
    
    return concatenated_filename



#############################################################################################
def replace_date_placeholders(file_name):
    """function to replace the date and time placeholders in target filenames"""
    date_pattern = r"%[DdMmYyHhIiSs]+%"
    date_time_placeholders = re.findall(date_pattern,file_name)
    # Get current date and time components
    current_datetime = datetime.datetime.now()
    year = current_datetime.strftime("%Y")
    month = current_datetime.strftime("%m")
    day = current_datetime.strftime("%d")
    hour = current_datetime.strftime("%H")
    minute = current_datetime.strftime("%M")
    second = current_datetime.strftime("%S")

    for placeholder in date_time_placeholders:
        if "YYYY" in placeholder:
            file_name = file_name.replace(placeholder, year)
        elif "MM" in placeholder:
            file_name = file_name.replace(placeholder, month)
        elif "DD" in placeholder:
            file_name = file_name.replace(placeholder, day)
        elif "HH" in placeholder:
            file_name = file_name.replace(placeholder, hour)
        elif "MI" in placeholder:
            file_name = file_name.replace(placeholder, minute)
        elif "SS" in placeholder:
            file_name = file_name.replace(placeholder, second)

    return file_name

############################################################################################
def sink_params(tgt_ing_type,tgt_details,tgt_conn,tgt_type):
    """ function to get sink parameter """
    # Initialize variables for AWS S3 sink
    bucket_name = None
    s3_endpoint = None
    s3_credentials_provider = None
    if tgt_type == "AWS S3":
        bucket_name = "s3a://" + tgt_conn['bucket_name']
        s3_endpoint = f"s3.{tgt_conn['region_name']}.amazonaws.com"
        s3_credentials_provider= "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
    if tgt_ing_type == 'Files':
        object_sufix_name = tgt_details.get('object_sufix_name')
        if object_sufix_name:
            tgt_details['object_sufix_name'] = replace_date_placeholders(object_sufix_name)
        filename_time_format = tgt_details['object_sufix_name']
        object_prefix_name = tgt_details.get('object_prefix_name', '')
        if object_prefix_name == "" or object_prefix_name is None:
            file_name_expression = tgt_details['object_name']
        else:
            file_name_expression = object_prefix_name + tgt_details['object_name']
        if tgt_details['target_file_format'] in ( 'csv' ,'text' ):
            delimiter = tgt_details['delimiter']
        else:
            delimiter =None
    return filename_time_format , delimiter ,file_name_expression,\
            bucket_name,s3_endpoint,s3_credentials_provider


def load_typcasting_data(typcasting_path):
    """getting the typecasting json path"""
    with open(typcasting_path, 'r', encoding='utf-8') as jsonfile:
        return json.load(jsonfile)

def cast_column(col_name, data_type, data_types_to_cast, src_type):
    """getting the casted columns"""
    if data_type.lower() in data_types_to_cast:
        if src_type in ('MySQL', 'MSSQL'):
            return f'CAST({col_name} AS VARCHAR(255)) AS {col_name}'
        elif src_type in ('PostgreSQL', 'Oracle'):
            return f'CAST("{col_name}" AS VARCHAR(255)) AS "{col_name}"'
    else:
        if src_type in ('MySQL', 'MSSQL'):
            return col_name
        elif src_type in ('PostgreSQL', 'Oracle'):
            return f'"{col_name}"'
        
def transform_data_type(data_type):
    """function to transform oracle datatype"""
    if data_type.startswith("INTERVAL DAY"):
        return "interval day(k) to second(r)"
    elif re.search(r"TIMESTAMP\((\d+)\) WITH TIME ZONE", data_type):
        return "timestamp(k) with time zone"
    elif re.search(r"TIMESTAMP\((\d+)\) WITH LOCAL TIME ZONE", data_type):
        return "timestamp with local time zone"
    else:
        return data_type

def get_load_type_clause(src_details, tgt_details, data_pkg, src_type):
    """function to get the clause and column names"""
    try:
        paths_data = data_pkg['paths_data']
        typcasting_path = paths_data["folder_path"] + paths_data["seatunnel_typecasting_file_path"]
        json_data = load_typcasting_data(typcasting_path)
        if src_type in json_data:
            data_types_to_cast = json_data[src_type]

        columns_info, _ = get_columns_info_details(data_pkg)
        column_list = []
        for col_name, data_type in columns_info:
            if src_type in ('Oracle'):
                data_type = transform_data_type(data_type)
            column_list.append(cast_column(col_name, data_type, data_types_to_cast, src_type))

        if src_details['extraction_type'] == 'Filter':
            clause = f"where {src_details['extraction_criteria']}"
        else:
            clause = ""

        if tgt_details['audit_fields'].lower() == 'yes':
            crtd_by = data_pkg['json_data']['created_by']
            crtd_dttm = data_pkg['json_data']['updated_dttm']
            updt_by = data_pkg['json_data']['updated_by']
            updt_dttm = datetime.datetime.now().strftime(CURRENT_TIMESTAMP)

            audit_fields = f", '{crtd_by}' as crtd_by, '{crtd_dttm}' as crtd_dttm, \
                '{updt_by}' as updt_by, '{updt_dttm}' as updt_dttm"

            if src_type in ('MySQL', 'MSSQL', 'Oracle', 'PostgreSQL'):
                col_nm =  ", ".join(column_list) + audit_fields
        else:
            if src_type in ('MySQL', 'MSSQL', 'Oracle', 'PostgreSQL'):
                col_nm =  ", ".join(column_list)

        return clause, col_nm
    except FileNotFoundError:
        task_logger.error("File not found: %s", typcasting_path)
    except json.JSONDecodeError:
        task_logger.error("Error decoding JSON from file: %s", typcasting_path)
    except Exception as e:
        task_logger.error("Exception occurred in get_load_type_clause function: %s", e)
        raise e

def get_insert_query(tgt_details,data_pkg,tgt_type):
    """ funstion to get the insert quert """

    if tgt_details['audit_fields'] == 'YES' and data_pkg['json_data']['source'] == 'Files':
        col_nm, value = get_tgt_col_nm(data_pkg)
        audit_col_nm = "crtd_by, crtd_dttm, updt_by, updt_dttm"
        if tgt_type == "MySQL":
            tbl_nm = f"{tgt_details['database_name']}.{tgt_details['object_name']}"
        elif tgt_type in ('PostgreSQL'):
            tbl_nm = f"{tgt_details['database_name'].lower()}.{tgt_details['schema_name'].lower()}.{tgt_details['object_name'].lower()}"
        elif tgt_type in ('MSSQL'):
            tbl_nm = f"{tgt_details['database_name']}.{tgt_details['schema_name']}.{tgt_details['object_name']}"
        elif tgt_type in ('Oracle'):
            tbl_nm = f"{tgt_details['schema_name'].upper()}.{tgt_details['object_name'].upper()}"
            audit_col_nm = "CRTD_BY, CRTD_DTTM, UPDT_BY, UPDT_DTTM"
        crtd_by = data_pkg['json_data']['created_by']
        crtd_dttm = data_pkg['json_data']['updated_dttm']
        updt_by = data_pkg['json_data']['updated_by']
        updt_dttm = datetime.datetime.now().strftime(CURRENT_TIMESTAMP)
        x = f"insert into {tbl_nm}({col_nm},{audit_col_nm}) values({value},'{crtd_by}','{crtd_dttm}','{updt_by}','{updt_dttm}')"
        return x
    else:
        return " "

############################################################################################
def get_seatunnel_source(data_pkg,decrypt):
    """Getting the source plugins for seatunnel."""
    try:
        if data_pkg['json_data']['source'] == 'DB':
            fields = ""
            clause, col_nm = get_load_type_clause(data_pkg['src_details'],
                                                  data_pkg['tgt_details'],data_pkg,data_pkg['src_type'])
            source: JDBCInPlugin =  JDBCInPlugin(host=data_pkg['src_conn']['hostname'],
            user = data_pkg['src_conn']['username'],
            password=decrypt(data_pkg['src_conn']['password'],data_pkg['paths_data']),database = data_pkg['src_details']['database_name'],
            table = data_pkg['src_details']['object_name'],type = data_pkg['src_type'],port=data_pkg['src_conn']['port'],
            schema = data_pkg['src_details']['schema_name'], clause = clause, col_nm = col_nm)
        elif data_pkg['json_data']['source'] == 'Files':
            file_type = data_pkg['src_type']    
            if data_pkg['src_details']['object_type'] in ['gz','bz2']:
                local_path = data_pkg['paths_data']["folder_path"] + data_pkg['paths_data']['local_repo'] + data_pkg['paths_data']['programs'] + \
                    data_pkg['json_data']['project_name']+'/'  +data_pkg['paths_data']['pipelines']+data_pkg['paths_data']['tasks'] + data_pkg['paths_data']['source_files']
                source,fields, _ = load_zip_files(data_pkg, local_path)
                 
            elif file_type == REMOTE_SERVER and data_pkg['src_details']['object_type'] == 'parquet':
            
                local_path = data_pkg['paths_data']["folder_path"] + data_pkg['paths_data']['local_repo'] + data_pkg['paths_data']['programs'] + \
                    data_pkg['json_data']['project_name']+'/'  +data_pkg['paths_data']['pipelines']+data_pkg['paths_data']['tasks'] + data_pkg['paths_data']['source_files']
                source,fields = load_parquet_file(data_pkg, local_path)
            else :
                if  data_pkg['src_details']['object_type'] in ['xls', 'xlsx']:
                    f_type = 'excel'
                else:
                    f_type = data_pkg['src_details']['object_type']
                try:
                    skip_head = data_pkg['src_details']['skip_header']
                    delimiter = data_pkg['src_details']['delimiter']
                except Exception:
                    task_logger.error("Please mention the skip_header and delimiter.")
                batchsize = data_pkg['json_data']['chunk_size']
                #Collecting Local Server Parameter info for files as a source
                if file_type == LOCAL_SERVER:
                    fields,_ = seatunnel_params('DB',data_pkg)
                    schema3 = {"fields":fields}   
                    src_file_path = data_pkg['src_details']['file_path'] + data_pkg['src_details']['object_name']
                    source: FILEINPlugin =  FILEINPlugin(file_path = src_file_path, 
                            file_type =  f_type, skip_header = skip_head,
                            schema = schema3, delimiter = delimiter)
                
                #Collecting AWS S3 Parameter info for files as a source
                elif file_type == AWS_S3:
                    fields, _ = seatunnel_params(AWS_S3,data_pkg)
                    schema3 = {"fields":fields}   
                    src_file_path = f"/{data_pkg['src_details']['file_path']}"
                    bucket_name = f"s3a://{data_pkg['src_conn']['bucket_name']}"
                    s3_endpoint = f"s3.{data_pkg['src_conn']['region_name']}.amazonaws.com"
                    s3_credentials_provider = "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
                    access_key = decrypt(data_pkg['src_conn']['access_key'],data_pkg['paths_data'])
                    secret_key = decrypt(data_pkg['src_conn']['secret_access_key'],data_pkg['paths_data'])
                    
                    source: S3FileINPlugin = S3FileINPlugin(file_path = src_file_path, bucket_name = bucket_name,
                                    file_type = f_type , skip_header = skip_head,
                                    s3_endpoint = s3_endpoint, s3_credentials_provider = s3_credentials_provider,
                                    access_key = access_key, secret_key = secret_key, batchsize = batchsize,
                                    schema = schema3
                                    # , delimiter = delimiter
                                    )
                elif file_type == REMOTE_SERVER:

                    task_logger.info("Entered the Remote server condition.")
                    fields, _ = seatunnel_params(REMOTE_SERVER,data_pkg)
                    host = data_pkg['src_conn']['hostname']
                    port = data_pkg['src_conn']['port']
                    user_name = data_pkg['src_conn']['username']
                    password = decrypt(data_pkg['src_conn']['password'],data_pkg['paths_data'])
                    schema3 = {"fields":fields}  
                    src_file_path = f"{data_pkg['src_details']['file_path']}{data_pkg['src_details']['object_name']}"

                    source: SFTPFILEINPlugin = SFTPFILEINPlugin( host = host, port = port, 
                                    user_name = user_name, password = password, file_path = src_file_path,
                                    file_type = f_type , batchsize = batchsize, schema = schema3,
                                    skip_header = skip_head                            
                                    )
        return source, fields         
    except Exception:
        task_logger.error("Error occured in get_seatunnel_source")
############################################################################################
def get_seatunnel_target(data_pkg,decrypt,fields):
    """Getting the sink/target plugins for seatunnel."""
    try:
        
        if data_pkg['json_data']['target'] == 'DB':
            type_change= fields
            task_logger.info("Executing Operations_performed to determine execution status")
            execute = operations_performed(data_pkg['tgt_details']['action_on_table'], data_pkg, type_change)
            primary_key = data_pkg['tgt_details']['primary_key']
            insert_query = get_insert_query(data_pkg['tgt_details'],data_pkg,data_pkg['tgt_type'])

            sink: JDBCOutPugin = JDBCOutPugin(host=data_pkg['tgt_conn']['hostname'],
            user = data_pkg['tgt_conn']['username'] ,password = decrypt(data_pkg['tgt_conn']['password'],
            data_pkg['paths_data']),database = data_pkg['tgt_details']['database_name'],
            table = data_pkg['tgt_details']['object_name'],type = data_pkg['tgt_type'], port = data_pkg['tgt_conn']['port'],
            schema = data_pkg['tgt_details']['schema_name'],prim = primary_key, source = data_pkg['json_data']['source'],
            action = data_pkg['tgt_details']['action_on_table'], audit = data_pkg['tgt_details']['audit_fields'],
            insert_query = insert_query )

            task_logger.info("Constructing filename for SeaTunnel execution")
            nm = f"ora_{data_pkg['tgt_details']['object_name']}.json"
            task_logger.info("printitn JDBCOutPlugin for target connection %s", nm)
            if execute is True:
                task_logger.info("Executing SeaTunnel with source and sink connections")
                return sink, nm
                
            else :
                task_logger.error("Skipping SeaTunnel execution due to\
                Operations_performed result")
                y = 1
                return sink, nm
        elif data_pkg['json_data']['target'] == 'Files':
            filename_time_format,delimiter,file_name_expression,_,\
            _,_ = sink_params("Files",data_pkg['tgt_details'],
            data_pkg['tgt_conn'],data_pkg['tgt_type'])

            local_path = data_pkg['paths_data']["folder_path"] + data_pkg['paths_data']['local_repo'] + data_pkg['paths_data']['programs'] + \
                    data_pkg['json_data']['project_name']+'/'  +data_pkg['paths_data']['pipelines']+data_pkg['paths_data']['tasks'] + data_pkg['paths_data']['source_files']
            if data_pkg['tgt_type'] == LOCAL_SERVER:
                task_logger.info("Initializing FileOutPlugin for file sink")

                sink: FILEOUTPlugin = FILEOUTPlugin(file_path=data_pkg['tgt_details']['file_path'],
                file_type=data_pkg['tgt_details']['target_file_format'],
                delimiter=delimiter,file_name_expression= file_name_expression,type = data_pkg['tgt_type'],
                batchsize=data_pkg['json_data']["chunk_size"],filename_time_format= filename_time_format )

            elif data_pkg['tgt_type'] in ("AWS S3", "Remote Server"):
                task_logger.info("Initializing s3FileOutPlugin for s3file sink")

                sink: FILEOUTPlugin = FILEOUTPlugin(file_path=local_path,
                file_type=data_pkg['tgt_details']['target_file_format'],
                delimiter=delimiter,file_name_expression= file_name_expression,type = data_pkg['tgt_type'],
                batchsize=data_pkg['json_data']["chunk_size"],filename_time_format= filename_time_format )

            #     sink: S3FileOUTPlugin = S3FileOUTPlugin(file_path=data_pkg['tgt_details']['file_path'],
            #     file_type=data_pkg['tgt_details']['target_file_format'],
            #     delimiter=delimiter,file_name_expression= file_name_expression,type = data_pkg['tgt_type'],
            #     batchsize=data_pkg['json_data']["chunk_size"],filename_time_format= filename_time_format,
            #     bucket_name= bucket_name,access_key=decrypt(data_pkg['tgt_conn']['access_key'],data_pkg['paths_data']),
            #     secret_key=decrypt(data_pkg['tgt_conn']['secret_access_key'],data_pkg['paths_data']),s3_endpoint=
            #     s3_endpoint,s3_credentials_provider=s3_credentials_provider)
            # elif data_pkg['tgt_type'] == "Remote Server":
            #     task_logger.info("Initializing SftpFileOutPlugin for sftpfile sink")
                
            #     sink: SFTPFileOUTPlugin = SFTPFileOUTPlugin(file_path=data_pkg['tgt_details']['file_path'],
            #     file_type = data_pkg['tgt_details']['target_file_format'],
            #     delimiter=delimiter,file_name_expression= file_name_expression,type = data_pkg['tgt_type'],
            #     batchsize=data_pkg['json_data']["chunk_size"],filename_time_format= filename_time_format,
            #     host=data_pkg['tgt_conn']['hostname'] ,port= data_pkg['tgt_conn']['port'],user=data_pkg['tgt_conn']['username'],
            #     password=decrypt(data_pkg['tgt_conn']['password'],data_pkg['paths_data']))
           
            task_logger.info("Constructing filename for SeaTunnel execution")
            nm = f"ora_{data_pkg['tgt_details']['object_name']}.json"
            
            return sink, nm
    except Exception:
        task_logger.error("Error Occurred in get_seatunnel_target function.")

############################################################################################

def seatunnel_read_write(file_path,cluster_name,value):
    """reading the cluster management json"""
    with open(file_path, 'r') as file:
        # Load the JSON data
        data1 = json.load(file)
    
    data1[cluster_name] = value
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data1, json_file, indent=4)
        task_logger.info("writing to seatunnel json for cluster as  %s , %s",cluster_name,value)
        # exit(0)

def start_seatunnel_cluster(paths_data,json_data):
    """function to start the cluster """
    if json_data["target"] == "Files": 
        new_directory = paths_data['seatunnel_path_v2']+"bin"
    else:
        new_directory = paths_data['seatunnel_path_v1']+"bin"
    file_path = paths_data['folder_path'] + paths_data['seatunnel_folder_path'] + 'Seatunnel_cluster_manager.json'

    with open(file_path, 'r', encoding='utf-8') as file:
        # Load the JSON data
        data = json.load(file)
    
    cluster_name = "None"
    for cluster, status in data.items():
        if status == "Inactive":
            cluster_name = cluster
            break
    
    if cluster_name == "None":
        task_logger.info("No cluster available currently.")
        exit(0)
        return 0 
    
    task_logger.info("cluster name,%s",cluster_name)
    
    
    command = "nohup ./seatunnel-cluster.sh -cn "+ cluster_name + " &"
    task_logger.info("cluster start command,%s",command)
    os.chdir(new_directory)
    # Execute the command in a subprocess
    process = subprocess.Popen(command, shell=True)

    seatunnel_read_write(file_path,cluster_name,'Active')

    return cluster_name

def close_seatunnel_cluster(cluster_name,paths_data,json_data):
    """function to stop the cluster """
    if json_data["target"] == "Files": 
        new_directory = paths_data['seatunnel_path_v2']+"bin"
    else:
        new_directory = paths_data['seatunnel_path_v1']+"bin"
    os.chdir(new_directory)
    command = "./stop-seatunnel-cluster.sh -cn "+ cluster_name
    task_logger.info("running the stop cluster command")
    subprocess.run(command, shell=True)
############################################################################################

def seatunnel_main(json_data,paths_data,src_conn,tgt_conn,src_details,tgt_details,decrypt,
    engine,task_name,run_id,iter_value,group_number,subtask_no,src_type,tgt_type, cluster_name):
    """Function to get the seatunnel source and sink connections."""
    try:
        y = 1
        task_logger.info("Executing seatunnel_main for task_name: %s,group_number: %s,\
        subtask_no: %s",task_name, group_number, subtask_no)
        seatunnel_task_logger.info("Seatunnel logging started for : %s, group_number: %s,\
        subtask_no: %s",  task_name, group_number, subtask_no)
        task_logger.info("Initializing SeaTunnel with target object name: %s",
        tgt_details['object_name'])
        if json_data["target"] == "Files": 
            task_logger.info("excecuting with seatunnel 2.3.4")
            seatunnel: SeaTunnel = SeaTunnel(
                name=tgt_details['object_name'],
                seatunnel_path = paths_data["seatunnel_path_v2"]+'bin/seatunnel.sh'  ,
                parallelism = 2,
                mode = 'BATCH',
                config_dir= paths_data["folder_path"]+ paths_data["seatunnel_folder_path"]+"/"
            )
        else:
            task_logger.info("excecuting with seatunnel 2.3.3")
            seatunnel: SeaTunnel = SeaTunnel(
                name=tgt_details['object_name'],
                seatunnel_path = paths_data["seatunnel_path_v1"]+'bin/seatunnel.sh'  ,
                parallelism = 2,
                mode = 'BATCH',
                config_dir= paths_data["folder_path"]+ paths_data["seatunnel_folder_path"]+"/"
            )

        task_logger.info("Preparing data package for execution")
        
        data_pkg = {
            'json_data' : json_data,
            'paths_data' : paths_data,
            'src_conn' : src_conn,
            'tgt_conn' : tgt_conn,
            'src_type' : src_type,
            'tgt_type' : tgt_type,
            'tgt_details' : tgt_details,
            'src_details' : src_details,
            'decrypt' : decrypt
            
            }
        task_logger.info("Initializing Plugin for source connection")
        
        source, fields = get_seatunnel_source(data_pkg,decrypt)
        sink, nm = get_seatunnel_target(data_pkg,decrypt,fields)

        y, total_read_count, total_write_count = seatunnel.exec(source, sink, nm,cluster_name, True)

        if y == 1:
            seatunnel_task_logger.info("SeaTunnel Execution Status is : 'FAILED'")
            task_logger.error("SeaTunnel execution failed. Updating audit with 'FAILED' status.")
            engine.audit(json_data,task_name,run_id,paths_data,'STATUS','FAILED',iter_value,
                        group_number,subtask_no)
            # cluster_close()
            seatunnel_task_logger.info("##########################################")
        elif y == 0 :
            seatunnel_task_logger.info("SeaTunnel Execution Status is : 'COMPLETED'")
            task_logger.info("SeaTunnel execution completed successfully. Updating audit with"
                            "'COMPLETED' status.")
            if json_data["target"] == "Files":
                task_logger.info("file generated with seatunnel job")
                process_files(data_pkg)
            if src_type == AWS_S3:
                    task_logger.info("count getting from aws s3")
            engine.audit(json_data,task_name,run_id,paths_data,'SRC_RECORD_COUNT',
            total_read_count,iter_value,group_number,subtask_no)
            engine.audit(json_data,task_name,run_id,paths_data,'TRGT_RECORD_COUNT',
            total_write_count,iter_value,group_number,subtask_no)
            engine.audit(json_data,task_name,run_id,paths_data,'STATUS','COMPLETED',
            iter_value,group_number,subtask_no)
            # cluster_close()
            seatunnel_task_logger.info("###########################################")
        else:
            seatunnel_task_logger.info("SeaTunnel Execution Status is : 'FAILED'")
            task_logger.error("SeaTunnel execution failed. Updating audit with 'FAILED' status.")
            engine.audit(json_data,task_name,run_id,paths_data,'STATUS','FAILED',iter_value,
                        group_number,subtask_no)
            # cluster_close()
            seatunnel_task_logger.info("###########################################")
    except Exception as e:
        task_logger.error("Error Occurred in Seatunnel main %s",e)
        raise e

##################################################################################################

def seatunnel_bulk_execution(hierarchy,json_data,decrypt,config_file_path,paths_data,task_name,
                             run_id,iter_value):
    """Function used to trigger the seatunnel jobs in parrallel if required."""
    task_logger.info("Starting seatunnel_bulk_execution for hierarchy: %s", hierarchy)
    engn_path = os.path.expanduser(paths_data["folder_path"]) + paths_data['src'] + \
        paths_data['scripts'] + paths_data['engine_main']
    sys.path.insert(0, engn_path)
    engine = importlib.import_module("engine_code")
    failed_groups = []
    seatunnel_json_file_path = paths_data['folder_path'] + paths_data['seatunnel_folder_path'] + 'Seatunnel_cluster_manager.json'

    if len(hierarchy) > 0:
        #Start Seatunnel Cluster
        cluster_name = start_seatunnel_cluster(paths_data,json_data)

        for data in hierarchy:
            group_number = list(data.keys())[0]
            # Extract the key from the dictionary
            task_logger.info("starting the bulk ingestion process for group: %s",group_number)
            engine.audit(json_data, task_name,run_id,paths_data,'STATUS','STARTED',iter_value,
                         group_number,None)
            group = data[group_number]
            task=[]
            processes = []
            for subtask in group:
                #execute for 1 subtask
                task_logger.info("Executing bulk ingestion process for subtask: %s", subtask)
                source,target=get_subtask_details(json_data["task"]["details"],subtask)
                src = source["connection_name"]
                tgt = target["connection_name"]
                src_conn,src_type = get_conn_subtype_type(config_file_path + src + '.json')
                tgt_conn,tgt_type = get_conn_subtype_type(config_file_path + tgt + '.json')
                task_logger.info("starting the bulk ingestion process for subtask: %s",subtask)
                task_logger.info("source:%s",source)
                task_logger.info("target:%s",target)

                bulk_task = mp.Process(target = seatunnel_main, args =
                            [json_data,paths_data,src_conn,tgt_conn,source,target,decrypt,engine,\
                             task_name,run_id,iter_value,group_number,subtask,src_type,tgt_type, cluster_name],\
                                name = 'Process_' + str(subtask))
                processes.append(bulk_task)
                bulk_task.start()
            for threads in processes:
                threads.join()
            for subtask in group:
                status = engine.subtask_audit_status(json_data["task_name"], subtask,paths_data)
                task_logger.info("subtasks status:%s", status)
                if status and len(status) > 0:
                    # Check if the result is not empty and has at least one element
                    first_dict = status[0]
                    audit_value_task = first_dict['audit_value']
                    if audit_value_task == 'COMPLETED':
                        # print(subtask)
                        task.append({subtask:'COMPLETED'})
                    elif audit_value_task != 'COMPLETED':
                        task.append({subtask:'FAILED'})
            while True:
                keys = [list(d.keys())[0] for d in task]
                if set(group).issubset(set(keys)) is True:
                    break
                time.sleep(3)
            if any('FAILED' in k.values() for k in task):
                failed_groups.append(group_number)
                task_logger.warning("execution for task_group:%s FAILED",group_number)
                engine.audit(json_data, task_name,run_id,paths_data,'STATUS','FAILED',iter_value,
                             group_number,None)
                process2 = close_seatunnel_cluster(cluster_name,paths_data,json_data)

                seatunnel_read_write(seatunnel_json_file_path,cluster_name,'Inactive')
                return failed_groups
            engine.audit(json_data, task_name,run_id,paths_data,'STATUS','COMPLETED',iter_value,
                            group_number,None)
            task_logger.info("execution for task_group:%s COMPLETED", group_number)
        process2 = close_seatunnel_cluster(cluster_name,paths_data,json_data)
        seatunnel_read_write(seatunnel_json_file_path,cluster_name,'Inactive')
        return failed_groups
    return failed_groups

#################################################################################################

def seatunnel_execute(json_data, config_file_path,paths_data,hierarchy,task_id,run_id,
    iter_value):
    """execution of the seatunnel code."""

    task_logger.info("Executing seatunnel_execute for task_id: %s, run_id: %s", task_id, run_id)
    utility_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
    paths_data["ingestion_path"]
    sys.path.insert(0, utility_path)
    module = importlib.import_module("utility")
    decrypt = getattr(module, "decrypt")
    homepath = os.path.expanduser(paths_data["folder_path"])
    task_logger.info("Expanded user homepath: %s", homepath)
    failed = seatunnel_bulk_execution(hierarchy,json_data,decrypt,config_file_path,paths_data,
                                      task_id,run_id,iter_value)
    task_logger.info("seatunnel_bulk_execution completed. Failed groups: %s", failed)
    return failed