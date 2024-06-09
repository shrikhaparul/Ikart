""" script for reading data from xml"""
import logging
import sys
import os
import glob
import importlib
import pandas as pd
import xmltodict


task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")

def find_list_in_dict(d):
    """returns a list or dict based on value"""
    for _, value in d.items():
        if isinstance(value, list):
            return value
        elif isinstance(value, dict):
            result = find_list_in_dict(value)
            if result is not None:
                return result
    return None

def read(json_data: dict, task_id, run_id, paths_data, txt_file_path, iter_value):
    """function to read xml file"""
    try:
        task_logger.info("XML reading started")
        source = json_data["task"]["source"]
        file_path = source["file_path"]
        file_name = source["file_name"]
        pattern = os.path.join(file_path, file_name)
        # Use glob.glob to get a list of matching file paths
        all_files = glob.glob(pattern)
        task_logger.info("All files: %s", all_files)
        task_logger.info("List of files which were read")
        # Importing audit from orchestrate
        engine_code_path = os.path.join(paths_data["folder_path"], paths_data['src'],
        paths_data["ingestion_path"])
        sys.path.insert(0, engine_code_path)
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        count1 = 0
        if not all_files:
            task_logger.error("'%s' SOURCE FILE not found in the location", source["file_name"])
            update_status_file(task_id, 'FAILED', txt_file_path)
            audit(json_data, task_id, run_id,paths_data, 'STATUS', 'FAILED', iter_value)
            sys.exit()
        else:
            for file in all_files:
                with open(file, "r", encoding="utf-8") as file:
                    data = file.read()
                # Parse XML data to a Python dictionary
                python_dict = xmltodict.parse(data)
                events_list = find_list_in_dict(python_dict)
                if events_list:
                    # Use json_normalize to flatten the nested structure
                    datafram = pd.json_normalize(events_list)
                    datafram.columns=[col.strip('@').replace('.', '_') for col in datafram.columns]
                    count1 += 1
                    task_logger.info("Iteration %s: %s", iter_value, count1)
                    yield datafram
    except Exception as error:
        update_status_file(task_id, 'FAILED', txt_file_path)
        audit(json_data, task_id, run_id,paths_data, 'STATUS', 'FAILED', iter_value)
        task_logger.exception("Reading XML failed: %s", str(error))
        raise error
    