""" script for reading data from excel"""
import glob
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
            log2.info("pipeline txt file does not exist")
    except Exception as error:
        log2.exception("write_to_txt1: %s.", str(error))
        raise error

def read(prj_nm,json_data: dict,task_id,run_id,paths_data,file_path,skip_header = 0,
skip_footer= 0, sheet_name= 0)-> bool:
    """ function for reading data from excel"""
    try:
        log2.info("reading excel initiated...")
        path1 = json_data["task"]["source"]["source_file_path"]+\
        json_data["task"]["source"]["source_file_name"]
        # function for reading files present in a folder with different csv formats
        all_files = [f for f_ in [glob.glob(e) for e in (f'{path1}*.xls',
        f'{path1}*.xlsx', f'{path1}*.xlsm', f'{path1}*.xlsb') ] for f in f_]
        log2.info("list of files which were read")
        log2.info(all_files)
        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        from engine_code import audit
        audit_json_path = paths_data["folder_path"] +paths_data["Program"]+prj_nm+\
        paths_data["audit_path"]+task_id+\
                '_audit_'+run_id+'.json'
        if all_files == []:
            log2.error("'%s' SOURCE FILE not found in the location",
            json_data["task"]["source"]["source_file_name"])
            write_to_txt(task_id,'FAILED',file_path)
            audit(audit_json_path,json_data, task_id,run_id,'STATUS','FAILED')
            sys.exit()
            #return False
        else:
            default_skip_header = skip_header if json_data["task"]["source"]["skip_header"]==" "\
            else json_data["task"]["source"]["skip_header"]
            default_skip_footer = skip_footer if json_data["task"]["source"]["skip_footer"]==" "\
            else json_data["task"]["source"]["skip_footer"]
            # default_usecols = usecols  if json_data["task"]["source"]["select_columns"]==" "\
            # else list(json_data["task"]["source"]["select_columns"].split(","))
            default_sheet_name = sheet_name if json_data["task"]["source"]["sheet_name"]==" "\
             else json_data["task"]["source"]["sheet_name"]
            for file in all_files:
            # print(default_alias_cols)
            # default_header ='infer' if json_data["task"]["source"]["alias_columns"] == " "\
            #else None
                count = 0
            # df = pd.DataFrame()
            for file in all_files:
                count +=1
                data = pd.read_excel(io = file)
                # print(type(data))
                row_count = data.shape[0]-default_skip_header-default_skip_footer
                log2.info("the number of records in source file is:%s", row_count)
                count1 = 0
                # print(row_count)
                datafram = pd.read_excel(io = file, sheet_name = default_sheet_name,
                skiprows = default_skip_header,nrows = row_count)
                count1 = 1 + count1
                log2.info('%s iteration' , str(count1))
                yield datafram
    except Exception as error:
        log2.exception("reading_excel() is %s", str(error))
        raise error
