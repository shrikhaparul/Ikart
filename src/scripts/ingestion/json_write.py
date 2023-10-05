""" script for ingesting data to json"""
import logging
import os
from datetime import datetime
import json
import pandas as pd
from utility import replace_date_placeholders

task_logger = logging.getLogger('task_logger')

def split_large_json_file(input_file, output_directory, records_per_split, ext):
    '''function to split the large JSON files based on the number of records'''
    default_encoding = 'utf_8'
    # Open the input JSON file for reading
    with open(input_file, 'r',encoding=default_encoding) as infile:
        records = json.load(infile)
        split_number = 1
        record_count = 0
        if records_per_split <= 0:
            # If records_per_split is zero or negative, write the entire JSON content to one file
            split_file_path = f"{output_directory}{ext}"
            with open(split_file_path, 'w',encoding=default_encoding) as split_file:
                json.dump(records, split_file, indent=4)
        else:
            # Initialize an empty list to hold the records for each split
            split_records = []
            for record in records:
                split_records.append(record)
                record_count += 1
                if record_count >= records_per_split:
                    # Write the records to a split file
                    split_file_path = f"{output_directory}_part_000{split_number}{ext}"
                    with open(split_file_path, 'w',encoding=default_encoding) as split_file:
                        json.dump(split_records, split_file, indent=4)
                    # Reset the record count and clear the split_records list
                    record_count = 0
                    split_records = []
                    split_number += 1
            # Write any remaining records to the final split file
            if record_count > 0:
                split_file_path = f"{output_directory}_part_000{split_number}{ext}"
                with open(split_file_path, 'w',encoding=default_encoding) as split_file:
                    json.dump(split_records, split_file, indent=4)
    # Remove the original input JSON file
    os.remove(input_file)

def write(json_data: dict, dataframe, counter) -> bool:
    """ function for writing to JSON """
    try:
        target = json_data["task"]["target"]
        file_path = target["file_path"]
        file_name = target["file_name"]
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to JSON initiated")
        check = True if target['index'] == "False" else False
        # Reset the index and create an 'index' column
        dataframe.reset_index(drop=check, inplace=True)

        if counter == 1: # If it's the first chunk, write the data to a new JSON file
            if os.path.exists(target["file_path"]+file_name):
                os.remove(target["file_path"]+file_name)
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                dataframe.to_json(file_path + file_name, orient='records', lines=False)
            else:
                dataframe.to_json(file_path + file_name, orient='records', lines=False)
        else: # If it's not the first chunk, read the existing JSON file and append the new data
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                existing_dataframe = pd.read_json(file_path + file_name, orient='records')
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_json(file_path + file_name, orient='records', lines=False)
            else:
                existing_dataframe = pd.read_json(file_path + file_name, orient='records')
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_json(file_path + file_name, orient='records', lines=False)
        filename_wo_ext = os.path.splitext(file_name)[0]
        extension = os.path.splitext(file_name)[1]
        records_per_split = 0 if 'target_max_record_count' not in target else \
        target['target_max_record_count']
        if records_per_split > 0:
            split_large_json_file(file_path+file_name, file_path+filename_wo_ext,
                            records_per_split,extension)
        task_logger.info("JSON conversion completed")
        return True
    except Exception as error:
        task_logger.exception("converting_to_json() is %s", str(error))
        raise error
