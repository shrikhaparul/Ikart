""" script for writing data to S3"""
import logging
from datetime import datetime
import os
import importlib
import sys
import io
import pandas as pd
import boto3

module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")

task_logger = logging.getLogger('task_logger')
folder_timestamp = datetime.now().strftime("%Y%m%d")
file_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
CSV = '.csv'
XLSX = '.xlsx'
JSON = '.json'
PARQUET ='.parquet'
XML = '.xml'
REPLACE_OPERATION= "S3 target operation is REPLACE \n target path: %s"
APPEND_OPERATION="S3 target operation is APPEND"
OBJECT_EXISTS ="%s object already exists in the target location"
OBJECT_NOT_EXISTS = "%s object does not exists in the target location"
CREATE_OBJECT = "creating new object %s"

def establish_conn(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        # task_logger.info("aws access key id %s", decrypt(connection_details["aws_access_key_id"]))
        d_aws_access_key_id = decrypt(connection_details["access_key"])
        d_aws_secret_access_key = decrypt(connection_details["secret_access_key"])
        conn = boto3.client( service_name= 's3',region_name=
        connection_details["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        logging.info("connection established")
        return conn,connection_details
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        raise error

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

def check_path(con,file_path,connection_details):
    "function to check whether table object in s3 exists or not"
    result = con.list_objects(Bucket=connection_details["bucket_name"], Prefix=file_path )
    exists=False
    if 'Contents' in result:
        exists=True
    return exists

def write_csv(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for csv filetype"""
    task_logger.info("s3 write operation for CSV filetype started")
    target=json_data["task"]["target"]
    csv_buf = io.StringIO()
    datafram.to_csv(csv_buf, header=True, index=False)
    csv_buf.seek(0)
    if target["operation"] == "replace":
        #if operation is replace
        task_logger.info(REPLACE_OPERATION,target_path+CSV)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        csv_buf.getvalue(), Key=target_path+CSV,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+CSV,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+CSV)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+CSV)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            csv_buf.getvalue(), Key=target_path+'_'+file_timestamp+CSV,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+CSV)
            task_logger.info(CREATE_OBJECT,target_path+CSV)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            csv_buf.getvalue(), Key=target_path+CSV,ServerSideEncryption='AES256')

def write_excel(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for csv filetype"""
    task_logger.info("s3 write operation for EXCEL filetype started")
    target=json_data["task"]["target"]
    with io.BytesIO() as output:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer: # pylint: disable=abstract-class-instantiated
            datafram.to_excel(writer,header=True, index=False)
        data = output.getvalue()
    if target["operation"] == "replace":
        task_logger.info(REPLACE_OPERATION,target_path+XLSX)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        data, Key=target_path+XLSX,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+XLSX,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+XLSX)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+XLSX)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            data, Key=target_path+'_'+file_timestamp+XLSX,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+XLSX)
            task_logger.info(CREATE_OBJECT,target_path+XLSX)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            data, Key=target_path+XLSX,ServerSideEncryption='AES256')

def write_json(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for JSON filetype"""
    task_logger.info("s3 write operation for JSON filetype started")
    target=json_data["task"]["target"]
    json_buffer = io.StringIO()
    datafram.to_json(json_buffer,orient='records', index=True)
    if target["operation"] == "replace":
        #if operation is replace
        task_logger.info(REPLACE_OPERATION,target_path+JSON)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        json_buffer.getvalue(), Key=target_path+JSON,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+JSON,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+JSON)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+JSON)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            json_buffer.getvalue(), Key=target_path+'_'+file_timestamp+JSON,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+JSON)
            task_logger.info(CREATE_OBJECT,target_path+JSON)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            json_buffer.getvalue(), Key=target_path+JSON,ServerSideEncryption='AES256')

def write_parquet(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for parquet filetype"""
    task_logger.info("s3 write operation for PARQUET filetype started")
    target=json_data["task"]["target"]
    parquet_buffer = io.BytesIO()
    datafram.astype(str).to_parquet(parquet_buffer,engine='auto', index=False)
    if target["operation"] == "replace":
        #if operation is replace
        task_logger.info(REPLACE_OPERATION,target_path+PARQUET)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        parquet_buffer.getvalue(), Key=target_path+PARQUET,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+PARQUET,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+PARQUET)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+PARQUET)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            parquet_buffer.getvalue(), Key=target_path+'_'+file_timestamp+PARQUET,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+PARQUET)
            task_logger.info(CREATE_OBJECT,target_path+PARQUET)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            parquet_buffer.getvalue(), Key=target_path+PARQUET,ServerSideEncryption='AES256')

def write_xml(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for XML filetype"""
    task_logger.info("s3 write operation for XML filetype started")
    target=json_data["task"]["target"]
    xml_buffer = io.BytesIO()
    datafram.to_xml(xml_buffer,index=True)
    if target["operation"] == "replace":
        #if operation is replace
        task_logger.info(REPLACE_OPERATION,target_path+XML)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        xml_buffer.getvalue(), Key=target_path+XML,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+XML,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+XML)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+XML)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            xml_buffer.getvalue(), Key=target_path+'_'+file_timestamp+XML,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+XML)
            task_logger.info(CREATE_OBJECT,target_path+XML)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            xml_buffer.getvalue(), Key=target_path+XML,ServerSideEncryption='AES256')

def write(json_data,datafram,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value):
    """ function for ingesting data to S3 bucket based on the inputs in task json"""
    engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
    sys.path.insert(0, engine_code_path)
    #importing audit function from orchestrate script
    module1 = importlib.import_module("engine_code")
    audit = getattr(module1, "audit")
    target=json_data["task"]["target"]
    try:
        task_logger.info("ingest data to S3 initiated")
        conn,connection_details = establish_conn(json_data,'target',config_file_path)
        status="Pass"
        target_path = target["file_path"]+folder_timestamp+'/'+\
        target["file_name"]
        if target["file_type"]=="csv":
            write_csv(json_data,datafram,conn,target_path,connection_details)
        elif target["file_type"]=="excel":
            write_excel(json_data,datafram,conn,target_path,connection_details)
        elif target["file_type"]=="json":
            write_json(json_data,datafram,conn,target_path,connection_details)
        elif target["file_type"]=="parquet":
            write_parquet(json_data,datafram,conn,target_path,connection_details)
        elif target["file_type"]=="xml":
            write_xml(json_data,datafram,conn,target_path,connection_details)
        return status
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
