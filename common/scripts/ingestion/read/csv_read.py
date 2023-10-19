""" script for reading data from csv"""
import sys
import glob
import logging
import importlib
import os
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

def read(json_data: dict,task_id,run_id,paths_data,file_path,iter_value,
        delimiter = ",", skip_header= 0,
        skip_footer= 0, quotechar = '"', escapechar = None):
    """ function for reading data from csv"""
    try:
        source = json_data["task"]["source"]
        task_logger.info("reading csv initiated...")
        path = source["file_path"]+\
        source["file_name"]
        # function for reading files present in a folder with different csv formats
        all_files = [f for f_ in [glob.glob(e) for e in (f'{path}*.zip',f'{path}*.csv',
        f'{path}*.csv.zip', f'{path}*.gz', f'{path}*.bz2') ] for f in f_]
        task_logger.info("list of files which were read")
        task_logger.info(all_files)
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
            default_delimiter = delimiter if source["delimiter"]==" " else\
            source["delimiter"]
            default_skip_header = skip_header if source["skip_header"]\
            ==" " else source["skip_header"]
            default_skip_footer = skip_footer if source["skip_footer"]\
            ==" " else source["skip_footer"]
            default_quotechar = quotechar if source["quote_char"]==" " else\
            source["quote_char"]
            default_escapechar=escapechar if source["escape_char"]=="none" \
            else source["escape_char"]
            default_select_cols = None if source["select_columns"]==" " else\
            list(source["select_columns"].split(","))
            default_alias_cols = None if source["alias_columns"]==" " else\
            list(source["alias_columns"].split(","))
            default_encoding = "utf-8" if source["encoding"]==" " else\
            source["encoding"]
            for file in all_files:
                data = pd.read_csv(filepath_or_buffer = file,encoding=default_encoding,
                low_memory=False)
                audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',data.shape[0],
                iter_value)
                row_count = data.shape[0]-default_skip_header-default_skip_footer
                count1 = 0
                if source["select_columns"] != " " and \
                source["alias_columns"] != " ":
                    default_header = 0
                    # print(row_count)
                    for chunk in pd.read_csv(filepath_or_buffer = file, names = default_alias_cols,
                    header = default_header,engine='python',sep = default_delimiter,
                    usecols = default_select_cols, skiprows = default_skip_header,nrows = row_count,
                    chunksize = source["chunk_size"],
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        count1 = 1 + count1
                        task_logger.info(ITERATION , str(count1))
                        # print(list(chunk.columns))
                        yield chunk
                elif (source["select_columns"] != " " and source["alias_columns"] == " ") or \
                (source["select_columns"] == " " and source["alias_columns"] != " "):
                    default_header = 'infer' if source[
                        "alias_columns"]== " " else 0
                    # print(row_count)
                    for chunk in pd.read_csv(filepath_or_buffer = file, names = default_alias_cols,
                    header = default_header,sep = default_delimiter, usecols = default_select_cols,
                    skiprows = default_skip_header,nrows = row_count,
                    chunksize = source["chunk_size"],
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        count1 = 1 + count1
                        task_logger.info(ITERATION , str(count1))
                        # print(list(chunk.columns))
                        yield chunk
                elif source["select_columns"] == " " and \
                source["alias_columns"] == " ":
                    default_header ='infer' if source["alias_columns"] ==\
                     " " else None
                    # print(row_count)
                    for chunk in pd.read_csv(filepath_or_buffer = file, names = default_alias_cols,
                    header = default_header,sep = default_delimiter, usecols = default_select_cols,
                    skiprows = default_skip_header,nrows = row_count,
                    chunksize = source["chunk_size"],
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        count1 = 1 + count1
                        task_logger.info(ITERATION , str(count1))
                        # print(list(chunk.columns))
                        yield chunk
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("reading_csv() is %s", str(error))
        raise error
