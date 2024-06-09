""" script for writing data to csv file"""
import logging
from datetime import datetime
import os
import csv
import sys
import importlib
from utility import replace_date_placeholders,update_status_file

task_logger = logging.getLogger('task_logger')

def write(json_data: dict,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path):
    """ function for writing data to csv file"""
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        target = json_data["task"]["target"]
        file_name = replace_date_placeholders(target['file_name'])
        file_path = local_temp_path
        task_logger.info("writing data to csv file")
        created_by = json_data['created_by'] if 'created_by' in json_data else "etl_user"
        include_header = target.get("header", "Y") == "Y"
        quote = target['quote_char'] if "quote_char"  in target else None
        quote = None if quote in ("custom", "") else quote
        quoting1 = csv.QUOTE_NONE if quote is None else csv.QUOTE_ALL
        def_sep = "," if target["delimiter"] in ("", None, " ") else target["delimiter"]
        def_encoding = "utf-8" if target["encoding"] in ("", None, "") else target["encoding"]
        def_audit_columns = "inactive" if target["audit_columns"] in ("",None,"") \
        else target["audit_columns"]
        if counter ==1: # for first iteration
            if os.path.exists(file_path+file_name):
                os.remove(file_path+file_name)
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(file_path+file_name,
                sep=def_sep, mode='a',
                encoding=def_encoding, header = include_header, quotechar = quote,
                quoting = quoting1, index = False,
                escapechar='\\')
            else:
                datafram.to_csv(file_path+file_name,
                sep=def_sep, mode='a',
                encoding=def_encoding, header = include_header, quotechar = quote,
                quoting = quoting1, index = False, escapechar='\\')
        else: # for iterations other than one
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(file_path+file_name,
                sep=def_sep, header=False,
                mode='a', encoding = def_encoding, quotechar = quote, quoting = quoting1,
                index = False, escapechar='\\')
            else:
                # if audit_columns are  not active
                datafram.to_csv(file_path+file_name,
                sep=def_sep, header=False,
                mode='a', encoding = def_encoding, quotechar = quote, quoting = quoting1,
                index = False, escapechar='\\')
        task_logger.info("csv ingestion completed")
        return True, file_path, file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
