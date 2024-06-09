""" script for reading data from excel"""
import glob
import logging
import importlib
import sys
import os
import gzip
import zipfile
import tarfile
import bz2
import pandas as pd

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")

def read(json_data: dict,task_id,run_id,paths_data,txt_file_path,iter_value,skip_header = 0,
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
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        if not all_files:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            update_status_file(task_id,'FAILED',txt_file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            default_skip_header = skip_header if json_data["task"]["source"]["skip_header"] \
            in (" ",None,"None","") else json_data["task"]["source"]["skip_header"]
            default_skip_footer = skip_footer if json_data["task"]["source"]["skip_footer"] \
            in (" ",None,"None","") else json_data["task"]["source"]["skip_footer"]
            if source["header"] == "Y":
                use_header = True
            else:
                use_header = False
            use_header=0 if use_header else None
            for file in all_files:
                # Determine the compression format based on file extension
                file_extension = os.path.splitext(file)[1].lower()

                if file_extension == '.gz':
                    with gzip.open(file, 'rb') as gz_file:
                        excel_data = pd.read_excel(gz_file, sheet_name=sheet_name)
                elif file_extension == '.zip':
                    with zipfile.ZipFile(file, 'r') as zipf:
                        with zipf.open(zipf.namelist()[0]) as excel_file:
                            excel_data = pd.read_excel(excel_file, sheet_name=sheet_name)
                elif file_extension == '.tar':
                    with tarfile.open(file, 'r') as tar:
                        with tar.extractfile(tar.getnames()[0]) as excel_file:
                            excel_data = pd.read_excel(excel_file, sheet_name=sheet_name)
                elif file_extension == '.bz2':
                    with bz2.BZ2File(file, 'rb') as bz2_file:
                        excel_data = pd.read_excel(bz2_file, sheet_name=sheet_name)
                else:
                    excel_data = pd.read_excel(file, sheet_name=sheet_name, header=use_header)

                row_count = excel_data.shape[0] - default_skip_header - default_skip_footer
                task_logger.info("The number of records in the source file is: %s", row_count)
                count1 = 0
                if use_header != 0:
                    excel_data.columns = [f"column{i+1}" for i in range(len(excel_data.columns))]
                dataframe = excel_data.iloc[:row_count]
                count1 = 1 + count1
                task_logger.info('%s iteration', str(count1))
                yield dataframe
    except Exception as error:
        task_logger.exception("reading_excel() is %s", str(error))
        raise error
    