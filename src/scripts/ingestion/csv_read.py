""" script for reading data from csv file"""
import sys
import glob
import logging
import importlib
import os
import pandas as pd

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
ITERATION='Number of records read - %s'

def csv_functionality(default_select_cols,default_alias_cols,source,row_count,
    file,default_delimiter,default_quotechar,default_escapechar,default_encoding,
    compression,default_skip_header):
    """function to consider different parameters in place"""
    if source["header"] == "Y":
        use_header = True
    else:
        row_count = row_count + 1
        use_header = False
    task_logger.info("default_select_cols:%s, default_alias_cols:%s",
     default_select_cols,default_alias_cols)
    if default_select_cols is not None and \
    default_alias_cols is not None:
        # print(row_count)
        for csv_chunk in pd.read_csv(file, header=0 if  use_header else  None,
            chunksize=source["chunk_size"], names = default_alias_cols,
            sep = default_delimiter, usecols = default_select_cols,
            engine='python',
            nrows = row_count,
            quotechar = default_quotechar, escapechar = default_escapechar,
            encoding = default_encoding,compression=compression
            ):
            if not use_header:
                csv_chunk.columns =default_select_cols

            if default_skip_header > 0:
                csv_chunk = csv_chunk.iloc[default_skip_header:]
            yield csv_chunk
    elif (default_select_cols is not None and default_alias_cols is None):
        for csv_chunk in pd.read_csv(file, header=0 if  use_header else  None,
        chunksize=source["chunk_size"], names = default_select_cols,
        sep = default_delimiter, usecols = default_select_cols,
        nrows = row_count,
        quotechar = default_quotechar, escapechar = default_escapechar,
        encoding = default_encoding,compression=compression):
            if not use_header:
                if default_alias_cols is None:
                    csv_chunk.columns = [
                        f"column{i+1}" for i in range(len(csv_chunk.columns))]
                else :
                    csv_chunk.columns = list(source["alias_columns"].split(","))
            if default_skip_header > 0:
                csv_chunk = csv_chunk.iloc[default_skip_header:]
            yield csv_chunk
    elif  (default_select_cols is None and default_alias_cols is not None):
        for csv_chunk in pd.read_csv(file, header=0 if use_header else None,
            chunksize=source["chunk_size"], names = default_alias_cols,
        sep = default_delimiter, usecols = default_select_cols,
        nrows = row_count,
        quotechar = default_quotechar, escapechar = default_escapechar,
        encoding = default_encoding,compression=compression):
            if not use_header:
                if source["alias_columns"] is None:
                    csv_chunk.columns = [
                        f"column{i+1}" for i in range(len(csv_chunk.columns))]
                else :
                    csv_chunk.columns = list(source["alias_columns"].split(","))
            if default_skip_header > 0:
                csv_chunk = csv_chunk.iloc[default_skip_header:]
            yield csv_chunk
    elif default_select_cols is None and default_alias_cols is None:
        default_select_cols = None
        # Read the CSV data from the file
        for csv_chunk in pd.read_csv(file, header=0 if  use_header else None,
        chunksize=source["chunk_size"], names = default_alias_cols,
        sep = default_delimiter, usecols = default_select_cols,
        nrows = row_count,
        quotechar = default_quotechar, escapechar = default_escapechar,
        encoding = default_encoding,compression=compression):
            if not use_header:
                csv_chunk.columns = [
                    f"column{i+1}" for i in range(len(csv_chunk.columns))]
            if default_skip_header > 0:
                csv_chunk = csv_chunk.iloc[default_skip_header:]
            yield csv_chunk

def read(json_data: dict,task_id,run_id,paths_data,file_path,iter_value, local_file_path,
        delimiter = ",", skip_header= 0,
        skip_footer= 0, quotechar = '"', escapechar = None):
    """ function for reading data from csv"""
    try:
        
        task_logger.info("reading csv initiated...")
        source = json_data["task"]["source"]
        # src_file_path = local_file_path
        if local_file_path == None:
            local_file_path = " "
            src_file_path = source["file_path"]
            file_name = source["file_name"]
            if not src_file_path.endswith('/'):
                src_file_path = src_file_path + '/'
            pattern = os.path.join(src_file_path, file_name)
            
        else :
            pattern = local_file_path
            
        all_files = glob.glob(pattern)
        # source["file_name"]   
        # function for reading files present in a folder with different csv formats
        # Combine file_path and file_name
        # Ensure src_file_path ends with a trailing slash
        
        # Combine file_path and file_name using os.path.join
        # Use glob.glob to get a list of matching file paths
        
        task_logger.info("list of files which were read")
        task_logger.info("all files %s", all_files)
        
        if source['decryption'] == "yes" or source['compression'] not in ("","None"):
            default_select_cols = None
            default_alias_cols = None
        else:
            default_select_cols = None if source["select_columns"] in (None,"None","none","") else \
                list(source["select_columns"].split(","))
            default_alias_cols = None if source["alias_columns"] in (None,"None","none","") else\
            list(source["alias_columns"].split(","))

        engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        engine_code = importlib.import_module("engine_code")
        audit = getattr(engine_code, "audit")
        
        if not all_files:
            task_logger.error("'%s' SOURCE FILE not found in the location",
            source["file_name"])
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
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
            default_encoding = "utf-8" if source["encoding"] in (None,"None","none","") else\
            source["encoding"]
            default_encoding = "latin1" if source["encoding"] == "other" else default_encoding
            task_logger.info("Source chunk size is: %s", source["chunk_size"])
            dataframes = []  # List to collect dataframes from all files
            for file in all_files:
                compression = 'infer'
                data = pd.read_csv(filepath_or_buffer = file,encoding=default_encoding,
                low_memory=False,compression=compression)
                # exit(0)
                audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',data.shape[0],
                iter_value)
                row_count = data.shape[0]-default_skip_footer
                task_logger.info("Source file record count is: %s", data.shape[0])

                chunks = list(csv_functionality(default_select_cols,default_alias_cols,
                source,row_count,file,default_delimiter,default_quotechar,default_escapechar,
                default_encoding,compression,default_skip_header))
                dataframes.extend(chunks)
            return dataframes  # Return the list of dataframes
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.error("reading_csv() is %s", str(error))
        raise error
    finally:
        if os.path.isfile(local_file_path) :
            os.remove(local_file_path)
            # Logging: Config file removal
            task_logger.info("Temporary file removed: %s ", local_file_path)
    
