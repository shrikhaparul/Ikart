""" script for ingesting data to json"""
import logging
import os
import sys
from datetime import datetime
import importlib
import pandas as pd
from utility import construct_file_name,update_status_file

task_logger = logging.getLogger('task_logger')

def write(json_data: dict,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path,subtask_target_section,group_no,subtask_no):
    """ function for writing to JSON """
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        target = subtask_target_section
        file_name = construct_file_name(target)
        file_path = local_temp_path
        created_by = json_data['created_by'] if 'created_by' in json_data else "etl_user"
        task_logger.info("writing data to JSON initiated")
        def_audit_columns = "inactive" if target["audit_fields"] in ("",None,"")\
        else target["audit_fields"]
        if counter == 1: # If it's the first chunk, write the data to a new JSON file
            if os.path.exists(target["file_path"]+file_name):
                os.remove(target["file_path"]+file_name)
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY']=created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_json(file_path + file_name, orient='records', lines=False)
            else:
                datafram.to_json(file_path + file_name, orient='records', lines=False)
        else: # If it's not the first chunk, read the existing JSON file and append the new data
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY']=created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                existing_dataframe = pd.read_json(file_path + file_name, orient='records')
                updated_dataframe = pd.concat([existing_dataframe, datafram], ignore_index=True)
                updated_dataframe.to_json(file_path + file_name, orient='records', lines=False)
            else:
                existing_dataframe = pd.read_json(file_path + file_name, orient='records')
                updated_dataframe = pd.concat([existing_dataframe, datafram], ignore_index=True)
                updated_dataframe.to_json(file_path + file_name, orient='records', lines=False)
        task_logger.info("JSON conversion completed")
        return True,file_path,file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data,task_id,run_id,paths_data,'STATUS','FAILED',iter_value,group_no,subtask_no)
        task_logger.exception("converting_to_json() is %s", str(error))
        raise error
