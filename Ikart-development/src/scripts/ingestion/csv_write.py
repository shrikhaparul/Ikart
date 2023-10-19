""" script for writing data to csv file"""
import logging
from datetime import datetime
import os
from ast import literal_eval
from utility import replace_date_placeholders

task_logger = logging.getLogger('task_logger')

def split_large_file(input_file, output_directory, records_per_split, ext):
    '''function to split the large files based on number of records'''
    # Open the input file for reading
    with open(input_file, 'r') as infile:
        # Read the header
        header = infile.readline()

        split_number = 1
        record_count = 0
        split_file_path = f"{output_directory}_part_000{split_number}{ext}" \
        if records_per_split > 0 else f"{output_directory}{ext}"
        split_file = open(split_file_path, 'w')
        split_file.write(header)

        if records_per_split > 0:
            while True:
                line = infile.readline()
                if not line:
                    break
                split_file.write(line)
                record_count += 1

                if record_count >= records_per_split:
                    # Close the current split file and create a new one
                    split_file.close()
                    split_number += 1
                    split_file_path = f"{output_directory}_part_000{split_number}{ext}"
                    split_file = open(split_file_path, 'w')
                    split_file.write(header)
                    record_count = 0

        # Close the final split file
        split_file.close()
    # os.remove(input_file)

def write(json_data: dict,datafram, counter) -> bool:
    """ function for writing data to csv file"""
    try:
        target = json_data["task"]["target"]
        file_name = replace_date_placeholders(target['file_name'])
        file_path = replace_date_placeholders(target['file_path'])
        task_logger.info("writing data to csv file")
        created_by = json_data['created_by'] if 'created_by' in json_data else "etl_user"
        if counter ==1: # for first iteration
            if os.path.exists(file_path+file_name):
                os.remove(file_path+file_name)
            if target["audit_columns"] == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(file_path+file_name,
                sep=target["delimiter"], #header=literal_eval(target["header"]),
                index=literal_eval(target["index"]), mode='a',
                encoding=target["encoding"])
            else:
                # if audit_columns are  not active
                datafram.to_csv(file_path+file_name,
                sep=target["delimiter"], #header=literal_eval(
                # target["header"]),
                index=literal_eval(target["index"]), mode='a',
                encoding=target["encoding"])
        else: # for iterations other than one
            if target["audit_columns"] == "active":
                # if audit_columns are active
                datafram['CRTD_BY'] = created_by
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(file_path+file_name,
                sep=target["delimiter"], header=False,
                index=literal_eval(target["index"]),
                mode='a', encoding=target["encoding"])
            else:
                # if audit_columns are  not active
                datafram.to_csv(file_path+file_name,
                sep=target["delimiter"], header=False,
                index=literal_eval(target["index"]),
                mode='a', encoding=target["encoding"])
        filename_wo_ext = os.path.splitext(file_name)[0]
        extension = os.path.splitext(file_name)[1]
        records_per_split = 0 if 'target_max_record_count' not in target or \
        target['target_max_record_count'] in (None,"None","") else \
        target['target_max_record_count']
        if records_per_split > 0:
            split_large_file(file_path+file_name, file_path+filename_wo_ext,
                            records_per_split,extension)
        return True
    except Exception as error:
        task_logger.exception("ingest_data_to_csv() is %s", str(error))
        raise error
