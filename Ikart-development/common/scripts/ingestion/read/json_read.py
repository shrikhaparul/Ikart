""" script for reading data from xml"""
import logging
import sys
import os
import pandas as pd

log2 = logging.getLogger('log2')

def write_to_txt(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            log2.error("pipeline txt file does not exist")
    except Exception as error:
        log2.exception("write_to_txt: %s.", str(error))
        raise error

def read(json_data : dict,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from json  """
    try:
        log2.info("json  reading started")
        source_file_path = json_data["task"]["source"]["file_path"]+\
            json_data["task"]["source"]["file_name"]
        log2.info("list of files which were read")
        log2.info(source_file_path)
        is_exists = os.path.exists(source_file_path)
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        from engine_code import audit
        if is_exists is False:
            log2.error("'%s' SOURCE FILE not found in the location",
            json_data["task"]["source"]["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            log2.info("entered into else")
            datafram = pd.read_json(json_data["task"]["source"]["file_path"]+\
                json_data["task"]["source"]["file_name"],
                orient ='index',encoding = json_data["task"]["source"]["encoding"], nrows = None)
            datafram.columns = datafram.columns.astype(str)
        yield datafram
        return True
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        log2.exception("reading json() is %s", str(error))
        raise error
