""" script for reading data from excel"""
import glob
import logging
import importlib
import sys
import os
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

def read(json_data: dict,task_id,run_id,paths_data,file_path,iter_value,skip_header = 0,
skip_footer= 0, sheet_name= 0):
    """ function for reading data from excel"""
    try:
        source = json_data["task"]["source"]
        task_logger.info("reading excel initiated...")
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
        if all_files == []:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            default_skip_header = skip_header if json_data["task"]["source"]["skip_header"]==" "\
            else json_data["task"]["source"]["skip_header"]
            default_skip_footer = skip_footer if json_data["task"]["source"]["skip_footer"]==" "\
            else json_data["task"]["source"]["skip_footer"]
            # default_sheet_name = sheet_name if json_data["task"]["source"]["sheet_name"]==" "\
            # else json_data["task"]["source"]["sheet_name"]
            for file in all_files:
                data = pd.read_excel(io = file)
                # print(type(data))
                row_count = data.shape[0]-default_skip_header-default_skip_footer
                task_logger.info("the number of records in source file is:%s", row_count)
                count1 = 0
                # print(row_count)
                # datafram = pd.read_excel(io = file, sheet_name = default_sheet_name,
                # skiprows = default_skip_header,nrows = row_count)
                datafram = pd.read_excel(io = file, nrows = row_count)
                count1 = 1 + count1
                task_logger.info('%s iteration' , str(count1))
                yield datafram
    except Exception as error:
        task_logger.exception("reading_excel() is %s", str(error))
        raise error
