"""code to write the output dataframes into parquet files"""
import logging
import os
from datetime import datetime
import importlib
import sys
import pyarrow.parquet as pq
import pyarrow as pa
from utility import replace_date_placeholders,update_status_file

task_logger = logging.getLogger('task_logger')

def write(json_data,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path):
    """ function for writing to parquet """
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        target = json_data["task"]["target"]
        file_path = local_temp_path
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to parquet initiated")
        def_audit_columns = "inactive" if target["audit_columns"] in ("",None,"") \
        else target["audit_columns"]
        if counter == 1:  # If it's the first chunk, write the data to a new Parquet file
            if os.path.exists(target["file_path"] + file_name):
                os.remove(target["file_path"] + file_name)
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = "etl_user"
                datafram['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY'] = " "
                datafram['UPDT_DTTM'] = " "
                table = pa.Table.from_pandas(datafram)
                pq.write_table(table, file_path + file_name, version='1.0')
            else:
                table = pa.Table.from_pandas(datafram)
                pq.write_table(table, file_path + file_name, version='1.0')
        else:  # If it's not the first chunk, read the existing Parquet file and append the new data
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = "etl_user"
                datafram['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY'] = " "
                datafram['UPDT_DTTM'] = " "
                table = pa.Table.from_pandas(datafram)
                existing_table = pq.read_table(file_path + file_name)
                if existing_table.schema != table.schema:
                    # Align schemas by casting if they are different
                    table = table.cast(existing_table.schema)
                updated_table = pa.concat_tables([existing_table, table])
                pq.write_table(updated_table, file_path + file_name, version='1.0')
            else:
                table = pa.Table.from_pandas(datafram)
                existing_table = pq.read_table(file_path + file_name)
                if existing_table.schema != table.schema:
                    # Align schemas by casting if they are different
                    table = table.cast(existing_table.schema)
                updated_table = pa.concat_tables([existing_table, table])
                pq.write_table(updated_table, file_path + file_name, version='1.0')
        task_logger.info("parquet ingestion completed")
        return True,file_path,file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("ingesting_to_parquet() is %s", str(error))
        raise error
    