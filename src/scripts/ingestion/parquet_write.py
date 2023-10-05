import logging
import os
from datetime import datetime
import pandas as pd
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow as pa
from utility import replace_date_placeholders

task_logger = logging.getLogger('task_logger')

def split_large_parquet_file(input_file, output_directory, records_per_split, ext):
    '''function to split the large Parquet files based on the number of records'''
    df = pq.read_table(input_file).to_pandas()

    split_number = 1
    record_count = 0
    output_dfs = []

    if records_per_split <= 0:
        # If records_per_split is zero or negative, write the entire Parquet content to one file
        split_file_path = f"{output_directory}{ext}"
        pq.write_table(pa.Table.from_pandas(df), split_file_path)
    else:
        for _, row in df.iterrows():
            output_dfs.append(row)
            record_count += 1

            if record_count >= records_per_split:
                # Write the records to a split Parquet file
                split_file_path = f"{output_directory}_part_000{split_number}{ext}"
                pq.write_table(pa.Table.from_pandas(pd.concat(output_dfs, axis=1).T),
                               split_file_path)

                # Reset the record count and clear the output DataFrames
                record_count = 0
                output_dfs = []
                split_number += 1

        # Write any remaining records to the final split Parquet file
        if record_count > 0:
            split_file_path = f"{output_directory}_part_000{split_number}{ext}"
            pq.write_table(pa.Table.from_pandas(pd.concat(output_dfs, axis=1).T), split_file_path)
    # Remove the original input JSON file
    os.remove(input_file)

def write(json_data: dict, dataframe, counter) -> bool:
    """ function for writing to parquet """
    try:
        target = json_data["task"]["target"]
        file_path = target["file_path"]
        file_name = target["file_name"]
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to parquet initiated")
        check = True if target['index'] == "False" else False
        # Reset the index and create an 'index' column
        dataframe.reset_index(drop=check, inplace=True)

        if counter == 1:  # If it's the first chunk, write the data to a new Parquet file
            if os.path.exists(target["file_path"] + file_name):
                os.remove(target["file_path"] + file_name)
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY'] = "etl_user"
                dataframe['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY'] = " "
                dataframe['UPDT_DTTM'] = " "
                table = pa.Table.from_pandas(dataframe)
                pq.write_table(table, file_path + file_name, version='1.0')
            else:
                table = pa.Table.from_pandas(dataframe)
                pq.write_table(table, file_path + file_name, version='1.0')
        else:  # If it's not the first chunk, read the existing Parquet file and append the new data
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY'] = "etl_user"
                dataframe['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY'] = " "
                dataframe['UPDT_DTTM'] = " "
                table = pa.Table.from_pandas(dataframe)
                existing_table = pq.read_table(file_path + file_name)
                updated_table = pa.concat_tables([existing_table, table])
                pq.write_table(updated_table, file_path + file_name, version='1.0')
            else:
                table = pa.Table.from_pandas(dataframe)
                existing_table = pq.read_table(file_path + file_name)
                updated_table = pa.concat_tables([existing_table, table])
                pq.write_table(updated_table, file_path + file_name, version='1.0')

        task_logger.info("parquet conversion completed")

        # Check if the Parquet file needs to be split
        records_per_split = target['target_max_record_count']
        filename_wo_ext = os.path.splitext(file_name)[0]
        records_per_split = 0 if 'target_max_record_count' not in target else \
        target['target_max_record_count']
        if records_per_split > 0:
            split_large_parquet_file(file_path + filename_wo_ext + '.parquet',
            file_path + filename_wo_ext, records_per_split, '.parquet')
        return True
    except Exception as error:
        task_logger.exception("converting_to_parquet() is %s", str(error))
        raise error
