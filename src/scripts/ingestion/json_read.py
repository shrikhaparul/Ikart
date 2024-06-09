""" script for reading data from xml"""
import logging
import sys
import json
import glob
import importlib
import gzip
import zipfile
import tarfile
import os
import bz2
import pandas as pd

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
ITERATION='%s iteration'

def read(json_data : dict,task_id,run_id,paths_data,txt_file_path,iter_value,local_file_path):
    """ function for reading data from json  """
    try:
        task_logger.info("json  reading started")
        source = json_data["task"]["source"]
        
        if local_file_path == None:
            local_file_path = " "
            file_path = source["file_path"]
            file_name = source["file_name"]
            pattern = f'{file_path}{file_name}'
        else :
            pattern = local_file_path
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
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            for file in all_files:
                if file.endswith('.gz'):
                    with gzip.open(file, 'rb') as gz_file:
                        datafram = pd.read_json(gz_file,
                                    encoding=json_data["task"]["source"]["encoding"])
                elif file.endswith('.zip'):
                    with zipfile.ZipFile(file, 'r') as zipf:
                        with zipf.open(zipf.namelist()[0]) as json_file:
                            datafram = pd.read_json(json_file,
                                        encoding=json_data["task"]["source"]["encoding"])
                elif file.endswith('.tar'):
                    with tarfile.open(file, 'r') as tar:
                        with tar.extractfile(tar.getnames()[0]) as json_file:
                            datafram = pd.read_json(json_file,
                                        encoding=json_data["task"]["source"]["encoding"])
                elif file.endswith('.bz2'):
                    with bz2.BZ2File(file, 'rb') as bz2_file:
                        datafram = pd.read_json(bz2_file,
                                    encoding=json_data["task"]["source"]["encoding"])
                else:
                    datafram = pd.read_json(file, encoding=json_data["task"]["source"]["encoding"])

                # with open(file, 'r', encoding='utf-8') as file:
                #     data = json.load(file)
                # datafram = pd.json_normalize(data,max_level=0)
                datafram.columns = datafram.columns.astype(str)
                count1 = 1 + count1
                task_logger.info(ITERATION , str(count1))
                yield datafram
    except Exception as error:
        update_status_file(task_id,'FAILED',txt_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("reading json() is %s", str(error))
        raise error
    finally:
        if os.path.isfile(local_file_path) :
            os.remove(local_file_path)
            # Logging: Config file removal
            task_logger.info("Temporary file removed: %s ", local_file_path)
    
