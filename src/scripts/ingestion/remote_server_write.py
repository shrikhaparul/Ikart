""" script for writing data to S3"""
import logging
import importlib
import sys
from utility import update_status_file

task_logger = logging.getLogger('task_logger')

def write(json_data,task_id,run_id,iter_value,paths_data,
    text_file_path,datafram, counter,local_temp_path):
    """ function for ingesting data to S3 bucket based on the inputs in task json"""
    engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
    sys.path.insert(0, engine_code_path)
    #importing audit function from orchestrate script
    engine_code = importlib.import_module("engine_code")
    audit = getattr(engine_code, "audit")
    target=json_data["task"]["target"]
    try:
        if target["file_type"] == "csv":
            csv_write = importlib.import_module("csv_write")
            status,file_path, file_name = csv_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path)
            return status, file_path, file_name
        if target["file_type"] == "parquet":
            parquet_write = importlib.import_module("parquet_write")
            status,file_path, file_name = parquet_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path)
            return status, file_path, file_name
        if target["file_type"] == "json":
            json_write = importlib.import_module("json_write")
            status,file_path, file_name = json_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path)
            return status, file_path, file_name
        if target["file_type"] == "xml":
            xml_write = importlib.import_module("xml_write")
            status,file_path, file_name = xml_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path)
            return status, file_path, file_name
        if target["file_type"] == "xlsx":
            xlsx_write = importlib.import_module("xlsx_write")
            status,file_path, file_name = xlsx_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path)
            return status, file_path, file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
    