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
            # log2.info("txt getting called")
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            log2.error("pipeline txt file does not exist")
    except Exception as error:
        log2.exception("write_to_txt: %s.", str(error))
        raise error

def read(json_data : dict,task_id,run_id,paths_data,file_path,iter_value):
    """ function for readinging data from xml  """
    try:
        log2.info("xml reading started")
        file_path1 = json_data["task"]["source"]["file_path"]+\
            json_data["task"]["source"]["file_name"]
        log2.info("list of files which were read")
        log2.info(file_path1)
        is_exists = os.path.exists(file_path1)
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        from engine_code import audit
        if is_exists is False:
            log2.error("'%s' SOURCE FILE not found in the location",
            json_data["task"]["source"]["file_name"])
            status1= 'FAILED'
            write_to_txt(task_id,status1,file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            log2.info("entered into else")
            datafram = pd.read_xml(json_data["task"]["source"]["file_path"]+\
            json_data["task"]["source"]["file_name"],xpath='./*',parser='lxml',\
            encoding = json_data["task"]["source"]["encoding"])
        yield datafram
        return True
    except Exception as error:
        log2.exception("reading_xml() is %s", str(error))
        raise error
