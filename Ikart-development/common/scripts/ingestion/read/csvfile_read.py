""" script for reading data from csv"""
import sys
import glob
import importlib
import logging
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


def read(json_data: dict,task_id,run_id,paths_data,file_path,iter_value,
        delimiter = ",",skip_header = 0,skip_footer= 0, quotechar = '"', escapechar = None):
    """ function for reading data from csv"""
    try:
        log2.info("reading csv initiated...")
        path = json_data["task"]["source"]["file_path"]+\
        json_data["task"]["source"]["file_name"]
        # function for reading files present in a folder with different csv formats
        all_files = [f for f_ in [glob.glob(e) for e in (f'{path}*.zip',f'{path}*.csv',
        f'{path}*.csv.zip', f'{path}*.gz', f'{path}*.bz2',f'{path}*.txt') ] for f in f_]
        log2.info("list of files which were read")
        log2.info(all_files)
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        if all_files == []:
            log2.error("'%s' SOURCE FILE not found in the location",
            json_data["task"]["source"]["file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
            sys.exit()
        else:
            default_delimiter = delimiter if json_data["task"]["source"]["delimiter"]==" " else\
            json_data["task"]["source"]["delimiter"]
            default_skip_header=skip_header if json_data["task"]["source"]["skip_header"]==" " else\
            json_data["task"]["source"]["skip_header"]
            default_skip_footer=skip_footer if json_data["task"]["source"]["skip_footer"]==" " else\
            json_data["task"]["source"]["skip_footer"]
            default_quotechar = quotechar if json_data["task"]["source"]["quote_char"]==" " else\
            json_data["task"]["source"]["quote_char"]
            default_escapechar=escapechar if json_data["task"]["source"]["escape_char"]=="none" \
            else json_data["task"]["source"]["escape_char"]
            default_select_cols = None if json_data["task"]["source"]["select_columns"]==" " else\
            list(json_data["task"]["source"]["select_columns"].split(","))
            default_alias_cols = None if json_data["task"]["source"]["alias_columns"]==" " else\
            list(json_data["task"]["source"]["alias_columns"].split(","))
            default_encoding = "utf-8" if json_data["task"]["source"]["encoding"]==" " else\
            json_data["task"]["source"]["encoding"]
            # print(default_alias_cols)
            default_header ='infer' if json_data["task"]["source"]["alias_columns"] == " " else None
            for file in all_files:
                data = pd.read_csv(filepath_or_buffer = file,encoding=default_encoding,
                low_memory=False)
                # print(type(data))
                row_count = data.shape[0]-default_skip_header-default_skip_footer
                log2.info("the number of records in source file is:%s", row_count)
                count1 = 0
                # print(row_count)
                datafram = pd.read_csv(filepath_or_buffer = file, names = default_alias_cols,
                header = default_header,sep = default_delimiter,usecols = default_select_cols,
                skiprows = default_skip_header,nrows = row_count,quotechar = default_quotechar,
                escapechar = default_escapechar,encoding = default_encoding)
            count1 = 1 + count1
            log2.info('%s iteration' , str(count1))
            yield datafram
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        log2.exception("reading_csv() is %s", str(error))
        raise error
        