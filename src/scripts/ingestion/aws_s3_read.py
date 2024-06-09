import logging
import importlib
import sys
import os
from utility import update_status_file

module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
module = importlib.import_module("connections")
establish_conn_for_s3 = getattr(module, "establish_conn_for_s3")

task_logger = logging.getLogger('task_logger')


def read(json_data: dict,config_file_path,task_id,run_id,paths_data,file_path,
         iter_value, skip_header= 0,skip_footer= 0,
         delimiter = ",", quotechar = '"', escapechar = None):
    '''function to read s3 data'''
    try:
        # Temporary folder path
        local_temp_path = paths_data["folder_path"] + paths_data['local_repo'] + \
        paths_data['programs'] + json_data['project_name']+'/'  +paths_data['pipelines']+ \
        paths_data['tasks'] + paths_data['source_files'] + '/temp_path/'
        if not os.path.exists(local_temp_path):
            os.mkdir(local_temp_path)
        # Importing the audit functio from engine code
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        decryption = getattr(audit_module, "decryption_check")
        # Getting source information
        source = json_data['task']['source']
        # Creating S3 connection
        conn,connection_details = establish_conn_for_s3(json_data,
        'source',config_file_path,paths_data)
        bucket_name = connection_details["bucket_name"]
        path = source['file_path']+source['file_name']
        # Download file temporary location.
        text_file_path = local_temp_path + source['file_name']
        # downlaod the compressed file from aws.
        conn.download_file(bucket_name, path, text_file_path)
        task_logger.info(f"File copied from S3 to {text_file_path}")
        # Performing decryption if required
        local_file_path = decryption(json_data,text_file_path,local_temp_path, paths_data)
        if local_file_path == None:
            local_file_path = text_file_path
        else:
            task_logger.info("aws s3 removing file")
            task_logger.info(text_file_path)
            if os.path.exists(text_file_path):
                os.remove(text_file_path)
                task_logger.info(text_file_path)
            local_file_path = local_file_path

        file_type = source["file_type"]
        if file_type == "csv":
            csv_read = importlib.import_module("csv_read")
            status = csv_read.read(json_data,task_id,run_id,paths_data,
                                            file_path,iter_value, local_file_path)
            return status
        elif file_type == "parquet":
            parquet_read = importlib.import_module("parquet_read")
            status = parquet_read.read(json_data,task_id,run_id,paths_data,
                                            file_path,iter_value, local_file_path)
            return status
        elif file_type == "json":
            json_read = importlib.import_module("json_read")
            status = json_read.read(json_data,task_id,run_id,paths_data,
                                            file_path,iter_value, local_file_path)
            return status
        elif file_type == "xml":
            xml_read = importlib.import_module("xml_read")
            status = xml_read.read(json_data,task_id,run_id,paths_data,
                                            file_path,iter_value, local_file_path)
            return status
        elif file_type == "xlsx":
            xlsx_read = importlib.import_module("xlsx_read")
            status = xlsx_read.read(json_data,task_id,run_id,paths_data,
                                            file_path,iter_value, local_file_path)
            return status
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.info("reading_s3() is %s", str(error))
        raise error