""" script for reading data from xml"""
import logging
import sys
import os
import glob
import importlib
import pandas as pd

task_logger = logging.getLogger('task_logger')

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
    """ function for readinging data from xml  """
    try:
        source = json_data["task"]["source"]
        task_logger.info("reading xml initiated...")
        file_path = source["file_path"]
        file_name = source["file_name"]
        # function for reading files present in a folder with different csv formats
        # Combine file_path and file_name
        pattern = f'{file_path}{file_name}'
        # Use glob.glob to get a list of matching file paths
        all_files = glob.glob(pattern)
        task_logger.info("all files %s", all_files)
        task_logger.info("list of files which were read")
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module = importlib.import_module("engine_code")
        audit = getattr(module, "audit")
        if not all_files:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            for file in all_files:
                task_logger.info("entered into else")
                datafram = pd.read_xml(file,xpath='./*',parser='lxml',\
                encoding = source["encoding"])
                datafram.reset_index(drop=True, inplace=True)
                yield datafram
        # return True
    except Exception as error:
        task_logger.exception("reading_xml() is %s", str(error))
        raise error
