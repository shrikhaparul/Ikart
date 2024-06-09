"""code to write the output dataframes into parquet files"""
import logging
import os
from datetime import datetime
import importlib
import sys
import pyarrow.parquet as pq
import pyarrow as pa
from utility import update_status_file,construct_file_name

task_logger = logging.getLogger('task_logger')

def write(json_data: dict,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path,subtask_target_section,group_no,subtask_no):
    """ function for writing data to parquet """
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        target = subtask_target_section
        file_path = local_temp_path
        file_name = construct_file_name(target)
        task_logger.info("ingestiong data to parquet initiated..")
        created_by = json_data['created_by'] if 'created_by' in json_data else "etl_user"
        def_audit_columns = "inactive" if target["audit_fields"] in ("",None,"") \
        else target["audit_fields"]
        if counter == 1:  # If it's the first chunk, write the data to a new Parquet file
            if os.path.exists(file_path + file_name):
                os.remove(file_path + file_name)
            if def_audit_columns == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = created_by
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
                datafram['CRTD_BY'] = created_by
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
        audit(json_data,task_id,run_id,paths_data,'STATUS','FAILED',iter_value,group_no,subtask_no)
        task_logger.exception("ingesting_to_parquet() is %s", str(error))
        raise error
