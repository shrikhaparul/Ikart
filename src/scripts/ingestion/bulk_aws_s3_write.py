""" script for writing data to S3"""
import logging
import importlib
import sys
from utility import update_status_file

task_logger = logging.getLogger('task_logger')
def write(json_data,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path,subtask_target_section,group_no,subtask_no):
    """ function for ingesting data to S3 bucket based on the inputs in task json"""
    engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
    sys.path.insert(0, engine_code_path)
    #importing audit function from orchestrate script
    engine_code = importlib.import_module("engine_code")
    audit = getattr(engine_code, "audit")
    target=subtask_target_section
    try:
        if target["target_file_format"] == "csv":
            csv_write = importlib.import_module("bulk_csv_write")
            status,file_path,file_name=csv_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path,
            subtask_target_section,group_no,subtask_no)
            return status, file_path, file_name
        if target["target_file_format"] == "parquet":
            parquet_write = importlib.import_module("bulk_parquet_write")
            status,file_path, file_name = parquet_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path,subtask_target_section,
            group_no,subtask_no)
            return status, file_path, file_name
        if target["target_file_format"] == "json":
            json_write = importlib.import_module("bulk_json_write")
            status,file_path, file_name = json_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path,
            subtask_target_section,group_no,subtask_no)
            return status, file_path, file_name
        if target["target_file_format"] == "xml":
            xml_write = importlib.import_module("bulk_xml_write")
            status,file_path, file_name = xml_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path,
            subtask_target_section,group_no,subtask_no)
            return status, file_path, file_name
        if target["target_file_format"] == "excel":
            xlsx_write = importlib.import_module("bulk_xlsx_write")
            status,file_path, file_name = xlsx_write.write(json_data,task_id,run_id,iter_value,
            paths_data,text_file_path,datafram, counter,local_temp_path,
            subtask_target_section,group_no,subtask_no)
            return status, file_path, file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data,task_id,run_id,paths_data,'STATUS','FAILED',iter_value,group_no,subtask_no)
        task_logger.exception("write() is %s", str(error))
        raise error
    