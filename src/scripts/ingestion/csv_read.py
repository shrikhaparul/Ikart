""" script for reading data from csv"""
import sys
import glob
import logging
import importlib
import os
import pandas as pd
from io import StringIO

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
            default_delimiter = delimiter if source["delimiter"] is None else\
            source["delimiter"]
            default_skip_header = skip_header if source["skip_header"]\
            is None else source["skip_header"]
            default_skip_footer = skip_footer if source["skip_footer"]\
            is None else source["skip_footer"]
            default_quotechar = quotechar if source["quote_char"] in {None,"None","none",""}  else\
            source["quote_char"]
            default_escapechar=escapechar if source["escape_char"] in {None,"None","none",""}  \
            else source["escape_char"]
            default_escapechar = "\t" if default_escapechar == "\\t" else default_escapechar
            default_escapechar = "\n" if default_escapechar == "\\n" else default_escapechar
            default_select_cols = None if source["select_columns"] in (None,"None","none","") else \
                list(source["select_columns"].split(","))
            default_alias_cols = None if source["alias_columns"] in (None,"None","none","") else\
            list(source["alias_columns"].split(","))
            default_encoding = "utf-8" if source["encoding"]in (None,"None","none","") else\
            source["encoding"]
            for file in all_files:
                data = pd.read_csv(filepath_or_buffer = file,encoding=default_encoding,
                low_memory=False)
                audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',data.shape[0],
                iter_value)
                row_count = data.shape[0]-default_skip_footer
                count1 = 0
                task_logger.info(type(source["select_columns"]))
                task_logger.info("select columns before:%s",default_select_cols)                
                task_logger.info("select columns after:%s",default_select_cols)
                if source["select_columns"] is not None and \
                source["alias_columns"] is not None:
                    default_header = 0
                    if source["header"] == "Y":
                        use_header = True
                    else:
                        use_header = False
                    for csv_chunk in pd.read_csv(file, header=0 if  use_header else  None,
                                                 chunksize=source["chunk_size"], names = default_alias_cols,
                        sep = default_delimiter, usecols = default_select_cols,
                        engine='python',
                        nrows = row_count,
                        quotechar = default_quotechar, escapechar = default_escapechar,
                        encoding = default_encoding
                        ):
                        if not use_header:
                                csv_chunk.columns =default_select_cols

                        if default_skip_header > 0:
                            csv_chunk = csv_chunk.iloc[default_skip_header:]
                        count1 += 1
                        task_logger.info(ITERATION, str(count1))
                        yield csv_chunk
                elif (source["select_columns"] is not None and source["alias_columns"] is None):
                    default_header = 'infer' if source["alias_columns"] is None else 0
                    if source["header"] == "Y":
                        use_header = True
                    else:
                        use_header = False

                    for csv_chunk in pd.read_csv(file, header=0 if  use_header else  None,
                                                chunksize=source["chunk_size"], names = default_select_cols,
                    sep = default_delimiter, usecols = default_select_cols,
                    nrows = row_count,
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        if not use_header:
                            if source["alias_columns"] is None:
                                csv_chunk.columns = [f"column{i+1}" for i in range(len(csv_chunk.columns))]
                            else :
                                csv_chunk.columns = list(source["alias_columns"].split(","))
                        if default_skip_header > 0:
                            csv_chunk = csv_chunk.iloc[default_skip_header:]
                        count1 += 1
                        task_logger.info(ITERATION, str(count1))
                        yield csv_chunk
                elif  (source["select_columns"] is None and source["alias_columns"] is not None):
                    default_header = 'infer' if source["alias_columns"] is None else 0
                    if source["header"] == "Y":
                        use_header = True
                    else:
                        use_header = False
                    for csv_chunk in pd.read_csv(file, header=0 if use_header else  None,
                     chunksize=source["chunk_size"], names = default_alias_cols,
                    sep = default_delimiter, usecols = default_select_cols,
                    nrows = row_count,
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        if not use_header:
                            if source["alias_columns"] is None:
                                csv_chunk.columns = [f"column{i+1}" for i in range(len(csv_chunk.columns))]
                            else :
                                csv_chunk.columns = list(source["alias_columns"].split(","))
                        if default_skip_header > 0:
                            csv_chunk = csv_chunk.iloc[default_skip_header:]
                        count1 += 1
                        task_logger.info(ITERATION, str(count1))
                        yield csv_chunk
                elif source["select_columns"] is None and source["alias_columns"] is None:
                    default_header = 'infer' if source["alias_columns"] is None else None
                    if source["header"] == "Y":
                        use_header = True
                    else:
                        use_header = False
                    default_select_cols = None
                    # Read the CSV data from the file
                    for csv_chunk in pd.read_csv(file, header=0 if  use_header else  None,
                    chunksize=source["chunk_size"], names = default_alias_cols,
                    sep = default_delimiter, usecols = default_select_cols,
                    nrows = row_count,
                    quotechar = default_quotechar, escapechar = default_escapechar,
                    encoding = default_encoding):
                        if not use_header:
                            csv_chunk.columns = [f"column{i+1}" for i in range(len(csv_chunk.columns))]
                        if default_skip_header > 0:
                            csv_chunk = csv_chunk.iloc[default_skip_header:]
                        count1 += 1
                        task_logger.info(ITERATION, str(count1))
                        yield csv_chunk
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.error("reading_csv() is %s", str(error))
        raise error
