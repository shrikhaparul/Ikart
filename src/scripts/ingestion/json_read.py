""" script for reading data from xml"""
import logging
import sys
import os
import glob
import importlib
import pandas as pd

task_logger = logging.getLogger('task_logger')
ITERATION='%s iteration'

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

def read(json_data : dict,task_id,run_id,paths_data,file_path,iter_value):
    """ function for reading data from json  """
    try:
        task_logger.info("json  reading started")
        source = json_data["task"]["source"]
        file_path = source["file_path"]
        file_name = source["file_name"]
        pattern = f'{file_path}{file_name}'
        # Use glob.glob to get a list of matching file paths
        all_files = glob.glob(pattern)
        task_logger.info("all files %s", all_files)
        task_logger.info("list of files which were read")
        #importing audit from orchestrate
        engine_code_path = paths_data["folder_path"]+paths_data['src']+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        count1 = 0
        if not all_files:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            for file in all_files:
                datafram = pd.read_json(file,encoding = json_data["task"]["source"]["encoding"],
                                        nrows = None)
                datafram.columns = datafram.columns.astype(str)
                count1 = 1 + count1
                task_logger.info(ITERATION , str(count1))
                yield datafram
        # return True
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("reading json() is %s", str(error))
        raise error
